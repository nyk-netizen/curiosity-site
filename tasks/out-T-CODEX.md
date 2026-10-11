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

## fix1

### 修改

- `assets/book_template.html`：在宽度 ≥ 768、高度 ≥ 680 时，测量当前正文卡片中画面之外的实际高度，加上页顶位置和底部翻页栏高度，按剩余高度 × 1.5 限制画面宽度；同时限制内容宽度和 880px，保持原有 3:2 比例并水平居中。未使用画面 `max-height`、固定定位遮盖或隐藏正文溢出来强行通过验收。翻页、窗口调整、旁白/朗读提示及预览横幅尺寸变化时重新计算；包含页面滚动位置，避免从已滚动页面翻页时计算过大。375×812 不触发该规则，沿用原手机样式。
- `scripts/render_book.py`：封面 `new` 显示「你问：……」；`follow_up` 显示「你接着问：……」及下面的小字「接着《continues_from》」；`no_question` 显示「今天我们来想一想：……」及小字「今天没有问题，这一题是替你出的」。来源书名仍经过 HTML 转义。
- `scripts/test_book_tools.py`：增加三种 mode 的 CLI 渲染检查及来源标题转义检查。`scripts/test_book_interactions.js`：补齐 DOM 替身的查询与窗口事件接口。
- `scripts/test_book_layout.js`：新增使用 Node.js 标准库、通过 Chromium DevTools pipe 测量实际页面的验收脚本，无需安装依赖。覆盖任务指定五种视口，另加 768×680 和 375×812；断言页面高度、读给我听按钮底边、翻页栏、画面比例及手机无横向溢出，并将截图和数值存入临时目录。

### 自测结果

| 项目 | 本次实际结果 |
| --- | --- |
| 样例校验、单文件 HTML 渲染 | 退出码均为 0，生成 `/tmp/curiosity-fix1.html`。 |
| Python 回归 | 11 项全部通过，退出码 0；含三种 mode 文案、小字及来源标题转义。 |
| JavaScript 交互回归 | 退出码 0；翻页、朗读调用、追问选择、存储及反馈导出逻辑通过。 |
| 浏览器验收脚本语法 | `node --check scripts/test_book_layout.js` 退出码 0。 |
| 1280×800、1366×768、1440×900、1920×1080、768×1024 的真实布局验收 | **未完成**。已运行验收脚本，但本机 Chrome 启动后立即以 `SIGABRT` 退出，脚本退出码 1，未取得任何视口数值或截图；直接启动和已有 Playwright 启动也遇到相同退出。 |
| 375×812 手机实际布局 | **未完成**，同一浏览器启动阻碍；不能将保留手机 CSS 等同于实际无溢出验证。 |

