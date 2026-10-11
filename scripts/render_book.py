#!/usr/bin/env python3
"""Render validated book data as one offline HTML file; Python stdlib only."""

import argparse
import base64
import hashlib
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

from validate_book import load_book, print_result, validate_book

ASSETS = Path(__file__).resolve().parent.parent / "assets"
TOPICS = {"death": "死亡", "body": "身体", "fear": "恐惧", "religion": "宗教",
          "family_change": "家庭变化", "disaster": "灾难", "other": "其他"}


def esc(value):
    return html.escape(str(value), quote=True)


def inline_image(filename, book_path, index):
    path = Path(book_path).resolve().parent / filename
    suffix = path.suffix.lower()
    data = path.read_bytes()
    if suffix in (".png", ".jpg", ".jpeg"):
        mime = "image/png" if suffix == ".png" else "image/jpeg"
        return f'<img alt="画面" src="data:{mime};base64,{base64.b64encode(data).decode("ascii")}">'
    if suffix != ".svg":
        raise ValueError(f"不支持的图片格式：{filename}；请用 PNG、JPG 或 SVG")
    root = ET.fromstring(data)
    if root.tag != "{http://www.w3.org/2000/svg}svg" and root.tag != "svg":
        raise ValueError(f"图片不是 SVG：{filename}")
    # Reject executable/external content so embedding cannot undo offline behavior.
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag in ("script", "foreignObject", "style", "animate", "animateMotion", "animateTransform", "set"):
            raise ValueError(f"SVG 含不支持的活动内容 {tag}：{filename}")
        for key, value in element.attrib.items():
            attribute = key.rsplit("}", 1)[-1].lower()
            if attribute.startswith("on") or (attribute in ("href", "src") and not value.startswith("#")):
                raise ValueError(f"SVG 含脚本或外部引用：{filename}")
            if re.search(r"url\(\s*['\"]?(?!#)[^\s'\"]", value, re.I) or "@import" in value.lower():
                raise ValueError(f"SVG 含外部样式引用：{filename}")
    # Isolate each illustration's ids (gradients, masks, and use references).
    ids = {element.attrib["id"]: f"art{index}-{element.attrib['id']}"
           for element in root.iter() if "id" in element.attrib}
    for element in root.iter():
        for key, value in list(element.attrib.items()):
            if key == "id":
                element.set(key, ids[value])
            else:
                if value.startswith("#") and value[1:] in ids:
                    value = "#" + ids[value[1:]]
                value = re.sub(r"url\(\s*(['\"]?)#([^)'\"\s]+)\1\s*\)",
                               lambda m: "url(#" + ids.get(m[2], m[2]) + ")", value)
                element.set(key, value)
    if "viewBox" not in root.attrib:
        width, height = root.get("width", ""), root.get("height", "")
        if re.fullmatch(r"\d+(?:\.\d+)?(?:px)?", width) and re.fullmatch(r"\d+(?:\.\d+)?(?:px)?", height):
            root.set("viewBox", f"0 0 {width.removesuffix('px')} {height.removesuffix('px')}")
        else:
            raise ValueError(f"SVG 需要 viewBox 或数值宽高，才能完整缩放：{filename}")
    root.set("preserveAspectRatio", "xMidYMid meet")
    root.set("role", "img")
    root.set("aria-label", "绘本画面")
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    return ET.tostring(root, encoding="unicode")


def list_html(items):
    return '<ul>' + ''.join(f'<li>{esc(item)}</li>' for item in items) + '</ul>' if items else '<p>无</p>'


