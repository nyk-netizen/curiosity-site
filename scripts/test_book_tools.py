#!/usr/bin/env python3
"""Stdlib regression checks, including section 4's six invalid copies."""

import base64
import copy
import json
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
import unittest

from render_book import render_book
from validate_book import validate_book, validate_schema

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "assets/sample_book.json"


class BookToolsTests(unittest.TestCase):
    def setUp(self):
        self.book = json.loads(SAMPLE.read_text(encoding="utf-8"))
        # Boundary tests construct their own page counts and optional features.
        # The real sample (including these fields) is covered by CLI tests.
        self.book.pop("age_band", None)
        self.book["parent_card"].pop("co_reading", None)
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
        for age_band in ([], {}, None, 1, "unknown"):
            self.book["age_band"] = age_band
            self.assertIn("age_band", [e["path"] for e in validate_book(self.book, self.input)["errors"]])
        self.input.write_text('{"title": NaN}', encoding="utf-8")
        result = self.run_cli("validate_book.py", self.input, "--json")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["errors"][0]["path"], "$")

    def test_render_and_approval_gate(self):
        output = self.directory / "sample.html"
        result = self.run_cli("render_book.py", SAMPLE, output)
        self.assertEqual(result.returncode, 0, result.stderr)
        document = output.read_text(encoding="utf-8")
        self.assertIn('1 / 9', document)
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
        self.assertIn('1 / 10', document)

    def test_ending_combines_child_words_and_chapter_prompts(self):
        self.book["child_page"]["child_words"] = ' 孩子的原话\n还想看 <云> & 闪电 '
        self.book["chapters"][0]["follow_up"]["question"] = '云里有 <冰> & 水吗？'
        for status in ("approved", "pending", "changes_requested"):
            with self.subTest(status=status):
                self.book["parent_card"]["approval"]["status"] = status
                document = render_book(self.book, self.input)
                sections = document.split('<section ')[1:]
                expected = 9 if status == "approved" else 10
                self.assertEqual(len(sections), expected)
                self.assertIn(f'1 / {expected}', document)
                self.assertNotIn('class="page follow-up"', document)
                ending = sections[-1].split('</section>')[0]
                self.assertIn('aria-label="读完啦"', ending)
                self.assertIn(' 孩子的原话\n还想看 &lt;云&gt; &amp; 闪电 </textarea>', ending)
                self.assertIn('云里有 &lt;冰&gt; &amp; 水吗？</button>', ending)
                self.assertEqual(ending.count('data-follow='), 3)
                self.assertLess(ending.index('id="child-words"'), ending.index('class="follow-prompts"'))
                self.assertLess(ending.index('class="follow-prompts"'), ending.index('<fieldset>'))
                self.assertNotIn('data-read=', ending)
                story_start = 1 if status == "approved" else 2
                for index, section in enumerate(sections[story_start:-1], story_start):
                    self.assertIn('class="page story"', section)
                    self.assertIn(f'data-read="{index}"', section)
                    self.assertNotIn('data-follow=', section)
                self.assertEqual(document.count('<details class="parent-card"'), 1)
                if status == "approved":
                    self.assertIn('<details class="parent-card" >', ending)
                else:
                    self.assertIn('<details class="parent-card" open>', sections[1])
                    self.assertNotIn('<details', ending)

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
        self.assertNotIn('<svg ', document)
        self.assertIn('data:image/svg+xml;base64,' + base64.b64encode(svg.encode()).decode(), document)
        self.assertIn('data:image/png;base64,', document)
        self.assertIn('data:image/jpeg;base64,', document)
        self.assertNotIn('<script>alert', document)
        self.assertNotIn('<img alt="画面" src="images/', document)

    def test_svg_xss_isolated_as_image_and_xlink_preserved(self):
        # Reproduce the uppercase SCRIPT / lowercase foreignobject bypasses.
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 300 200">
<SCRIPT>alert(1)</SCRIPT><foreignobject><div onclick="alert(2)">bad</div></foreignobject>
<rect oNLoAd="alert(3)"/><image href="https://example.com/external.png"/>
<defs><rect id="guide" width="20" height="20"/></defs><use xlink:href="#guide"/></svg>'''
        (self.directory / "art.svg").write_text(svg, encoding="utf-8")
        self.book["chapters"][0]["pages"][0]["visual"]["image"] = "art.svg"
        self.write()
        output = self.directory / "safe.html"
        result = self.run_cli("render_book.py", self.input, output)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        class Tags(HTMLParser):
            def __init__(self):
                super().__init__()
                self.tags = []

            def handle_starttag(self, tag, attrs):
                self.tags.append((tag, dict(attrs)))

        parser = Tags()
        parser.feed(output.read_text(encoding="utf-8"))
        self.assertFalse(any(tag in ("svg", "foreignobject", "use", "rect") for tag, _ in parser.tags))
        self.assertEqual(sum(tag == "script" for tag, _ in parser.tags), 2)  # Trusted template only.
        self.assertFalse(any(key.lower().startswith("on") for _, attrs in parser.tags for key in attrs))
        images = [attrs["src"] for tag, attrs in parser.tags if tag == "img"]
        self.assertEqual(len(images), 1)
        self.assertTrue(images[0].startswith("data:image/svg+xml;base64,"))
        self.assertEqual(base64.b64decode(images[0].split(",", 1)[1]).decode(), svg)
        self.assertIn('xlink:href="#guide"', svg)  # No ns1 rewrite or cross-page ID collisions.

    def test_image_paths_cannot_leave_book_directory(self):
        outside = self.directory / "outside.svg"
        outside.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 3 2"/>')
        book_directory = self.directory / "book"
        book_directory.mkdir()
        self.input = book_directory / "book.json"
        (book_directory / "linked.svg").symlink_to(outside)
        (book_directory / "linked-dir").symlink_to(self.directory, target_is_directory=True)
        (book_directory / "images").mkdir()
        cases = [str(outside), "../outside.svg", "images/../../outside.svg",
                 "../book/../outside.svg", "linked.svg", "linked-dir/outside.svg",
                 "C:\\private\\outside.svg", "\\\\server\\share\\outside.svg"]
        output = self.directory / "rejected.html"
        for filename in cases:
            with self.subTest(filename=filename):
                self.book["chapters"][0]["pages"][0]["visual"]["image"] = filename
                self.write()
                result = self.run_cli("validate_book.py", self.input, "--json")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("chapters[0].pages[0].visual.image",
                              [e["path"] for e in json.loads(result.stdout)["errors"]])
                result = self.run_cli("render_book.py", self.input, output)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertFalse(output.exists())
                # Direct render must independently enforce confinement, too.
                with self.assertRaises(ValueError):
                    render_book(self.book, self.input)
        (book_directory / "local.svg").write_bytes(outside.read_bytes())
        (book_directory / "local-link.svg").symlink_to(book_directory / "local.svg")
        for filename in ("local.svg", "local-link.svg", "images/../local.svg"):
            self.book["chapters"][0]["pages"][0]["visual"]["image"] = filename
            self.assertTrue(validate_book(self.book, self.input)["ok"])
            self.assertIn("data:image/svg+xml;base64,", render_book(self.book, self.input))
        self.book["guide"]["reference_image"] = "linked.svg"
        self.assertIn("guide.reference_image", [e["path"] for e in validate_book(self.book, self.input)["errors"]])

    def test_companion_phrases_in_all_child_facing_ai_fields(self):
        fields = [("title", self.book, "title"),
                  ("guide.catchphrase", self.book["guide"], "catchphrase"),
                  ("child_page.prompt", self.book["child_page"], "prompt"),
                  ("chapters[0].follow_up.question", self.book["chapters"][0]["follow_up"], "question"),
                  ("chapters[0].pages[0].narration", self.book["chapters"][0]["pages"][0], "narration"),
                  ("chapters[0].pages[0].narration_en", self.book["chapters"][0]["pages"][0], "narration_en"),
                  ("chapters[0].pages[0].visual.description", self.book["chapters"][0]["pages"][0]["visual"], "description")]
        for path, container, key in fields:
            for phrase in ("别告诉爸爸妈妈", "I AM YOUR BEST FRIEND"):
                with self.subTest(path=path, phrase=phrase):
                    previous = container.get(key)
                    container[key] = phrase
                    errors = validate_book(self.book, self.input)["errors"]
                    self.assertTrue(any(e["path"] == path and "陪伴话术" in e["message"] for e in errors), errors)
                    if previous is None:
                        container.pop(key)
                    else:
                        container[key] = previous
        self.book["question"]["original"] = "别告诉爸爸妈妈"
        self.book["child_page"]["child_words"] = "I am your best friend"
        self.book["parent_card"]["hard_notes"][0] = "不要写「我永远陪着你」"
        self.assertTrue(validate_book(self.book, self.input)["ok"])

    def test_required_strings_not_blank_and_anchor_word_limits(self):
        fields = [("title", self.book, "title"),
                  ("guide.image_anchor", self.book["guide"], "image_anchor"),
                  ("guide.catchphrase", self.book["guide"], "catchphrase"),
                  ("question.original", self.book["question"], "original"),
                  ("question.age", self.book["question"], "age"),
                  ("chapters[0].name", self.book["chapters"][0], "name"),
                  ("chapters[0].pages[0].narration", self.book["chapters"][0]["pages"][0], "narration"),
                  ("chapters[0].pages[0].visual.description", self.book["chapters"][0]["pages"][0]["visual"], "description"),
                  ("chapters[0].pages[0].visual.image_prompt", self.book["chapters"][0]["pages"][0]["visual"], "image_prompt"),
                  ("chapters[0].follow_up.question", self.book["chapters"][0]["follow_up"], "question"),
                  ("child_page.prompt", self.book["child_page"], "prompt"),
                  ("parent_card.sources[0].title", self.book["parent_card"]["sources"][0], "title"),
                  ("parent_card.sources[0].where", self.book["parent_card"]["sources"][0], "where"),
                  ("parent_card.hard_notes[0]", self.book["parent_card"]["hard_notes"], 0),
                  ("guide.colors[0]", self.book["guide"]["colors"], 0),
                  ("parent_card.sensitive.how_handled", self.book["parent_card"]["sensitive"], "how_handled"),
                  ("parent_card.weekend_project", self.book["parent_card"], "weekend_project")]
        for path, container, key in fields:
            for blank in ("", " \t\n\u3000"):
                with self.subTest(path=path, blank=blank):
                    previous = container[key]
                    container[key] = blank
                    errors = validate_book(self.book, self.input)["errors"]
                    self.assertTrue(any(e["path"] == path and "不能为空" in e["message"] for e in errors), errors)
                    container[key] = previous
        for count in (0, 14, 15, 30, 31):
            with self.subTest(anchor_words=count):
                anchor = " ".join(["word"] * count)
                self.book["guide"]["image_anchor"] = anchor
                for chapter in self.book["chapters"]:
                    for page in chapter["pages"]:
                        page["visual"]["image_prompt"] = anchor + " " + "detail " * 30
                errors = validate_book(self.book, self.input)["errors"]
                self.assertEqual(any(e["path"] == "guide.image_anchor" for e in errors), count not in (15, 30))
        self.book["guide"]["image_anchor"] = "123 " * 15
        self.assertIn("guide.image_anchor", [e["path"] for e in validate_book(self.book, self.input)["errors"]])

    def test_bilingual_requires_nonempty_english_on_every_page(self):
        self.book["language"] = "bilingual"
        all_pages = [(f"chapters[{ci}].pages[{pi}].narration_en", page)
                     for ci, chapter in enumerate(self.book["chapters"])
                     for pi, page in enumerate(chapter["pages"])]
        errors = validate_book(self.book, self.input)["errors"]
        self.assertEqual({e["path"] for e in errors}, {path for path, _ in all_pages})
        for _, page in all_pages:
            page["narration_en"] = "Let's discover how thunder works."
        self.assertTrue(validate_book(self.book, self.input)["ok"])
        self.write()
        complete = self.directory / "bilingual.html"
        result = self.run_cli("render_book.py", self.input, complete)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(complete.read_text(encoding="utf-8").count('class="narration english"'), len(all_pages))
        for path, page in all_pages:
            for invalid in (None, "", " \t\n\u3000"):
                with self.subTest(path=path, invalid=invalid):
                    page["narration_en"] = invalid
                    errors = validate_book(self.book, self.input)["errors"]
                    self.assertTrue(any(e["path"] == path and "bilingual" in e["message"] for e in errors), errors)
                    page["narration_en"] = "Let's discover how thunder works."
        self.book["chapters"][2]["pages"][-1].pop("narration_en")
        self.write()
        output = self.directory / "missing-english.html"
        self.assertEqual(self.run_cli("render_book.py", self.input, output).returncode, 1)
        self.assertFalse(output.exists())
        self.book["language"] = "zh"
        self.assertTrue(validate_book(self.book, self.input)["ok"])

    def test_existing_books_validate_and_render(self):
        books = [SAMPLE, *sorted((ROOT / "examples").glob("*/book.json"))]
        self.assertGreaterEqual(len(books), 6)
        for index, book_path in enumerate(books):
            with self.subTest(book=str(book_path.relative_to(ROOT))):
                result = self.run_cli("validate_book.py", book_path, "--json")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                output = self.directory / f"existing-{index}.html"
                result = self.run_cli("render_book.py", book_path, output)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertTrue(output.is_file())
                self.assertIn('这本书由 AI 生成，家长看过才算数。', output.read_text(encoding="utf-8"))

    def age_book(self, band, count, length=1, mode="new", language="zh"):
        book = copy.deepcopy(self.book)
        book.update(age_band=band, mode=mode, language=language, continues_from="上一本")
        # Keep three valid chapters; follow-ups below use one or two as needed.
        chapters = book["chapters"][:min(3, count)]
        prototype = copy.deepcopy(chapters[0]["pages"][0])
        prototype.update(narration="字 \n" * length, narration_en="word " * 40)
        for index, chapter in enumerate(chapters):
            page_count = count // len(chapters) + (index < count % len(chapters))
            chapter["pages"] = [copy.deepcopy(prototype) for _ in range(page_count)]
        book["chapters"] = chapters
        return book

    def test_age_band_page_boundaries_by_mode(self):
        for band, lower, upper in (("small", 3, 4), ("middle", 4, 6), ("large", 4, 8)):
            for mode in ("new", "no_question", "follow_up"):
                minimum = 2 if mode == "follow_up" else lower
                for count in (minimum - 1, minimum, upper, upper + 1):
                    with self.subTest(band=band, mode=mode, count=count):
                        book = self.age_book(band, count, mode=mode)
                        errors = validate_book(book, self.input)["errors"]
                        valid = minimum <= count <= upper
                        self.assertEqual(not errors, valid, errors)
                        if not valid:
                            self.assertTrue(any(e["path"] == "chapters" and "全书正文" in e["message"] for e in errors))
        for count in (3, 4, 8, 9):
            book = self.age_book("large", count)
            book.pop("age_band")
            self.assertEqual(validate_book(book, self.input)["ok"], 4 <= count <= 8)

    def test_age_band_narration_boundaries_and_cover(self):
        for band, limit, label in (("small", 30, "小班 3–4 岁"),
                                   ("middle", 45, "中班 4–5 岁"), ("large", 60, "大班 5–6 岁")):
            for language in ("zh", "bilingual"):
                for length in (limit, limit + 1):
                    with self.subTest(band=band, language=language, length=length):
                        book = self.age_book(band, 4, length, language=language)
                        errors = validate_book(book, self.input)["errors"]
                        self.assertEqual(not errors, length == limit, errors)
                        if errors:
                            self.assertEqual(len(errors), 4)
                            self.assertTrue(all(e["path"].endswith(".narration") for e in errors))
                        else:
                            document = render_book(book, self.input)
                            self.assertIn(f'<p class="age-band">{label}</p>', document.split('</section>', 1)[0])
            book = self.age_book(band, 4, language="en")
            for chapter in book["chapters"]:
                for page in chapter["pages"]:
                    page["narration"] = "word " * 40
            self.assertTrue(validate_book(book, self.input)["ok"])
            book["chapters"][0]["pages"][0]["narration"] += "word"
            self.assertIn("chapters[0].pages[0].narration", [e["path"] for e in validate_book(book, self.input)["errors"]])
        self.assertNotIn('class="age-band"', render_book(self.book, self.input))

    def test_co_reading_schema_and_page_bounds(self):
        self.assertTrue(validate_book(self.book, self.input)["ok"])
        self.book["parent_card"]["co_reading"] = {"pauses": [{"page": 7, "ask": "你看见了什么？"}], "tips": []}
        self.assertTrue(validate_book(self.book, self.input)["ok"])
        for page in (0, -1, 8, True, 1.5, "1", None):
            with self.subTest(page=page):
                self.book["parent_card"]["co_reading"]["pauses"][0]["page"] = page
                errors = validate_book(self.book, self.input)["errors"]
                self.assertIn("parent_card.co_reading.pauses[0].page", [e["path"] for e in errors])
        self.book["parent_card"]["co_reading"]["pauses"][0]["page"] = 8
        self.write()
        output = self.directory / "out-of-range.html"
        self.assertEqual(self.run_cli("render_book.py", self.input, output).returncode, 1)
        self.assertFalse(output.exists())
        for value in (None, [], {}, {"pauses": [], "tips": []},
                      {"pauses": [{"page": 1, "ask": " \n"}], "tips": [""]},
                      {"pauses": [True, {"page": []}], "tips": "wrong"}):
            self.book["parent_card"]["co_reading"] = value
            self.assertFalse(validate_book(self.book, self.input)["ok"])

    def test_co_reading_render_numbering_escaping_and_speech(self):
        self.assertNotIn('怎么一起读', render_book(self.book, self.input))
        self.assertNotIn('class="co-reading-hint"', render_book(self.book, self.input))
        asks = [(1, '你看见了什么？'), (3, '猜猜 <云> & 水去哪了？'), (3, '还有什么？')]
        self.book["parent_card"]["co_reading"] = {
            "pauses": [{"page": page, "ask": ask} for page, ask in asks],
            "tips": ['孩子插嘴就停下来听。', '等一等 <回答> & 不纠正。']}
        self.assertTrue(validate_book(self.book, self.input)["ok"])
        for status in ("approved", "pending", "changes_requested"):
            with self.subTest(status=status):
                self.book["parent_card"]["approval"]["status"] = status
                document = render_book(self.book, self.input)
                parent = document.split('<summary>家长卡（给大人看）</summary>', 1)[1].split('</details>', 1)[0]
                self.assertTrue(parent.lstrip().startswith('<p class="ai-notice">这本书由 AI 生成，家长看过才算数。</p>'))
                self.assertIn('<h3>怎么一起读</h3>', parent)
                self.assertIn('第 3 页：问猜猜 &lt;云&gt; &amp; 水去哪了？', parent)
                self.assertIn('等一等 &lt;回答&gt; &amp; 不纠正。', parent)
                stories = [s.split('</section>', 1)[0] for s in document.split('class="page story"')[1:]]
                for index, story in enumerate(stories, 1):
                    self.assertEqual(story.count('class="co-reading-hint"'), sum(page == index for page, _ in asks))
                    if index in (1, 3):
                        self.assertLess(story.index('class="narration"'), story.index('class="co-reading-hint"'))
                        self.assertLess(story.index('class="co-reading-hint"'), story.index('class="read-button"'))
                    self.assertEqual(story.count('<button '), 1)
                payload = json.loads(document.split('<script id="book-data" type="application/json">', 1)[1].split('</script>', 1)[0])
                self.assertEqual([lines[0]["text"] for lines in payload["narrations"].values()],
                                 [p["narration"] for c in self.book["chapters"] for p in c["pages"]])
                self.assertFalse(any(ask in json.dumps(payload, ensure_ascii=False) for _, ask in asks))


if __name__ == "__main__":
    unittest.main(verbosity=2)