浏览器备用通道同样不可用：Chrome CUA 报 `native pipe is closed`，内置浏览器报 `Browser is not available: iab`。因此本次没有声称满足实际浏览器几何验收，仍需在可启动 Chrome 的环境运行下面的最后一条命令。没有安装包、修改系统权限或绕过环境限制。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/validate_book.py assets/sample_book.json
PYTHONDONTWRITEBYTECODE=1 python3 scripts/render_book.py assets/sample_book.json /tmp/curiosity-fix1.html
PYTHONDONTWRITEBYTECODE=1 python3 scripts/test_book_tools.py
node scripts/test_book_interactions.js /tmp/curiosity-fix1.html
node scripts/test_book_layout.js /tmp/curiosity-fix1.html
```

验收脚本第二个参数可指定 Chrome 可执行文件路径，也支持 `CHROME_BIN` 环境变量。脚本加载本地单文件 HTML，不依赖网络；生产渲染与校验脚本仍只用 Python 标准库。本次只改 `scripts/`、`assets/book_template.html` 和按任务要求追加本说明；未改只读输入、未读取 `_runs/`、未 commit/push。

## fix2

### 修改与选择理由

- **1、9 · SVG**：统一使用 `<img src="data:image/svg+xml;base64,...">`，不再把 SVG XML 内联进 HTML DOM。选择图片嵌入，是因为浏览器的 SVG 图片模式隔离脚本执行并禁用外部资源，无需依赖容易漏掉标签、属性大小写或命名空间的过滤规则。SVG 原始字节保留，`xlink:href` 仍在 XML 图片上下文中正确解释，不再被 ElementTree 序列化成 `ns1:href`；每张图片拥有独立的 ID 空间，无需改写引用。PNG/JPG 继续 base64 嵌入，模板现有 `object-fit:contain` 负责完整显示。
- **2 · 路径**：新增校验器和渲染器共用的 `resolve_book_image`。拒绝绝对路径（含 Windows 盘符、UNC）、会越出书目录的 `..`；用 `Path.resolve(strict=True)` 获取真实路径，再用 `relative_to` 检查文件位于书目录内，因此外部文件及外部目录的符号链接均拒绝。允许书目录内的符号链接和不越界的 `images/../local.svg`。渲染器读取图片前独立执行此检查，直接调用 `render_book()` 也不能绕过；角色 `reference_image` 的非空路径同样校验。
- **4 · 陪伴话术**：对 `title`、`guide.catchphrase`、`child_page.prompt`、每章 `follow_up.question`、每页 `narration` / `narration_en` / `visual.description` 检查完整禁词表，大小写不敏感。`question.original` 和 `child_page.child_words` 不做陪伴话术检查，家长说明也不在此检查范围。
- **5 · 必填内容**：schema 仅增加 `minLength` 约束，未增删字段、改字段名或改原有 `required` / `x-rules`。校验器对有正数 `minLength` 的字符串额外检查去空白后非空，覆盖书名、角色描述/口头禅、旁白、画面说明、指令、追问、来源、原理条目等；`child_words` 仍允许留空。向导及可选主角的 `image_anchor` 必须为 15–30 个英文单词（纯数字不计，词内撇号或连字符计作一个词）。
- **10 · 双语**：`language=bilingual` 时逐页要求 `narration_en` 存在且为非空字符串；缺失、null、空字符串或全空白均报准确的页字段路径。英文旁白的 40 词上限继续生效。
- **16 · 运行版本**：本次支持的最低 Python 版本明确为 **Python 3.9**，实际自测使用 Python 3.9.6。旧 SVG 分支的 `removesuffix()` 已随内联逻辑移除。生产脚本仍只用 Python 标准库；Node.js 仅用于已有交互测试，本次使用 v24.14.0。

### 自测结果

- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/test_book_tools.py`：**17 项全部通过，退出码 0**。针对第 1、2、4、5、10 条各新增了可复现的回归测试，另新增四本现有书的 CLI 校验/渲染回归。SVG 测试重现大写 `SCRIPT`、小写 `foreignobject`、混合大小写事件属性及外部引用，并用 HTMLParser 确认产物只含数据图片、没有新增活动 DOM；base64 解码后与原始 SVG 完全一致，含仅有 `xlink:href` 的引用。
- 路径测试覆盖绝对路径、`../` 越界、外部文件/目录符号链接，同时验证合法本地文件和内部符号链接可渲染；非法路径在 CLI 校验、CLI 渲染和直接渲染调用中都被拒绝，CLI 不产生 HTML。
- 文案测试覆盖七类字段的中文和大写英文禁词及孩子原话豁免；空白测试覆盖空字符串、空格、制表、换行和全角空格；锚句测试覆盖 0/14/15/30/31 词及纯数字。双语测试覆盖每一页的缺失/空/null/全空白，并确认合法双语渲染逐页包含英文旁白。

| 现有书 | 校验 | 渲染 |
| --- | --- | --- |
| `assets/sample_book.json` | 通过，3 章 7 页 | 退出码 0 |
| `examples/t10_claude-code_代码画图/book.json` | 通过，3 章 8 页 | 退出码 0 |
| `examples/t10_codex_图片书/book.json` | 通过，3 章 7 页 | 退出码 0 |
| `examples/t10_zcode_代码画图/book.json` | 通过，3 章 7 页 | 退出码 0 |

四本书另行逐本运行 CLI，HTML 输出到系统临时目录，未覆盖仓库内示例。样例另保留一份 `/tmp/curiosity-fix2.html`，运行 `node scripts/test_book_interactions.js /tmp/curiosity-fix2.html` 退出码 0：翻页、朗读参数、追问、存储和反馈导出逻辑均通过。对比 Git 中原 schema 的结构确认差异仅为 `minLength`；`git diff --check` 通过。

### 范围与限制

本节取代前文关于 SVG 黑名单/ID 改写及「双语英文可缺省」的旧说明。SVG 在图片中显示，依赖外部资源的内容不会加载；本次检查的是产物结构、引用字节和脚本逻辑，没有新增真实浏览器截图、实际听音或下载验收。

本次仅修改 `scripts/validate_book.py`、`scripts/render_book.py`、`scripts/test_book_tools.py`、`assets/book.schema.json` 的校验约束，并追加本节。未修改样例、examples、blocklist、模板、README、SKILL 或 references；未读取 `_runs/`，未安装包，未 commit/push，未写 Codex 记忆、设置或密钥。

## fix3

### 修改

