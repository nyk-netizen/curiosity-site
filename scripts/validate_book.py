#!/usr/bin/env python3
"""Validate book JSON using the repository schema and its x-rules (stdlib only)."""

import argparse
import json
import re
from pathlib import Path, PureWindowsPath

ASSETS = Path(__file__).resolve().parent.parent / "assets"
WORD = re.compile(r"[A-Za-z0-9]+(?:['’\-][A-Za-z0-9]+)*")
ENGLISH_WORD = re.compile(r"[A-Za-z]+(?:['’\-][A-Za-z]+)*")
# x-rules.age_band_limits (the schema describes these limits in prose).
AGE_BAND_LIMITS = {"small": (3, 4, 30), "middle": (4, 6, 45), "large": (4, 8, 60)}


def resolve_book_image(filename, book_path):
    """Resolve an image within the book directory, including symlink targets."""
    relative = Path(filename)
    windows = PureWindowsPath(filename)
    if relative.is_absolute() or windows.drive or windows.root:
        raise ValueError("图片路径必须是书目录内的相对路径，不允许绝对路径")
    depth = 0
    for part in relative.parts:
        if part == "..":
            depth -= 1
            if depth < 0:
                raise ValueError("图片路径不能通过 ../ 越出书目录")
        elif part != ".":
            depth += 1
    try:
        directory = Path(book_path).resolve().parent
        resolved = (directory / relative).resolve(strict=True)
        resolved.relative_to(directory)
    except ValueError as exc:
        raise ValueError("图片真实路径必须位于书目录内（不允许外部符号链接）") from exc
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"图片文件不存在或无法解析：{filename}") from exc
    if not resolved.is_file():
        raise ValueError(f"图片路径不是文件：{filename}")
    return resolved


def child_facing_strings(book):
    """AI-written child-facing fields; children's verbatim quotes are excluded."""
    for path, value in strings(book):
        if path in ("title", "guide.catchphrase", "child_page.prompt") or re.fullmatch(
                r"chapters\[\d+\]\.(?:follow_up\.question|pages\[\d+\]\.(?:narration(?:_en)?|visual\.description))", path):
            yield path, value


def word_count(value):
    return len(WORD.findall(value))


def child_path(path, key):
    return f"{path}.{key}" if path else str(key)


