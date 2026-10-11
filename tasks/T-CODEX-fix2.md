# T-CODEX-fix2 · 公开前审查发现的脚本问题

审查全文在 tasks/review-公开前审查.md。禁止项同 T-CODEX.md 第 5 节，只改 scripts/ 和 assets/book_template.html。
这次允许改 assets/book.schema.json 的**校验约束**（minLength 等），但不许增删字段或改字段名。

修这几条（编号对应审查报告）：
- 1（高）SVG 内联 XSS：改成白名单（只允许静态 SVG 元素和属性，标签和属性名大小写不敏感；去掉所有 on* 属性、script、foreignObject、外部 href），或者干脆把 SVG 用 <img src="data:image/svg+xml;base64,..."> 嵌入。选更稳的那个，交付说明里写理由
- 2（高）路径越界：validate 和 render 都拒绝绝对路径、../ 越出书目录、指向书目录外的符号链接（用 realpath 判断）
- 4 陪伴话术：检查所有面向孩子显示或朗读的、由 AI 写的字符串（narration、narration_en、guide.catchphrase、follow_up.question、child_page.prompt、title、visual.description）。question.original 和 child_page.child_words 是孩子原话，不查
- 5 必填字符串去空白后不能为空（title、narration、image_prompt、image_anchor、follow_up.question、sources[].title/where、hard_notes 每条等）；image_anchor 15–30 个英文单词
- 9 xlink:href 统一转成 href（如果第 1 条改成 <img> 嵌入，这条自然解决，说明一下即可）
- 10 language=bilingual 时每页 narration_en 必填非空
- 16 脚本里用了 3.9 才有的写法就在交付说明里写明最低 Python 版本

改完：现有 4 本书（assets/sample_book.json、examples/*/book.json）都要仍然通过校验并能渲染；为第 1、2、4、5、10 条各加一个能复现的测试到 scripts/test_book_tools.py。结果追加到 tasks/out-T-CODEX.md 末尾「fix2」一节。
