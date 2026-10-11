# T-RUN-T10 · 在一个平台上装好 Skill，跑一道题

> 三个平台（Claude Code / Codex / ZCode）用同一份说明，只有 `<平台>` 和输出文件夹不同。
> 目的：验证一个**没见过这个仓库**的 agent，只看 `SKILL.md` 能不能按流程做出一本合格的书。

## 贴给 agent 的话

> 下面问卷里的孩子（小名「豆豆」）、兴趣、恐惧和角色原话**全部是虚构的测试数据**，不是真实孩子。

```
你装了一个叫「好奇心工地」（curiosity-site）的 skill，位置：<skill 目录>。
请按它的 SKILL.md 和用到的 references/ 工作，帮一位家长把孩子的问题做成一本绘本。

规则：
1. 所有产出只写到 <输出文件夹> 这一个文件夹里（它就是 SKILL.md 里说的 curiosity-site-books/）。
   不要打开仓库里的 _runs/、examples/ 或任何其他成品，也不要参考 assets/sample_book.json 以外的书。
2. 家长已经填过问卷，你直接把下面这份答案整理成 <输出文件夹>/_family/profile.json，不用再问：
   - 孩子：5 岁，中文，不认字，小名「豆豆」
   - 兴趣：车与工程机械、动物
   - 怕：黑
   - 家长先看的话题：死亡、身体与性别
   - 向导角色：已经和孩子一起造好了，角色卡如下（原样用）：
     名字：小方
     外形：一个橙色的方块小工人，戴黄色安全帽，圆圆的黑眼睛，两只短短的蓝胳膊，背着一个工具包
     颜色：橙色、黄色、蓝色
     口头禅：戴好安全帽，我们进去看看！
     image_anchor：a small orange cube-shaped builder with a yellow hard hat, round black eyes, short blue arms and a tiny tool bag
     孩子的原话：「它是个方方的小工人，橙色的，要戴黄帽子，手是蓝的，还要背工具包」
   - 怎么读：家长读
   - 出什么：<路线>
   - 多长：标准（6–8 页）
   - 放行：每本都要家长先看
   - 分享：可以公开
3. 孩子的问题是：「<问题>」
4. 做到第 7 步「家长放行」时停下：approval 保持 pending，把你会对家长说的话写进交付说明，不要自己改成 approved。
5. 能联网就查证；不能联网就照 SKILL.md 的规定在 sources 里写明。
6. 做完后在 <输出文件夹>/交付说明.md 里写：走了哪几步、每步大约用时、哪一步不确定、SKILL.md 里哪里写得让你犹豫。
```

## 各平台的填法

| 平台 | skill 目录 | 输出文件夹 | 路线 |
|---|---|---|---|
| Claude Code | `~/.claude/skills/curiosity-site` | `<仓库>/_runs/claude-code/` | 代码画的书（你只能写代码，按 06 的代码画图路线） |
| Codex | `~/.codex/skills/curiosity-site` | `<仓库>/_runs/codex/` | 图片书（你能直接生图，按 06 的生图路线） |
| ZCode | `~/.agents/skills/curiosity-site` | `<仓库>/_runs/zcode/` | 代码画的书（你只能写代码，按 06 的代码画图路线） |

## 验收（Claude Code 自己跑）

- [ ] 输出文件夹里有 `_family/profile.json`、`<日期>_<题目>/book.json`、`images/`、`book.html`、`交付说明.md`
- [ ] 自己重跑 `validate_book.py`，退出码 0
- [ ] `book.html` 浏览器打开：有「家长预览版」横幅、三章、每章一个追问口、最后一页留给孩子、家长卡
- [ ] 画面：SVG 用 `rsvg-convert -w 1536 -h 1024` 按原尺寸渲染看；PNG 和角色参考图并排看一致性
- [ ] 家长卡的 `sources` 抽查一条能不能打开；`uncertain` 不是空的
- [ ] 没有越界写文件（`git status` 看）