def parent_card(book, opened=False):
    parent = book["parent_card"]
    sensitive = parent["sensitive"]
    sources = []
    for source in parent["sources"]:
        where = source["where"]
        parsed = urlsplit(where)
        location = (f'<a href="{esc(where)}" target="_blank" rel="noopener noreferrer">{esc(where)}</a>'
                    if parsed.scheme in ("http", "https") and parsed.netloc else esc(where))
        sources.append(f'<li><strong>{esc(source["title"])}</strong><br>{location}'
                       + (f'<p>用于：{esc(source["used_for"])}</p>' if source.get("used_for") else '') + '</li>')
    approval = parent["approval"]
    status = {"pending": "待家长放行", "approved": "家长已放行", "changes_requested": "家长要求修改"}[approval["status"]]
    level = {"none": "无", "notice": "提醒家长", "parent_first": "家长先看"}[sensitive["level"]]
    return f'''<details class="parent-card" {'open' if opened else ''}>
<summary>家长卡（给大人看）</summary>
<h3>核心原理 · hard_notes</h3>{list_html(parent['hard_notes'])}
<h3>参考来源 · sources</h3><ul>{''.join(sources)}</ul>
<h3>不确定与简化 · uncertain</h3>{list_html(parent['uncertain'])}
<h3>敏感提醒 · sensitive</h3><p>级别：{level}；涉及：{esc('、'.join(TOPICS[t] for t in sensitive['topics']) or '无')}</p>
<p>{esc(sensitive['how_handled'])}</p>
<h3>周末小实验 · weekend_project</h3><p>{esc(parent['weekend_project'])}</p>
<h3>家长放行 · approval</h3><p>{status}（{esc(approval['status'])}）</p>
<p>{esc(approval.get('note', ''))}</p><p>{esc(approval.get('date', ''))}</p>
</details>'''


