#!/usr/bin/env python3
"""Offline audio regression checks: mock Edge TTS, never contact the service."""

import asyncio
import base64
import contextlib
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import make_audio
import render_book
from audio_paths import resolve_book_audio

ROOT = Path(__file__).resolve().parent.parent


class AudioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="curiosity-audio-tests-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "book"
        self.directory.mkdir()
        self.input = self.directory / "book.json"
        self.book = json.loads((ROOT / "assets/sample_book.json").read_text(encoding="utf-8"))
        self.input.write_text(json.dumps(self.book, ensure_ascii=False), encoding="utf-8")
        self.calls = []
        calls = self.calls

        class Communicate:
            def __init__(self, text, voice, rate):
                self.text, self.voice, self.rate = text, voice, rate

            async def save(self, path):
                calls.append((self.text, self.voice, self.rate))
                Path(path).write_bytes(b"ID3" + self.text.encode("utf-8"))

        self.module = SimpleNamespace(Communicate=Communicate)

    def generate(self, **kwargs):
        with patch.dict(sys.modules, {"edge_tts": self.module}), contextlib.redirect_stdout(io.StringIO()):
            return asyncio.run(make_audio.make_audio(self.book, self.input, **kwargs))

    def payload(self):
        document = render_book.render_book(self.book, self.input)
        return json.loads(re.search(r'<script id="book-data" type="application/json">(.*?)</script>', document, re.S)[1])

    def test_cache_text_voice_rate_deleted_and_corrupt_file(self):
        self.assertEqual(self.generate(), 0)
        self.assertEqual(len(self.calls), 7)
        paths = sorted((self.directory / "audio").glob("*.mp3"))
        self.assertEqual([p.name for p in paths], [f"p{i:02d}.mp3" for i in range(1, 8)])
        times = [p.stat().st_mtime_ns for p in paths]
        self.assertEqual(self.generate(), 0)
        self.assertEqual(len(self.calls), 7)
        self.assertEqual([p.stat().st_mtime_ns for p in paths], times)
        self.book["chapters"][1]["pages"][0]["narration"] += "！"
        self.assertEqual(self.generate(), 0)
        self.assertEqual(len(self.calls), 8, "Only changed page regenerates")
        paths[0].unlink()
        paths[1].write_bytes(b"corrupt")
        self.assertEqual(self.generate(), 0)
        self.assertEqual(len(self.calls), 10, "Missing/corrupt MP3 regenerates")
        self.generate(voice="zh-CN-YunxiNeural")
        self.assertEqual(len(self.calls), 17)
        self.generate(voice="zh-CN-YunxiNeural", rate="+10%")
        self.assertEqual(len(self.calls), 24)
        # Fully cached runs work without Edge TTS installed or a network.
        with patch.object(make_audio, "get_backend", side_effect=AssertionError("Should use cache")):
            self.assertEqual(self.generate(voice="zh-CN-YunxiNeural", rate="+10%"), 0)

    def test_english_bilingual_defaults_and_render_numbering(self):
        self.book["language"] = "en"
        self.generate()
        self.assertTrue(all(voice == "en-US-AnaNeural" for _, voice, _ in self.calls))
        self.book["language"] = "bilingual"
        for chapter in self.book["chapters"]:
            for page in chapter["pages"]:
                page["narration_en"] = "Hello from this page."
        self.calls.clear()
        self.generate()
        self.assertEqual(len(self.calls), 14)
        self.assertEqual([voice for _, voice, _ in self.calls],
                         ["zh-CN-XiaoxiaoNeural", "en-US-AnaNeural"] * 7)
        for status, start in (("approved", 1), ("pending", 2)):
            self.book["parent_card"]["approval"]["status"] = status
            payload = self.payload()
            self.assertEqual(list(payload["narrations"]), [str(i) for i in range(start, start + 7)])
            for number, lines in enumerate(payload["narrations"].values(), 1):
                for suffix, line in zip(("", "_en"), lines):
                    self.assertEqual(base64.b64decode(line["audio"].split(",", 1)[1]),
                                     (self.directory / f"audio/p{number:02d}{suffix}.mp3").read_bytes())

    def test_render_no_audio_partial_audio_and_empty_audio(self):
        self.assertTrue(all("audio" not in lines[0] for lines in self.payload()["narrations"].values()))
        audio = self.directory / "audio"
        audio.mkdir()
        (audio / "p03.mp3").write_bytes(b"ID3test")
        (audio / "p04.mp3").write_bytes(b"")
        payload = self.payload()
        self.assertEqual([index for index, lines in payload["narrations"].items() if "audio" in lines[0]], ["3"])
        self.assertEqual(payload["narrations"]["3"][0]["audio"], "data:audio/mpeg;base64,SUQzdGVzdA==")

    def test_failed_page_removes_stale_audio_and_preserves_other_cache(self):
        self.generate()
        changed = self.book["chapters"][0]["pages"][1]
        changed["narration"] = "这页改过了。"

        async def fail(*args):
            raise ConnectionError("mock network offline")

        errors = io.StringIO()
        with patch.object(make_audio, "get_backend", return_value=fail), contextlib.redirect_stderr(errors):
            self.assertEqual(self.generate(), 1)
        self.assertIn("正文第 2 页 narration", errors.getvalue())
        self.assertIn("mock network offline", errors.getvalue())
        self.assertFalse((self.directory / "audio/p02.mp3").exists())
        self.assertEqual(len(list((self.directory / "audio").glob("*.mp3"))), 6)
        self.assertNotIn("p02.mp3", json.loads((self.directory / "audio/manifest.json").read_text())["files"])
        self.assertNotIn("audio", self.payload()["narrations"]["2"][0])
        self.assertFalse(list((self.directory / "audio").glob(".tts-*")))

    def test_corrupt_manifest_regenerates(self):
        self.generate()
        (self.directory / "audio/manifest.json").write_text("{broken")
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            self.assertEqual(self.generate(), 0)
        self.assertEqual(len(self.calls), 14)
        self.assertIn("缓存清单", errors.getvalue())

    def test_python_library_preferred_cli_fallback_and_missing_dependency(self):
        with patch.dict(sys.modules, {"edge_tts": self.module}), patch.object(make_audio.shutil, "which") as which:
            save = make_audio.get_backend()
            asyncio.run(save("你好", "voice", "-5%", self.directory / "preferred.mp3"))
            which.assert_not_called()
        with patch.object(make_audio.importlib, "import_module", side_effect=ImportError), \
                patch.object(make_audio.shutil, "which", return_value="/test/edge-tts"), \
                patch.object(make_audio.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run:
            asyncio.run(make_audio.get_backend()("text $(literal)", "voice", "-5%", self.directory / "cli.mp3"))
            self.assertEqual(run.call_args.args[0], ["/test/edge-tts", "--text", "text $(literal)",
                                                    "--voice", "voice", "--rate=-5%", "--write-media", str(self.directory / "cli.mp3")])
            self.assertNotIn("shell", run.call_args.kwargs)
        with patch.object(make_audio.importlib, "import_module", side_effect=ImportError), \
                patch.object(make_audio.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "未找到.*python3.11"):
                make_audio.get_backend()
        errors = io.StringIO()
        with patch.object(make_audio, "get_backend", side_effect=RuntimeError("未找到 edge_tts 或 edge-tts")), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
            self.assertEqual(make_audio.main([str(self.input)]), 1)
        self.assertIn("未找到 edge_tts 或 edge-tts", errors.getvalue())

    def test_cli_rate_spelling_and_invalid_input(self):
        with patch.dict(sys.modules, {"edge_tts": self.module}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(make_audio.main([str(self.input), "--rate", "-5%"]), 0)
        self.assertEqual(self.calls[0][2], "-5%")
        self.input.write_text("{}")
        with patch.object(make_audio, "get_backend") as backend, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(make_audio.main([str(self.input)]), 1)
            backend.assert_not_called()

    def test_render_with_audio_success_failure_and_launch_error(self):
        output = self.directory / "book.html"
        for returncode in (0, 1):
            def generate(command):
                self.assertEqual(command[0], sys.executable)
                if returncode == 0:
                    self.generate()
                return SimpleNamespace(returncode=returncode)
            errors = io.StringIO()
            with patch.object(render_book.subprocess, "run", side_effect=generate), \
                    patch.object(sys, "argv", ["render_book.py", str(self.input), str(output), "--with-audio"]), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                self.assertEqual(render_book.main(), 0)
            self.assertTrue(output.is_file())
            self.assertEqual("警告" in errors.getvalue(), returncode == 1)
            document = output.read_text()
            self.assertEqual(document.count('data:audio/mpeg;base64,'), 7 if returncode == 0 else 0)
            for path in (self.directory / "audio").glob("*.mp3"):
                path.unlink()
        with patch.object(render_book.subprocess, "run", side_effect=OSError("launch failed")), \
                patch.object(sys, "argv", ["render_book.py", str(self.input), str(output), "--with-audio"]), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(render_book.main(), 0)
        self.assertNotIn("data:audio/mpeg", output.read_text())

    def test_paths_reject_escape_and_external_symlinks_before_writes(self):
        outside = Path(self.temp.name) / "outside.mp3"
        outside.write_bytes(b"external content")
        for name in (str(outside), "../outside.mp3", "audio/../../outside.mp3", "C:\\outside.mp3"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                resolve_book_audio(name, self.input)
        (self.directory / "audio").symlink_to(Path(self.temp.name), target_is_directory=True)
        for action in (self.generate, self.payload):
            with self.assertRaisesRegex(ValueError, "外部符号链接"):
                action()
        (self.directory / "audio").unlink()
        (self.directory / "audio").mkdir()
        for filename in ("p01.mp3", "manifest.json"):
            linked = self.directory / "audio" / filename
            linked.symlink_to(outside)
            with self.assertRaises(ValueError):
                self.generate()
            if filename == "p01.mp3":
                with self.assertRaises(ValueError):
                    self.payload()
            linked.unlink()
        self.assertEqual(outside.read_bytes(), b"external content")
        # Internal symlinks and non-escaping '..' follow fix2's rules.
        local = self.directory / "audio/local.mp3"
        local.write_bytes(b"ID3safe")
        (self.directory / "audio/p01.mp3").symlink_to(local)
        self.assertIn("audio", self.payload()["narrations"]["1"][0])
        self.assertEqual(resolve_book_audio("audio/../audio/local.mp3", self.input), local.resolve())

    def test_audio_output_cannot_overwrite_input_through_internal_symlink(self):
        audio = self.directory / "audio"
        audio.mkdir()
        original = self.input.read_bytes()
        for filename in ("p01.mp3", "manifest.json"):
            linked = audio / filename
            linked.symlink_to(self.input)
            with self.assertRaisesRegex(ValueError, "不能覆盖输入 JSON"):
                self.generate()
            self.assertEqual(self.input.read_bytes(), original)
            linked.unlink()


if __name__ == "__main__":
    unittest.main(verbosity=2)
