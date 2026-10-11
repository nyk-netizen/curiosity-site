#!/usr/bin/env python3
"""Generate cached Edge TTS recordings. No installation or book JSON changes."""

import argparse
import asyncio
import hashlib
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from audio_paths import resolve_book_audio
from validate_book import load_book, print_result, validate_book

CHINESE_VOICE = "zh-CN-XiaoxiaoNeural"
ENGLISH_VOICE = "en-US-AnaNeural"
DEFAULT_RATE = "-5%"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def get_backend():
    try:
        module = importlib.import_module("edge_tts")
    except ImportError:
        executable = shutil.which("edge-tts")
        if not executable:
            raise RuntimeError("未找到 edge_tts Python 库或 edge-tts 命令行；请使用已配置 edge-tts 的 Python 环境（本机可用 python3.11）。")

        async def save(text, voice, rate, output):
            # Pass arguments directly, never through a shell. '=...' handles
            # negative percentages for edge-tts's argparse command line.
            result = await asyncio.to_thread(
                subprocess.run, [executable, "--text", text, "--voice", voice,
                                 "--rate=" + rate, "--write-media", str(output)],
                capture_output=True, text=True, timeout=120)
            if result.returncode:
                raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "edge-tts 退出码非 0")
        return save

    async def save(text, voice, rate, output):
        await module.Communicate(text, voice, rate=rate).save(str(output))
    return save


def audio_jobs(book, voice=None, rate=DEFAULT_RATE):
    primary = voice or (ENGLISH_VOICE if book["language"] == "en" else CHINESE_VOICE)
    number = 0
    for chapter in book["chapters"]:
        for page in chapter["pages"]:
            number += 1
            yield number, "narration", f"p{number:02d}.mp3", page["narration"], primary, rate
            if book["language"] == "bilingual":
                yield number, "narration_en", f"p{number:02d}_en.mp3", page["narration_en"], ENGLISH_VOICE, rate


def write_manifest(path, entries):
    # Atomic writes keep a previous valid manifest on interruption.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".manifest-", suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
        json.dump({"version": 1, "files": entries}, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


async def make_audio(book, book_path, voice=None, rate=DEFAULT_RATE):
    started = time.monotonic()
    jobs = list(audio_jobs(book, voice, rate))
    # Check every output and manifest before writing anything, even if cached.
    manifest_path = resolve_book_audio("audio/manifest.json", book_path)
    paths = {job[2]: resolve_book_audio("audio/" + job[2], book_path) for job in jobs}
    for path in [manifest_path, *paths.values()]:
        if path == Path(book_path).resolve():
            raise ValueError("音频输出路径不能覆盖输入 JSON")
        if path.exists() and not path.is_file():
            raise ValueError(f"音频输出路径不是文件：{path.name}")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    entries = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("version") == 1 and isinstance(manifest.get("files"), dict):
                entries = manifest["files"]
        except (OSError, ValueError, AttributeError) as exc:
            print(f"警告：音频缓存清单无法读取，将重新生成：{exc}", file=sys.stderr)
    generated = cached = failed = total_bytes = 0
    backend = None
    for number, field, filename, text, selected_voice, selected_rate in jobs:
        path = paths[filename]
        expected = {"text_hash": digest(text.encode("utf-8")), "voice": selected_voice, "rate": selected_rate}
        entry = entries.get(filename)
        if (isinstance(entry, dict) and all(entry.get(key) == value for key, value in expected.items())
                and path.is_file() and path.stat().st_size > 0
                and entry.get("audio_hash") == digest(path.read_bytes())):
            cached += 1
            total_bytes += path.stat().st_size
            print(f"缓存：正文第 {number} 页 {field} → audio/{filename}", flush=True)
            continue
        # Never leave a stale recording available to --with-audio's fallback
        # after a text/voice/rate change and a failed network request.
        path.unlink(missing_ok=True)
        entries.pop(filename, None)
        temporary = None
        try:
            if backend is None:
                backend = get_backend()
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".tts-", suffix=".mp3", delete=False) as stream:
                temporary = Path(stream.name)
            await asyncio.wait_for(backend(text, selected_voice, selected_rate, temporary), timeout=120)
            size = temporary.stat().st_size
            if size == 0:
                raise RuntimeError("服务没有返回音频数据")
            expected["audio_hash"] = digest(temporary.read_bytes())
            os.replace(temporary, path)
            entries[filename] = expected
            generated += 1
            total_bytes += size
            print(f"已生成：正文第 {number} 页 {field} → audio/{filename}（{size} 字节）", flush=True)
        except Exception as exc:
            failed += 1
            print(f"正文第 {number} 页 {field}（audio/{filename}）生成失败：{type(exc).__name__}: {exc}；"
                  "Edge TTS 需要联网，请检查网络和服务可用性。", file=sys.stderr)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        write_manifest(manifest_path, entries)
    print(f"音频完成：新生成 {generated} 段，缓存 {cached} 段，失败 {failed} 段；"
          f"MP3 共 {total_bytes} 字节；耗时 {time.monotonic() - started:.2f} 秒")
    return 1 if failed else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="为每页旁白生成 Edge TTS MP3（在线服务）")
    parser.add_argument("book", type=Path)
    parser.add_argument("--voice", help="主旁白声音；默认中文晓晓、英文 Ana")
    parser.add_argument("--rate", default=DEFAULT_RATE, help="语速，默认 -5%%")
    # Accept the exact requested spelling: --rate -5% (not just --rate=-5%).
    arguments = list(sys.argv[1:] if argv is None else argv)
    for index in range(len(arguments) - 1, 0, -1):
        if arguments[index - 1] == "--rate" and re.fullmatch(r"[+-]\d+%", arguments[index]):
            arguments[index - 1:index + 1] = ["--rate=" + arguments[index]]
    args = parser.parse_args(arguments)
    if not re.fullmatch(r"[+-]\d+%", args.rate):
        parser.error("--rate 必须是带正负号的百分比，如 -5% 或 +10%")
    book, result = load_book(args.book)
    if result is None:
        result = validate_book(book, args.book)
    if not result["ok"]:
        print_result(result)
        return 1
    try:
        return asyncio.run(make_audio(book, args.book, args.voice, args.rate))
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"音频生成失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