- `scripts/render_book.py`：删除正文之间的独立追问卡，全部正文连续翻页；将追问合并到最后的「读完啦」页。标题使用 `child_page.prompt`，第一位为预填 `child_words` 的大输入框，提示「孩子自己说的话，家长帮忙写下来，原话照录」。第二位为小字「说不出来的话，看看这些？」及每章追问按钮；之后保留 reaction、parent_note 和反馈下载。样例总页数从 12 减为 9；未放行样例为 10 页。
- `assets/book_template.html`：提示按钮使用较小字号、浅色背景，点击后保留问题文字并显示「已选」，继续用原有 localStorage 和 `follow_ups_tapped` 导出逻辑；输入框文字仍原样进入 `child_words`，反馈字段不变。移除旧追问卡样式，为「读完啦」页增加紧凑排版及宽度 ≥ 768、高度 680–800 的适配，输入框最低保留 100px；反馈控件仍可向下滚动。提示按钮没有朗读按钮。
- 封面、放行横幅、家长卡位置和展开逻辑保持原有行为：已放行家长卡折叠在最后一页反馈区之后；未放行家长卡在封面之后默认展开。键盘、滑动和正文朗读逻辑未变；正文朗读索引随实际页序连续生成。
- `scripts/test_book_interactions.js`：从实际 HTML 检查连续正文、减少后的页数、追问按钮文字及所在页、输入框优先顺序、末页无朗读按钮；翻到「读完啦」后点击提示按钮、录入原话并检查下载的反馈全部字段，覆盖已选文字、去重、保存/恢复及拒绝存储时的导出。
- `scripts/test_book_tools.py`：增加三种放行状态的末页结构、页序、原话预填、HTML 转义和家长卡回归；遍历样例和全部 examples 校验、渲染，数量要求改为至少五本，允许后续新增示例。`scripts/test_book_layout.js` 增加末页输入框及全部提示按钮不滚动可见、小字号和无横向溢出的真实浏览器断言，并兼容未放行书的第一页正文位置。

### 自测结果

- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/test_book_tools.py`：**18 项全部通过，退出码 0**。
- 任务指定五本书逐本 CLI 渲染及 JavaScript 交互回归通过。执行期间工作区新增 `examples/t10_zcode_代码画图_v2/book.json`，额外检查也通过；没有修改任何书的 JSON。

| 书 | 正文页数 | 翻页总数 | 校验 / 渲染 / 交互回归 |
| --- | --- | --- | --- |
| `assets/sample_book.json` | 7 | 9 | 全部通过 |
| `examples/t10_claude-code_代码画图/book.json` | 8 | 10 | 全部通过 |
| `examples/t10_codex_图片书/book.json` | 7 | 9 | 全部通过 |
| `examples/t10_zcode_代码画图/book.json` | 7 | 10 | 全部通过 |
| `examples/t22_codex_孩子当主角/book.json` | 6 | 9 | 全部通过 |
| `examples/t10_zcode_代码画图_v2/book.json`（额外） | 7 | 10 | 全部通过 |

- 另用 `/tmp/curiosity-fix3-books/prefilled.json` 检查包含空格、换行、`<` 和 `&` 的已有孩子原话：HTML 正确转义，交互回归确认预填及不编辑时的反馈导出保留原话。临时 JSON/HTML 全部放在 `/tmp/`，样例 HTML 为 `/tmp/curiosity-fix3.html`。
- `node --check scripts/test_book_layout.js`、`git diff --check` 均通过。
- **真实视口布局验收未完成**：实际运行 `node scripts/test_book_layout.js /tmp/curiosity-fix3.html`，Chrome 启动即以 `SIGABRT` 退出，脚本退出码 1，没有取得截图或几何数据。备用浏览器通道拒绝 `file:///tmp/curiosity-fix3.html`，说明 URL 策略仅允许 http/https，禁止绕过；本次没有绕过此限制。因此不能声称已实测满足 1280×800 等视口下的输入框和提示按钮可见要求。JavaScript 回归使用 DOM 替身，也不代表实际听音或浏览器下载已验收。