def render_book(book, book_path):
    pending = book["parent_card"]["approval"]["status"] != "approved"
    sensitive = book["parent_card"]["sensitive"]
    banner = ''
    if pending:
        topics = ('<br>这本书涉及：' + esc('、'.join(TOPICS[t] for t in sensitive['topics']))
                  if sensitive['level'] == 'parent_first' else '')
        banner = f'<aside id="preview-banner" role="status">家长预览版 · 还没放行，先别给孩子看{topics}</aside>'
    guide = book["guide"]
    question_prefix = {"new": "你问：", "follow_up": "你接着问：",
                       "no_question": "今天我们来想一想："}[book["mode"]]
    question_note = ''
    if book["mode"] == "follow_up":
        question_note = f'<p class="question-note">接着《{esc(book["continues_from"])}》</p>'
    elif book["mode"] == "no_question":
        question_note = '<p class="question-note">今天没有问题，这一题是替你出的</p>'
    pages = [f'''<section class="page cover" aria-label="封面">
<p class="eyebrow">从一个问题，走进一个世界</p><div class="cover-mark" aria-hidden="true">?</div>
<h1>{esc(book['title'])}</h1><p class="question">{question_prefix}{esc(book['question']['original'])}</p>{question_note}
<div class="guide"><p>这次的向导 · <strong>{esc(guide['name'])}</strong></p><p>「{esc(guide['catchphrase'])}」</p></div>
<p class="hint">和爸爸妈妈一起，翻开下一页吧。</p></section>''']
    if pending:
        pages.append('<section class="page" aria-label="家长预览"><p class="eyebrow">先给大人看</p>'
                     + parent_card(book, opened=True) + '</section>')
    narrations = {}
    art_index = 0
    for ci, chapter in enumerate(book["chapters"]):
        for page in chapter["pages"]:
            art_index += 1
            visual = page["visual"]
            illustration = (inline_image(visual["image"], book_path, art_index) if visual.get("image")
                            else f'<div class="placeholder"><span>画面想象</span><p>{esc(visual["description"])}</p></div>')
            number = len(pages)
            narrations[str(number)] = [{"text": page["narration"], "lang": "en-US" if book["language"] == "en" else "zh-CN"}]
            english = ''
            if book["language"] == "bilingual" and page.get("narration_en"):
                english = f'<p class="narration english" lang="en">{esc(page["narration_en"])}</p>'
                narrations[str(number)].append({"text": page["narration_en"], "lang": "en-US"})
            pages.append(f'''<section class="page story" aria-label="正文第 {art_index} 页">
<p class="eyebrow">{esc(chapter['name'])}</p><div class="picture">{illustration}</div>
<p class="narration">{esc(page['narration'])}</p>{english}
<button class="read-button" type="button" data-read="{number}">读给我听</button><p class="speech-status" role="status"></p></section>''')
        follow = chapter["follow_up"]["question"]
        pages.append(f'''<section class="page follow-up" aria-label="追问口">
<p class="eyebrow">追问口 · {esc(chapter['name'])}</p><div class="follow-symbol" aria-hidden="true">?</div>
<h2>{esc(follow)}</h2><p>这个问题，也让你好奇吗？</p>
<button class="follow-button" type="button" data-follow="{ci}" aria-pressed="false">我也想知道这个！</button>
<p class="hint">把好奇心留在这里，下次再一起看看。</p></section>''')
    reaction_options = [('loved', '喜欢'), ('ok', '一般'), ('bored', '没兴趣'), ('scared', '害怕了'), ('confused', '没听懂')]
    radios = ''.join(f'<label><input type="radio" name="reaction" value="{value}">{label}</label>' for value, label in reaction_options)
    pages.append(f'''<section class="page child-page" aria-label="留给孩子的一页">
<p class="eyebrow">这一页，留给你</p><h2>{esc(book['child_page']['prompt'])}</h2>
<label class="field-label" for="child-words">孩子的原话（爸爸妈妈帮忙写）</label>
<textarea id="child-words" rows="5" placeholder="把孩子说的话，原样记在这里……">{esc(book['child_page']['child_words'])}</textarea>
<fieldset><legend>家长记录：孩子这次的反应</legend><div class="reactions">{radios}</div></fieldset>
<label class="field-label" for="parent-note">家长补充</label><textarea id="parent-note" rows="3"></textarea>
<button type="button" id="export-feedback">保存这次的反馈</button><p id="save-status" role="status"></p>
{parent_card(book) if not pending else ''}</section>''')
    content = ''.join(page if index == 0 else page.replace('<section ', '<section hidden ', 1)
                      for index, page in enumerate(pages))
    data = {"title": book["title"], "question": book["question"]["original"],
            "followUps": [chapter["follow_up"]["question"] for chapter in book["chapters"]],
            "narrations": narrations,
            "storageKey": "curiosity-book-" + hashlib.sha256(json.dumps(book, ensure_ascii=False, sort_keys=True).encode()).hexdigest()}
    payload = json.dumps(data, ensure_ascii=False).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    template = (ASSETS / "book_template.html").read_text(encoding="utf-8")
    replacements = {"TITLE": esc(book["title"]), "LANG": "en" if book["language"] == "en" else "zh-CN",
                    "BANNER": banner, "PAGES": content, "DATA": payload, "TOTAL": str(len(pages))}
    return re.sub(r"\{\{(TITLE|LANG|BANNER|PAGES|DATA|TOTAL)\}\}", lambda m: replacements[m[1]], template)


def main():
    parser = argparse.ArgumentParser(description="渲染为离线单文件 HTML 绘本")
    parser.add_argument("book", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    book, result = load_book(args.book)
    try:
        if result is None:
            result = validate_book(book, args.book)
        if not result["ok"]:
            print_result(result)
            return 1
        if args.output.resolve() == args.book.resolve():
            raise ValueError("输出 HTML 不能覆盖输入 JSON")
        document = render_book(book, args.book)
        args.output.write_text(document, encoding="utf-8")
    except (OSError, ValueError, ET.ParseError) as exc:
        print(f"渲染失败：{exc}", file=sys.stderr)
        return 1
    print(f"已生成：{args.output}（正文 {result['stats']['pages']} 页，单文件离线绘本）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
