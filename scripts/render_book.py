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

from validate_book import load_book, print_result, resolve_book_image, validate_book

ASSETS = Path(__file__).resolve().parent.parent / "assets"
TOPICS = {"death": "死亡", "body": "身体", "fear": "恐惧", "religion": "宗教",
          "family_change": "家庭变化", "disaster": "灾难", "other": "其他"}
AGE_BAND_LABELS = {"small": "小班 3–4 岁", "middle": "中班 4–5 岁", "large": "大班 5–6 岁"}


def esc(value):
    return html.escape(str(value), quote=True)


def inline_image(filename, book_path):
    path = resolve_book_image(filename, book_path)
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
    # Browser SVG image mode disables scripts and external resources. Keep the
    # original XML bytes so XLink namespaces and local references remain intact;
    # never insert untrusted SVG elements into the HTML document's DOM.
    return f'<img alt="画面" src="data:image/svg+xml;base64,{base64.b64encode(data).decode("ascii")}">'


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
    co_reading = ''
    if "co_reading" in parent:
        reading = parent["co_reading"]
        pauses = ''.join(f'<li>第 {pause["page"]} 页：问{esc(pause["ask"])}</li>' for pause in reading["pauses"])
        co_reading = f'<h3>怎么一起读</h3><ul>{pauses}</ul>' + (list_html(reading["tips"]) if reading["tips"] else '')
    return f'''<details class="parent-card" {'open' if opened else ''}>
<summary>家长卡（给大人看）</summary>
<p class="ai-notice">这本书由 AI 生成，家长看过才算数。</p>
{co_reading}
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
    age_note = (f'<p class="age-band">{AGE_BAND_LABELS[book["age_band"]]}</p>'
                if "age_band" in book else '')
    pages = [f'''<section class="page cover" aria-label="封面">
<p class="eyebrow">从一个问题，走进一个世界</p><div class="cover-mark" aria-hidden="true">?</div>
<h1>{esc(book['title'])}</h1><p class="question">{question_prefix}{esc(book['question']['original'])}</p>{question_note}{age_note}
<div class="guide"><p>这次的向导 · <strong>{esc(guide['name'])}</strong></p><p>「{esc(guide['catchphrase'])}」</p></div>
<p class="hint">和爸爸妈妈一起，翻开下一页吧。</p></section>''']
    if pending:
        pages.append('<section class="page" aria-label="家长预览"><p class="eyebrow">先给大人看</p>'
                     + parent_card(book, opened=True) + '</section>')
    narrations = {}
    pauses_by_page = {}
    for pause in book["parent_card"].get("co_reading", {}).get("pauses", []):
        pauses_by_page.setdefault(pause["page"], []).append(pause["ask"])
    art_index = 0
    for chapter in book["chapters"]:
        for page in chapter["pages"]:
            art_index += 1
            visual = page["visual"]
            illustration = (inline_image(visual["image"], book_path) if visual.get("image")
                            else f'<div class="placeholder"><span>画面想象</span><p>{esc(visual["description"])}</p></div>')
            number = len(pages)
            narrations[str(number)] = [{"text": page["narration"], "lang": "en-US" if book["language"] == "en" else "zh-CN"}]
            english = ''
            if book["language"] == "bilingual" and page.get("narration_en"):
                english = f'<p class="narration english" lang="en">{esc(page["narration_en"])}</p>'
                narrations[str(number)].append({"text": page["narration_en"], "lang": "en-US"})
            parent_hint = ''.join(f'<p class="co-reading-hint">家长可以停下来问：{esc(ask)}</p>'
                                  for ask in pauses_by_page.get(art_index, []))
            pages.append(f'''<section class="page story" aria-label="正文第 {art_index} 页">
<p class="eyebrow">{esc(chapter['name'])}</p><div class="picture">{illustration}</div>
<p class="narration">{esc(page['narration'])}</p>{english}{parent_hint}
<button class="read-button" type="button" data-read="{number}">读给我听</button><p class="speech-status" role="status"></p></section>''')
    follow_buttons = ''.join(
        f'<button class="follow-button" type="button" data-follow="{ci}" aria-pressed="false">'
        f'{esc(chapter["follow_up"]["question"])}</button>'
        for ci, chapter in enumerate(book["chapters"]))
    reaction_options = [('loved', '喜欢'), ('ok', '一般'), ('bored', '没兴趣'), ('scared', '害怕了'), ('confused', '没听懂')]
    radios = ''.join(f'<label><input type="radio" name="reaction" value="{value}">{label}</label>' for value, label in reaction_options)
    pages.append(f'''<section class="page child-page" aria-label="读完啦">
<p class="eyebrow">读完啦</p><h2>{esc(book['child_page']['prompt'])}</h2>
<label class="field-label" for="child-words">孩子自己说的话，家长帮忙写下来，原话照录</label>
<textarea id="child-words" rows="4" placeholder="孩子自己说的话，家长帮忙写下来，原话照录">{esc(book['child_page']['child_words'])}</textarea>
<div class="follow-prompts" role="group" aria-labelledby="follow-prompts-label">
<p id="follow-prompts-label">说不出来的话，看看这些？</p><div class="follow-buttons">{follow_buttons}</div></div>
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
