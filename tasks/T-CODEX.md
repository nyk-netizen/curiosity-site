# T-CODEX · Skill 的 assets 与 scripts

> 派给 Codex（gpt-6.1-sol / high）。工作目录是仓库根目录 `curiosity-site/`。
> 这个仓库是一个开源 Agent Skill「好奇心工地」：孩子提一个问题，agent 按固定流程做一本把问题讲清楚的绘本。你负责其中两个不依赖任何模型的工具。

## 1. 目标

1. `scripts/validate_book.py`：校验一本书的 JSON 是否合格
2. `scripts/render_book.py`：把这份 JSON 渲染成**一个能离线打开的单文件 HTML 绘本**
3. `assets/imagegen_notes.md`：你自己（Codex）用内置生图能力做绘本时的操作说明（见第 3 节）

## 2. 输入（只读，不许改）

- `assets/book.schema.json`：书的数据结构，**唯一准绳**。注意末尾的 `x-rules`，那是 JSON Schema 表达不了、但校验脚本必须查的规则
- `assets/sample_book.json`：样例书（7 页，没有图片，`render.route = code`）
- `assets/ip_blocklist.txt`、`assets/companion_blocklist.txt`：禁用词表，`#` 开头是注释

## 3. 产出

### 3.1 `scripts/validate_book.py`
- 用法：`python3 scripts/validate_book.py <book.json>`
- **只用 Python 标准库**（不许 `pip install jsonschema`）。自己实现一个够用的 JSON Schema 子集：`type`（含 `["string","null"]` 这种数组形式）、`required`、`properties`、`additionalProperties: false`、`enum`、`const`、`minItems`、`maxItems`、`minLength`、`maxLength`、`items`。schema 从 `assets/book.schema.json` 读（相对脚本位置定位，不依赖当前目录）
- 再逐条实现 `x-rules` 里的每一条
- 通过：打印一行「通过」+ 页数统计，退出码 0
- 不通过：逐条列出错误，每条带 JSON 路径（如 `chapters[1].pages[0].narration`）和中文说明，退出码 1。一次列全，不要遇到第一个错误就停
- `--json` 参数：把结果按 `{"ok": bool, "errors": [{"path","message"}], "stats": {...}}` 输出，方便 agent 读

### 3.2 `scripts/render_book.py`
- 用法：`python3 scripts/render_book.py <book.json> <输出.html>`
- 输出**单个 HTML 文件**，断网能打开：CSS/JS 内联；`.png/.jpg` 图片转 base64 内嵌；`.svg` 直接内联。图片路径相对 book.json 所在目录
- 渲染前先跑一遍校验（import validate_book 里的函数），不通过就报错退出，不出 HTML
- 只用 Python 标准库

页面结构（一屏一页，可翻页）：
1. **封面**：书名、孩子的原问题（「你问：……」）、向导角色名字和口头禅
2. **正文页**：上面是画面（3:2，完整显示不裁切；没有图片时显示一个浅色框，里面写 `visual.description`），下面是旁白（大字）+「读给我听」按钮
3. **每章最后一页之后**插一张「追问口」卡片：显示这一章的 `follow_up.question`，按钮「我也想知道这个！」。点了之后按钮变成已选状态，记进 localStorage
4. **最后一页留给孩子**：显示 `child_page.prompt`，下面一个大输入框（家长代写孩子的原话）；如果 `child_words` 已经有内容就预先填上
5. **反馈导出**：最后一页有个按钮「保存这次的反馈」，下载一个 `feedback.json`：
   ```json
   {"book_title": "...", "question": "...", "date": "YYYY-MM-DD",
    "follow_ups_tapped": ["孩子点过的追问"], "child_words": "输入框里的话",
    "reaction": "", "parent_note": ""}
   ```
   页面上加两个家长填的小控件：reaction 单选（喜欢 / 一般 / 没兴趣 / 害怕了 / 没听懂，对应 `loved/ok/bored/scared/confused`）、parent_note 文本框