可复跑命令：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/test_book_tools.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/render_book.py assets/sample_book.json /tmp/curiosity-fix3.html
node scripts/test_book_interactions.js /tmp/curiosity-fix3.html
node scripts/test_book_layout.js /tmp/curiosity-fix3.html
```

### 范围

本次仅修改 `scripts/render_book.py`、`assets/book_template.html`、三个 `scripts/test_*` 文件，并按要求追加本节。未修改 schema 或任何 book.json，未读取 `_runs/`，未安装包，未 commit/push。工作区同时出现 README、SKILL、references 和新增示例等其他变动，均非本任务写入，未还原或覆盖。

## fix4

### 修改

- `scripts/validate_book.py`：实现 `x-rules.age_band_limits`，small 正文 3–4 页、中文旁白 ≤30 字；middle 4–6 页、≤45 字；large 4–8 页、≤60 字。未填 `age_band` 按 large，follow_up 三档下限均为 2、各档上限不变。中文计数沿用去掉空白后计算字符数（含标点），适用于 zh / bilingual；英文仍为 40 词上限。非法档位由 schema 报错，不会导致规则校验崩溃。
- 实现 `co_reading_pages`，超过正文总页数时报 `parent_card.co_reading.pauses[N].page`。共读卡可省略，有则执行 schema 的对象、必填字段、数组和非空文本约束；补上数值 `minimum` / `maximum` 支持，执行 schema 中页码至少为 1 的限制，同时拒绝布尔值、字符串和非整数页码。
- `scripts/render_book.py`：所有家长卡在 summary 后第一行固定显示「这本书由 AI 生成，家长看过才算数。」。有共读卡时显示「怎么一起读」、逐项「第 N 页：问……」及 tips。封面有档位才显示对应「小班 3–4 岁 / 中班 4–5 岁 / 大班 5–6 岁」。
- 共读提示按正文连续页码匹配，不包含封面、家长预览页或结尾页；同页多个 pause 均显示。提示放在旁白之后、朗读按钮之前，HTML 转义处理；提示和 tips 不进入朗读数据，也不新增按钮。
- `assets/book_template.html`：提示使用 13px、浅色 `#9b8b77`（旁白为 22–28px），封面档位为 14px。沿用 fix1 测量剩余高度、同时缩小画面宽度的适配，家长提示占用高度也计入；增加提示尺寸观察，变化后重新适配。
- `scripts/test_book_tools.py`：新增三档在三种 mode 下页数边界、中文/双语长度边界、英文上限、默认 large、非法档位、共读卡缺失/合法/越界/错误结构测试；检查家长卡顶部声明、共读页码跨章及预览页映射、同页多个提示、转义和朗读数据。现有书回归至少要求六本。
- `scripts/test_book_layout.js`：改为每一页正文都检查七种视口，增加提示字号明显小于旁白、在旁白与朗读按钮之间、桌面无需滚动可见等断言，保留画面 3:2、朗读按钮、翻页栏和末页布局检查。

### 自测结果

- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/test_book_tools.py`：**22 项全部通过，退出码 0**。
- 六本现有书分别运行 CLI 校验、CLI 渲染及 JavaScript 交互回归：全部通过；输出在 `/tmp/curiosity-fix4-books/existing-0.html` 至 `existing-5.html`，未覆盖 examples。

| 书 | 正文页数 | 校验 / 渲染 / 交互回归 |
| --- | --- | --- |
| `assets/sample_book.json` | 7 | 全部通过 |
| `examples/t10_claude-code_代码画图/book.json` | 8 | 全部通过 |
| `examples/t10_codex_图片书/book.json` | 7 | 全部通过 |
| `examples/t10_zcode_代码画图/book.json` | 7 | 全部通过 |
| `examples/t10_zcode_代码画图_v2/book.json` | 7 | 全部通过 |
| `examples/t22_codex_孩子当主角/book.json` | 6 | 全部通过 |

- 另生成已放行、未放行共读测试书，档位 large，正文第 1 / 3 / 7 页有提示，第一页旁白达到 60 字上限。两份校验、渲染和交互回归均通过；临时 JSON / HTML 为 `/tmp/curiosity-fix4-books/co-reading-approved.*`、`co-reading-pending.*`。
- `node --check scripts/test_book_layout.js`、`git diff --check` 通过。
- **真实布局验收未完成**：对样例和两份共读书实际运行布局脚本，Chrome 均启动即 `SIGABRT`，脚本退出码 1，未取得截图或几何数据。尝试本地 HTTP 服务时，环境拒绝绑定 `127.0.0.1`（`Operation not permitted`）；备用浏览器安全策略拒绝 `file://`，只允许 http/https，明确禁止绕过。停止此浏览器路径，未降低保护或申请额外权限。因此不能声称已实测通过 1280×800 的正文无滚动要求。交互回归使用 DOM 替身，也不代表真实听音或下载验收。

可复跑命令（临时共读书保留在上述目录）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/test_book_tools.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/render_book.py assets/sample_book.json /tmp/curiosity-fix4.html
node scripts/test_book_interactions.js /tmp/curiosity-fix4.html
node scripts/test_book_layout.js /tmp/curiosity-fix4.html
node scripts/test_book_layout.js /tmp/curiosity-fix4-books/co-reading-approved.html
node scripts/test_book_layout.js /tmp/curiosity-fix4-books/co-reading-pending.html
```

### 范围

本次仅写入 `scripts/validate_book.py`、`scripts/render_book.py`、`scripts/test_book_tools.py`、`scripts/test_book_layout.js`、`assets/book_template.html` 和本交付记录。`assets/book.schema.json` 在开始前已修改，本任务未编辑；期间另有 `SKILL.md` 变动，也非本任务写入。未修改任何现有书 JSON、README、references 或 blocklist；未读取 `_runs/`，未安装包，未 commit/push。