def strings(value, path=""):
    if isinstance(value, str):
        yield path or "$", value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from strings(item, child_path(path, key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from strings(item, f"{path}[{index}]")


def blocklist(name):
    return [line.strip() for line in (ASSETS / name).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def json_equal(left, right):
    # JSON booleans must not compare equal to Python's integer 0/1.
    return type(left) is type(right) and left == right


def validate_schema(value, schema, path, errors):
    def error(message, at=None):
        errors.append({"path": at if at is not None else path or "$", "message": message})

    types = {
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "string": lambda v: isinstance(v, str),
        "null": lambda v: v is None,
        "boolean": lambda v: isinstance(v, bool),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    }
    expected = schema.get("type")
    if expected is not None:
        allowed = expected if isinstance(expected, list) else [expected]
        if not any(types[kind](value) for kind in allowed):
            error("类型错误，应为 " + " / ".join(allowed))
            return
    if "enum" in schema and not any(json_equal(value, option) for option in schema["enum"]):
        error("值必须是以下之一：" + json.dumps(schema["enum"], ensure_ascii=False))
    if "const" in schema and not json_equal(value, schema["const"]):
        error("值必须为 " + json.dumps(schema["const"], ensure_ascii=False))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            error(f"数值至少为 {schema['minimum']}，实际 {value}")
        if "maximum" in schema and value > schema["maximum"]:
            error(f"数值最多为 {schema['maximum']}，实际 {value}")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                error("缺少必填字段", child_path(path, key))
        properties = schema.get("properties", {})
        for key, item in value.items():
            at = child_path(path, key)
            if key in properties:
                validate_schema(item, properties[key], at, errors)
            elif schema.get("additionalProperties") is False:
                error("不允许额外字段", at)
    elif isinstance(value, list):
        for keyword, comparison, label in (("minItems", len(value) < schema.get("minItems", 0), "至少"),
                                            ("maxItems", len(value) > schema.get("maxItems", len(value)), "最多")):
            if comparison:
                error(f"数组{label}需要 {schema[keyword]} 项，实际 {len(value)} 项")
        if "items" in schema:
            for index, item in enumerate(value):
                validate_schema(item, schema["items"], f"{path}[{index}]", errors)
    elif isinstance(value, str):
        if schema.get("minLength", 0) > 0 and not value.strip():
            error("字符串去掉空白后不能为空")
        if len(value) < schema.get("minLength", 0):
            error(f"字符串至少 {schema['minLength']} 个字符")
        if len(value) > schema.get("maxLength", len(value)):
            error(f"字符串最多 {schema['maxLength']} 个字符，实际 {len(value)} 个")


def validate_book(book, book_path):
    """Return {ok, errors, stats}; book_path determines relative image locations."""
    schema = json.loads((ASSETS / "book.schema.json").read_text(encoding="utf-8"))
    errors = []
    validate_schema(book, schema, "", errors)

    def error(path, message):
        errors.append({"path": path, "message": message})

    # Malformed objects still receive schema errors without crashing x-rule checks.
    obj = book if isinstance(book, dict) else {}
    chapters = obj.get("chapters", [])
    chapters = chapters if isinstance(chapters, list) else []
    pages = []
    for ci, chapter in enumerate(chapters):
        if not isinstance(chapter, dict) or not isinstance(chapter.get("pages"), list):
            continue
        for pi, page in enumerate(chapter["pages"]):
            pages.append((f"chapters[{ci}].pages[{pi}]", page))
    mode = obj.get("mode")
    age_band = obj.get("age_band", "large")
    # Invalid age_band values are reported by the schema, without crashing here.
    if not isinstance(age_band, str) or age_band not in AGE_BAND_LIMITS:
        age_band = "large"
    minimum, maximum, narration_limit = AGE_BAND_LIMITS[age_band]
    if mode in ("new", "no_question"):
        if len(chapters) != 3:
            error("chapters", f"mode={mode} 必须正好 3 章，实际 {len(chapters)} 章")
        for index, role in enumerate(("discover", "structure", "magic")):
            if index < len(chapters) and isinstance(chapters[index], dict) and chapters[index].get("role") != role:
                error(f"chapters[{index}].role", f"第 {index + 1} 章的 role 必须为 {role}")
    if mode in ("new", "no_question", "follow_up"):
        minimum = 2 if mode == "follow_up" else minimum
        if not minimum <= len(pages) <= maximum:
            error("chapters", f"mode={mode}、age_band={age_band} 全书正文必须 {minimum}–{maximum} 页，实际 {len(pages)} 页")
    if mode == "follow_up":
        if not 1 <= len(chapters) <= 3:
            error("chapters", "追问模式必须有 1–3 章")
        previous = obj.get("continues_from")
        if not isinstance(previous, str) or not previous.strip():
            error("continues_from", "mode=follow_up 时必须填写非空的上一本书名或文件夹名")
    guide = obj.get("guide")
    anchor = guide.get("image_anchor") if isinstance(guide, dict) else None
    if isinstance(anchor, str):
        count = len(ENGLISH_WORD.findall(anchor))
        if not 15 <= count <= 30:
            error("guide.image_anchor", f"角色锚句必须为 15–30 个英文单词，实际 {count} 词")
    protagonist = obj.get("protagonist")
    if isinstance(protagonist, dict) and isinstance(protagonist.get("image_anchor"), str):
        count = len(ENGLISH_WORD.findall(protagonist["image_anchor"]))
        if not 15 <= count <= 30:
            error("protagonist.image_anchor", f"角色锚句必须为 15–30 个英文单词，实际 {count} 词")
    companions = blocklist("companion_blocklist.txt")
    for path, value in child_facing_strings(book):
        for phrase in companions:
            if phrase.casefold() in value.casefold():
                error(path, f"儿童文案含禁用陪伴话术「{phrase}」")
    for path, page in pages:
        if not isinstance(page, dict):
            continue
        narration = page.get("narration")
        if isinstance(narration, str):
            if obj.get("language") in ("zh", "bilingual"):
                length = len(re.sub(r"\s", "", narration))
                if length > narration_limit:
                    error(path + ".narration", f"age_band={age_band} 中文旁白去掉空白后不得超过 {narration_limit} 个字符，实际 {length} 个")
            elif obj.get("language") == "en" and word_count(narration) > 40:
                error(path + ".narration", f"英文旁白不得超过 40 词，实际 {word_count(narration)} 词")
        english = page.get("narration_en")
        if obj.get("language") == "bilingual" and (not isinstance(english, str) or not english.strip()):
            error(path + ".narration_en", "language=bilingual 时每页必须填写非空英文旁白")
        if isinstance(english, str) and word_count(english) > 40:
            error(path + ".narration_en", f"英文旁白不得超过 40 词，实际 {word_count(english)} 词")
        visual = page.get("visual")
        if not isinstance(visual, dict):
            continue
        prompt = visual.get("image_prompt")
        if isinstance(prompt, str):
            count = word_count(prompt)
            if not 30 <= count <= 80:
                error(path + ".visual.image_prompt", f"生图指令必须为 30–80 个英文单词，实际 {count} 词")
            if isinstance(anchor, str) and anchor not in prompt:
                error(path + ".visual.image_prompt", "必须原样包含 guide.image_anchor")
        filename = visual.get("image")
        if isinstance(filename, str) and filename:
            try:
                resolve_book_image(filename, book_path)
            except ValueError as exc:
                error(path + ".visual.image", str(exc))
    for name, character in (("guide", guide), ("protagonist", protagonist)):
        filename = character.get("reference_image") if isinstance(character, dict) else None
        if isinstance(filename, str) and filename:
            try:
                resolve_book_image(filename, book_path)
            except ValueError as exc:
                error(name + ".reference_image", str(exc))
    ips = blocklist("ip_blocklist.txt")
    for path, value in strings(book):
        for term in ips:
            if term.casefold() in value.casefold():
                error(path, f"含禁用 IP 词「{term}」")
    parent = obj.get("parent_card")
    co_reading = parent.get("co_reading") if isinstance(parent, dict) else None
    pauses = co_reading.get("pauses") if isinstance(co_reading, dict) else None
    if isinstance(pauses, list):
        for index, pause in enumerate(pauses):
            page_number = pause.get("page") if isinstance(pause, dict) else None
            if isinstance(page_number, int) and not isinstance(page_number, bool) and page_number > len(pages):
                error(f"parent_card.co_reading.pauses[{index}].page",
                      f"共读页码不能超过全书正文 {len(pages)} 页，实际 {page_number}")
    sensitive = parent.get("sensitive") if isinstance(parent, dict) else None
    if isinstance(sensitive, dict) and sensitive.get("level") == "parent_first" and not sensitive.get("topics"):
        error("parent_card.sensitive.topics", "parent_first 时敏感话题 topics 不能为空")
    stats = {"chapters": len(chapters), "pages": len(pages),
             "pages_by_chapter": [len(c["pages"]) if isinstance(c, dict) and isinstance(c.get("pages"), list) else 0
                                  for c in chapters]}
    return {"ok": not errors, "errors": errors, "stats": stats}


def load_book(book_path):
    def reject_constant(value):
        raise ValueError(f"JSON 不允许数值 {value}")

    try:
        return json.loads(Path(book_path).read_text(encoding="utf-8-sig"), parse_constant=reject_constant), None
    except (OSError, ValueError) as exc:
        return None, {"ok": False, "errors": [{"path": "$", "message": f"无法读取 JSON：{exc}"}], "stats": {}}


def print_result(result, as_json=False):
    if as_json:
        print(json.dumps(result, ensure_ascii=False))
    elif result["ok"]:
        stats = result["stats"]
        print(f"通过 · {stats['chapters']} 章 · {stats['pages']} 页 · 各章页数 {stats['pages_by_chapter']}")
    else:
        for error in result["errors"]:
            print(f"{error['path']}：{error['message']}")


def main():
    parser = argparse.ArgumentParser(description="校验绘本 JSON")
    parser.add_argument("book", type=Path)
    parser.add_argument("--json", action="store_true", help="输出机器可读结果")
    args = parser.parse_args()
    book, result = load_book(args.book)
    if result is None:
        try:
            result = validate_book(book, args.book)
        except (OSError, ValueError) as exc:
            result = {"ok": False, "errors": [{"path": "$", "message": f"无法读取校验资源：{exc}"}], "stats": {}}
    print_result(result, args.json)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