6. **家长卡**：放在最后，用 `<details>` 默认折叠，标题「家长卡（给大人看）」。里面显示 hard_notes、sources（网址可点）、uncertain、sensitive、weekend_project、approval
7. **放行门**：如果 `parent_card.approval.status` 不是 `approved`：页面顶部固定一条横幅「家长预览版 · 还没放行，先别给孩子看」，家长卡默认展开并放到封面之后；`sensitive.level = parent_first` 时横幅里加一句「这本书涉及：<topics 中文名>」。topics 中文名：death 死亡、body 身体、fear 恐惧、religion 宗教、family_change 家庭变化、disaster 灾难、other 其他

交互：上一页 / 下一页按钮 + 键盘左右键 + 手机左右滑动；页码显示「3 / 9」。

朗读：浏览器自带 `speechSynthesis`，`zh-CN`（language=en 用 `en-US`），语速 0.9。浏览器要求先有一次用户点击才能出声，按钮点击本身就算，不要在页面加载时自动朗读。

视觉：
- 暖色浅底，不用暗色冷调（孩子的界面）；大字号，正文旁白手机上不小于 20px
- 手机竖屏（375 宽）也要能用；**宽屏下卡片不能被压成横条**：内容区限制最大宽度（比如 880px）并居中，画面按 3:2 显示，不要用 max-height 把画面压扁
- 翻页按钮、页码这类浮动元素不能挡住画面主体
- 不引入任何外部字体、CDN、图片

### 3.3 `assets/book_template.html`（可选）
render 如果用模板，模板放这里；也可以全部写在 render_book.py 里。

### 3.4 `assets/imagegen_notes.md`
写给「能直接生图的 agent」（以你自己为例）看的操作说明，中文，不超过 60 行：
- 先出一张角色参考图（用 `guide.image_anchor`），存成 `images/guide_ref.png`，把相对路径写回 `guide.reference_image`
- 之后每页都带上这张参考图生成，保证跨页一致；图片存成 `images/p01.png`、`images/p02.png`……，路径写回 `visual.image`
- 你实际用什么工具、什么参数、每张大约多久、出图尺寸。只写你确实知道、确实能做到的
- 一本 6–8 页串行出图要多久，怎样省时间
- 隐私：生图时提示词和参考图会发给哪家服务；不要把孩子的真实照片当参考图

### 3.5 `tasks/out-T-CODEX.md`
交付说明：做了什么、怎么跑、已知限制、哪里不确定。

## 4. 验收（Claude Code 会自己跑，不看自查表）

- [ ] `python3 scripts/validate_book.py assets/sample_book.json` 退出码 0
- [ ] 复制一份样例，分别：删掉 `parent_card.sources`、把一页旁白改成 80 字、在书名里塞「神奇校车」、在旁白里塞「我永远陪着你」、把 mode 改成 follow_up 但不填 continues_from、删掉一章——每种都能报出对应的错，路径正确
- [ ] `python3 scripts/render_book.py assets/sample_book.json /tmp/sample.html` 出的 HTML 断网能打开；375 / 768 / 1280 / 1920 四个宽度截图都没有横条、没有遮挡
- [ ] 把样例的 approval.status 改成 pending 再渲染，能看到放行横幅，家长卡展开
- [ ] 点「读给我听」有声音；点追问按钮后导出的 feedback.json 里有这条追问

## 5. 禁止

- 只许写 `scripts/`、`assets/`（除了下面不许改的）和 `tasks/out-T-CODEX.md`
- 不许改 `assets/book.schema.json`、`assets/sample_book.json`、两个 blocklist、`SKILL.md`、`references/`、`README.md`
- 不许 git commit / push
- 不许写 `~/.codex` 下的记忆和设置
- 不许把任何 key 写进文件
- 不许读 `_runs/` 下的任何东西
- 不许引入任何现成 IP 角色的名字或形象
- 不许 pip install；只用标准库
