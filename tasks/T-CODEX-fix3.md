# T-CODEX-fix3 · 追问卡挪到故事结束之后（作者定）

禁止项同 T-CODEX.md 第 5 节。只改 scripts/render_book.py、assets/book_template.html、scripts/test_*。不改 schema、不改任何 book.json。

## 为什么改
现在每章结尾插一整屏追问卡，打断故事；而且卡片用孩子口吻写的问题其实是 AI 猜的。孩子的好问题常常是读完之后才冒出来的。

## 改成这样
1. 正文页之间**不再插追问卡**。翻页顺序：封面 → 全部正文页 → 「读完啦」页 →（未放行时家长卡位置不变）→ 家长卡
2. 原来的「留给孩子的最后一页」和追问卡合并成一页「读完啦」：
   - 标题：`child_page.prompt`（例如「你还想知道什么？」）
   - **第一位**：大输入框，提示文字「孩子自己说的话，家长帮忙写下来，原话照录」；child_words 有内容就预先填上
   - **第二位**，小一号、视觉上退后：一行小字「说不出来的话，看看这些？」，下面列出每章的 follow_up.question 作为可点的提示按钮（点了变选中，记入 follow_ups_tapped，和原来一样）
   - 下面照旧：reaction 单选、parent_note、「保存这次的反馈」导出 feedback.json（字段不变）
3. 页码总数相应减少；键盘、滑动、朗读不变；「读完啦」页的提示按钮不需要「读给我听」
4. 封面、放行横幅、家长卡逻辑不变
5. 布局沿用 fix1 的要求：1280×800 等视口下「读完啦」页不滚动能看到输入框和提示按钮（反馈控件可以需要滚动）

## 验收
- 现有 5 本书（assets/sample_book.json、examples/*/book.json）全部能渲染
- 更新 scripts/test_book_interactions.js：点一个提示按钮后导出的 feedback.json 里有这条追问；输入框文字进入 child_words
- 结果追加到 tasks/out-T-CODEX.md 末尾「fix3」一节
