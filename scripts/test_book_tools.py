#!/usr/bin/env python3
"""Stdlib regression checks, including section 4's six invalid copies."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from render_book import render_book
from validate_book import validate_book, validate_schema

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "assets/sample_book.json"


class BookToolsTests(unittest.TestCase):
    def setUp(self):
        self.book = json.loads(SAMPLE.read_text(encoding="utf-8"))
        self.temp = tempfile.TemporaryDirectory(prefix="curiosity-tests-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.input = self.directory / "book.json"

    def write(self):
        self.input.write_text(json.dumps(self.book, ensure_ascii=False), encoding="utf-8")

    def run_cli(self, script, *args):
        return subprocess.run([sys.executable, str(ROOT / "scripts" / script), *map(str, args)],
                              cwd=self.directory, capture_output=True, text=True)

    def test_sample_and_different_cwd(self):
        result = self.run_cli("validate_book.py", SAMPLE)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("通过", result.stdout)
        result = self.run_cli("validate_book.py", "--json", SAMPLE)
        report = json.loads(result.stdout)
        self.assertEqual(report["stats"], {"chapters": 3, "pages": 7, "pages_by_chapter": [2, 3, 2]})
        self.assertTrue(report["ok"])
        self.assertEqual(report["errors"], [])

    def test_section_four_six_invalid_copies(self):
        original = copy.deepcopy(self.book)
        mutations = [
            ("删除 sources", lambda b: b["parent_card"].pop("sources"), "parent_card.sources"),
            ("80 字旁白", lambda b: b["chapters"][1]["pages"][0].update(narration="字" * 80), "chapters[1].pages[0].narration"),
            ("书名禁词", lambda b: b.update(title=b["title"] + "神奇校车"), "title"),
            ("陪伴话术", lambda b: b["chapters"][0]["pages"][0].update(narration="我永远陪着你"), "chapters[0].pages[0].narration"),
            ("追问无来源", lambda b: b.update(mode="follow_up"), "continues_from"),
            ("少一章", lambda b: b["chapters"].pop(), "chapters"),
        ]
        for name, mutate, expected in mutations:
            with self.subTest(name=name):
                self.book = copy.deepcopy(original)
                mutate(self.book)
                self.write()
                result = self.run_cli("validate_book.py", self.input, "--json")
                self.assertEqual(result.returncode, 1, result.stdout)
                report = json.loads(result.stdout)
                self.assertFalse(report["ok"])
                self.assertIn(expected, [error["path"] for error in report["errors"]])
                print(f"验收：{name} → {expected}（退出码 1）")

    def test_accumulates_all_errors(self):
        self.book["parent_card"].pop("sources")
        self.book["chapters"][0]["pages"][0]["narration"] = "字" * 80 + "我永远陪着你"
        self.book["title"] = "神奇校车"
        errors = validate_book(self.book, self.input)["errors"]
        self.assertGreaterEqual(len(errors), 4)

    def test_schema_subset(self):
        schema = {"type": "object", "required": ["missing"], "additionalProperties": False,
                  "properties": {"name": {"type": ["string", "null"], "minLength": 2, "maxLength": 3},
                                 "values": {"type": "array", "minItems": 2, "maxItems": 3,
                                            "items": {"enum": ["yes", "no"]}},
                                 "version": {"const": "1.0"}}}
        errors = []
        validate_schema({"name": "a", "values": ["wrong"], "version": 1, "extra": True}, schema, "", errors)
        self.assertEqual({e["path"] for e in errors}, {"missing", "name", "values", "values[0]", "version", "extra"})
        errors = []
        validate_schema({"missing": None}, {"type": "object", "properties": {"missing": {"type": ["string", "null"]}}}, "", errors)
        self.assertEqual(errors, [])
        for value, fragment in [("abcd", {"type": "string", "maxLength": 3}),
                                ([1, 2], {"type": "array", "maxItems": 1}),
                                (True, {"const": 1}), (1, {"type": "string"})]:
            errors = []
            validate_schema(value, fragment, "test", errors)
            self.assertTrue(errors)

    def test_all_other_x_rules(self):
        self.book["chapters"][0]["role"] = "magic"
        self.book["language"] = "bilingual"
        page = self.book["chapters"][2]["pages"][1]
        page["narration_en"] = "word " * 41
        page["visual"]["image_prompt"] = "too short"
        page["visual"]["image"] = "missing.png"
        self.book["parent_card"]["sensitive"].update(level="parent_first", topics=[])
        self.book["parent_card"]["hard_notes"][0] = "MAGIC SCHOOL BUS"
        paths = [e["path"] for e in validate_book(self.book, self.input)["errors"]]
        for expected in ("chapters[0].role", "chapters[2].pages[1].narration_en",
                         "chapters[2].pages[1].visual.image_prompt", "chapters[2].pages[1].visual.image",
                         "parent_card.sensitive.topics", "parent_card.hard_notes[0]"):
            self.assertIn(expected, paths)
        self.book = json.loads(SAMPLE.read_text(encoding="utf-8"))
        self.book["language"] = "en"
        self.book["chapters"][0]["pages"][0]["narration"] = "word " * 41
        self.assertIn("chapters[0].pages[0].narration", [e["path"] for e in validate_book(self.book, self.input)["errors"]])
        for mode in ("new", "no_question", "follow_up"):
            self.book = json.loads(SAMPLE.read_text(encoding="utf-8"))
            self.book.update(mode=mode, continues_from="previous")
            for chapter in self.book["chapters"]:
                chapter["pages"] = [copy.deepcopy(chapter["pages"][0])] * 3
            self.assertIn("chapters", [e["path"] for e in validate_book(self.book, self.input)["errors"]])

    def test_follow_up_and_boundaries(self):
        self.book.update(mode="follow_up", continues_from="previous")
        self.book["chapters"] = [self.book["chapters"][0]]
        self.book["chapters"][0]["pages"][0]["narration"] = "字 \n" * 60
        self.assertTrue(validate_book(self.book, self.input)["ok"])
        self.book["continues_from"] = " \n"
        self.assertIn("continues_from", [e["path"] for e in validate_book(self.book, self.input)["errors"]])
        self.book["continues_from"] = "previous"
        self.book["chapters"][0]["pages"] = self.book["chapters"][0]["pages"][:1]
        self.assertFalse(validate_book(self.book, self.input)["ok"])

    def test_bad_structures_do_not_crash(self):
        for value in (None, [], "book", {"chapters": [None, {"pages": [True, 1]}]}, {"chapters": "bad"}):
            self.assertFalse(validate_book(value, self.input)["ok"])
        self.input.write_text('{"title": NaN}', encoding="utf-8")
        result = self.run_cli("validate_book.py", self.input, "--json")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["errors"][0]["path"], "$")

    def test_render_and_approval_gate(self):
        output = self.directory / "sample.html"
        result = self.run_cli("render_book.py", SAMPLE, output)
        self.assertEqual(result.returncode, 0, result.stderr)
        document = output.read_text(encoding="utf-8")
        self.assertIn('1 / 12', document)
        self.assertNotIn('id="preview-banner"', document)
        self.assertIn('<details class="parent-card" >', document)
        self.assertNotIn('<script src=', document)
        self.assertNotIn('<link ', document)
        self.book["parent_card"]["approval"]["status"] = "pending"
        self.book["parent_card"]["sensitive"].update(level="parent_first", topics=["fear", "body"])
        self.write()
        result = self.run_cli("render_book.py", self.input, output)
        self.assertEqual(result.returncode, 0, result.stderr)
        document = output.read_text(encoding="utf-8")
        self.assertIn('家长预览版 · 还没放行，先别给孩子看', document)
        self.assertIn('这本书涉及：恐惧、身体', document)
        self.assertIn('<details class="parent-card" open>', document)
        self.assertLess(document.index('<details'), document.index('aria-label="正文第 1 页"'))

    def test_cover_question_modes(self):
        cases = [("new", "你问：", None),
                 ("follow_up", "你接着问：", "接着《上一本 &lt;云&gt;》"),
                 ("no_question", "今天我们来想一想：", "今天没有问题，这一题是替你出的")]
        for mode, prefix, note in cases:
            with self.subTest(mode=mode):
                self.book.update(mode=mode, continues_from="上一本 <云>" if mode == "follow_up" else None)
                self.write()
                output = self.directory / f"{mode}.html"
                result = self.run_cli("render_book.py", self.input, output)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                cover = output.read_text(encoding="utf-8").split('</section>', 1)[0]
                self.assertIn(f'<p class="question">{prefix}为什么会打雷？</p>', cover)
                if note:
                    self.assertIn(f'<p class="question-note">{note}</p>', cover)
                else:
                    self.assertNotIn('class="question-note"', cover)

    def test_invalid_render_writes_nothing(self):
        self.book["parent_card"].pop("sources")
        self.write()
        output = self.directory / "invalid.html"
        result = self.run_cli("render_book.py", self.input, output)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(output.exists())
        output.write_text("existing output", encoding="utf-8")
        result = self.run_cli("render_book.py", self.input, output)
        self.assertEqual(output.read_text(), "existing output")

    def test_embedded_images_and_escaping(self):
        (self.directory / "images").mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 200"><defs><linearGradient id="warm"><stop offset="0" stop-color="#fed"/></linearGradient></defs><rect width="300" height="200" fill="url(#warm)"/></svg>'
        (self.directory / "images/art.svg").write_text(svg, encoding="utf-8")
        (self.directory / "images/art.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        (self.directory / "images/art.jpg").write_bytes(b"\xff\xd8\xff")
        for index, suffix in enumerate(("svg", "png", "jpg")):
            self.book["chapters"][1]["pages"][index]["visual"]["image"] = f"images/art.{suffix}"
        self.book["child_page"]["child_words"] = '</textarea><script>alert("bad")</script>'
        self.book["question"]["original"] = '</script><script>alert("bad")</script>'
        self.assertTrue(validate_book(self.book, self.input)["ok"])
        document = render_book(self.book, self.input)
        self.assertIn('<svg ', document)
        self.assertIn('id="art3-warm"', document)
        self.assertIn('url(#art3-warm)', document)
        self.assertIn('data:image/png;base64,', document)
        self.assertIn('data:image/jpeg;base64,', document)
        self.assertNotIn('<script>alert', document)
        self.assertNotIn('<img alt="画面" src="images/', document)
        for dangerous in ('<script/>', '<image href="https://example.com/a.png"/>', '<rect onclick="alert(1)"/>'):
            (self.directory / "images/art.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 3 2">' + dangerous + '</svg>')
            with self.assertRaises(ValueError):
                render_book(self.book, self.input)


if __name__ == "__main__":
    unittest.main(verbosity=2)
