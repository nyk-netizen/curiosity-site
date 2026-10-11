# T-CODEX 交付说明

## 产出

- `scripts/validate_book.py`：标准库实现任务规定的 JSON Schema 子集，读取仓库 schema，逐条检查全部 10 条 `x-rules`；一次汇总中文错误及 JSON 路径，支持 `--json`、章数/页数统计和退出码 0/1。schema 与词表定位相对脚本，不依赖当前目录；图片相对书的 JSON 定位。
- `scripts/render_book.py` 与 `assets/book_template.html`：校验成功后生成单文件 HTML；CSS/JS 内联，PNG/JPG/JPEG 转 base64，SVG 直接内联。包含封面、正文、每章追问、孩子原话、家长反应及补充、反馈下载和家长卡；未放行时展示固定横幅，家长卡移到封面后并默认展开。支持左右按钮、键盘、手机滑动、中文/英文/双语朗读、localStorage。
- `assets/imagegen_notes.md`：中文 34 行，说明角色参考图、逐页带参考图、实际工具参数、保存路径、尺寸和时间的不确定性、省时方法及 OpenAI 服务隐私边界。本次没有生图。
- `scripts/test_book_tools.py`：10 项标准库回归测试，包含第 4 节六种错误变体。
- `scripts/test_book_interactions.js`：可选的 Node.js 标准库测试，在 DOM 替身中执行生成 HTML 的实际内联 JavaScript，检查交互及反馈数据逻辑。

## 怎么跑

```sh
python3 scripts/validate_book.py assets/sample_book.json
python3 scripts/validate_book.py assets/sample_book.json --json
python3 scripts/render_book.py assets/sample_book.json /tmp/sample.html
PYTHONDONTWRITEBYTECODE=1 python3 scripts/test_book_tools.py
node scripts/test_book_interactions.js /tmp/sample.html
```

前两个生产脚本只需要 Python 3 标准库（Python 3.9 或更新版本），不需要安装依赖。可选 JavaScript 测试需要 Node.js；它不参与生成或阅读绘本。

## 第 4 节自验结果

已先运行验收，再写本说明。此次实际结果：

| 验收项 | 结果与证据 |
| --- | --- |
| 样例校验命令 | 退出码 0；`通过 · 3 章 · 7 页 · 各章页数 [2, 3, 2]`。 |
| 删除 sources | 退出码 1，错误路径 `parent_card.sources`。 |
| 一页旁白改成 80 字 | 退出码 1，错误路径 `chapters[1].pages[0].narration`。 |
| 书名加入任务指定 IP 禁词 | 退出码 1，错误路径 `title`。 |
| 旁白加入任务指定陪伴话术 | 退出码 1，错误路径 `chapters[0].pages[0].narration`。 |
| mode 改为 follow_up，不填来源 | 退出码 1，错误路径 `continues_from`。 |
| 删除一章 | 退出码 1，错误路径 `chapters`。 |
| 样例渲染命令 | 退出码 0；生成 `/tmp/sample.html`。共 12 个翻页画面：封面 1 + 正文 7 + 追问卡 3 + 孩子页 1；已放行家长卡折叠放在孩子页末尾。 |
| pending 变体 | 退出码 0；生成 `/tmp/sample-pending.html`。HTML 检查确认放行横幅、敏感话题中文名、家长卡在封面后且有 `open` 属性。 |
| 375 / 768 / 1280 / 1920 截图及断网打开 | **未完成实际浏览器验收**：自动浏览器安全策略拒绝 `file:///tmp/sample.html`，只允许 http/https；未绕过限制，也未产生四种宽度截图。CSS 使用居中最大宽度 880px 的内容区、3:2 画面、正文最小 22px、正常文档流中的翻页按钮；这只是实现说明，不是截图验证。 |
| 点朗读有声音 | **未完成实际听音验收**。独立 JavaScript 测试确认点击后调用 speechSynthesis、没有加载时自动朗读、zh-CN/en-US、语速 0.9、双语顺序朗读。不能据此声称已听到声音。 |
| 追问按钮与 feedback.json | 独立 JavaScript 测试通过：追问已选状态、localStorage 写入/恢复、重复点击去重、导出文件名与全部字段、孩子原话保留、家长反应及备注；**真实浏览器点击和下载仍未实测**。 |

10 项 Python 测试全通过，退出码 0；可选 JavaScript 交互测试通过，退出码 0。额外检查了错误汇总、畸形数据不崩溃、跨工作目录、英文旁白上限、总页数及角色顺序、敏感话题、图片存在性、图片内嵌、文本转义、渲染失败不产生/覆盖 HTML、SVG 活动内容和外部引用拒绝。

## 已知限制与不确定项

- 无法在当前浏览器安全策略下完成本地文件截图、实际声音及浏览器下载验收；不能声称第 4 节全部通过。以上三个真实浏览器项目仍需在允许打开本地 HTML 的浏览器中验收。
- 离线朗读依赖浏览器 speechSynthesis 和系统已安装的相应语音。系统缺少语音或浏览器不支持时显示提示，不自动联网获取语音。
- 某些浏览器禁止 file:// 页面使用 localStorage；此时当前会话仍可选择追问、填写并导出反馈，但关闭后不能保证恢复。反馈日期使用本地日历日期。
- SVG 需要 viewBox 或可解析的数值宽高；为保持静态离线输出，拒绝脚本、外部引用、style 元素、foreignObject 与动画元素。一般静态图形、渐变、裁剪可用；图片 ID 会按页隔离。支持的图片格式为 PNG、JPG/JPEG、SVG。
- 英文词计数按 ASCII 字母/数字词段处理，词内部连字符和撇号视为同一个词；中文旁白按去掉空白后的字符数计算，标点也计入。
- 双语仅在 JSON 提供 narration_en 时显示并朗读英文；schema 没有要求 bilingual 必填 narration_en，校验器没有自行增加这个条件。
- 生图接口不提供独立 size/quality 参数；说明中的“每张几分钟、整本数十分钟”来自工具说明的预算，未实测，具体像素及耗时不能保证。
- 参考来源保持可点击；它们不参与页面加载，离线时点击外部来源本身仍需要网络。

## 范围

只新增/修改了 `scripts/`、可写的 `assets/` 产出及本说明。未修改 schema、样例、两个 blocklist、SKILL.md、references/、README.md；未读取 `_runs/`，未安装包，未 commit/push，未写任何 key、Codex 记忆或设置。验收用的临时 JSON/HTML 在 `/tmp/`，由样例复制生成。

以上范围描述本任务执行的写入。交付时 `git status` 也显示 SKILL.md、sample_book.json 等其他工作区变动；这些文件不在本任务写入范围，我没有修改或还原它们。
