# T-CODEX-fix4 · 年龄分档、共读卡、AI 声明（按儿童发展调研 + 作者定位）

背景：调研报告 ../07_儿童发展调研_缺口清单.md（仓库外，可读）。禁止项同 T-CODEX.md 第 5 节。
Claude Code 已改好 assets/book.schema.json（新增 `age_band`、`parent_card.co_reading`、x-rules 里的 `age_band_limits`、`co_reading_pages`，改了 `narration_length`）。**schema 不许再改**。你只改 scripts/ 和 assets/book_template.html。

## 要做
1. validate_book.py 按 x-rules 实现：
   - `age_band_limits`：按档校验正文页数和中文旁白长度（不填 age_band 按 large；small 3–4 页 ≤30 字；middle 4–6 页 ≤45 字；large 4–8 页 ≤60 字；follow_up 页数下限 2）。原来写死的「4–8 页」「60 字」改成按档
   - `co_reading_pages`：pauses[].page 不超过正文页数
   - co_reading 是可选字段（旧书没有），但有就要合格
2. render_book.py / 模板：
   - 家长卡**最上面**固定一行：「这本书由 AI 生成，家长看过才算数。」（不来自 JSON，所有书都有）
   - 家长卡里新增一节「怎么一起读」：列出 pauses（「第 N 页：问……」）和 tips；没有 co_reading 就不显示这一节
   - 正文页上，如果这一页在 pauses 里，旁白下方显示一个**很小、浅色**的家长提示：「家长可以停下来问：……」（字号明显小于旁白，不抢画面，不加按钮，不朗读）
   - 封面上如果有 age_band，小字显示「小班 3–4 岁 / 中班 4–5 岁 / 大班 5–6 岁」
3. 测试：现有 6 本书（assets/sample_book.json、examples/*/book.json）全部仍通过并能渲染；为 age_band 三档、co_reading 越界各加测试
4. 布局要求沿用 fix1：1280×800 下正文页不滚动能看全（加了家长提示的那页也要）
5. 结果追加到 tasks/out-T-CODEX.md 末尾「fix4」一节
