# T-CODEX-fix5 · 朗读换成「晓晓」（edge-tts，作者定）

禁止项同 T-CODEX.md 第 5 节。只改 scripts/ 和 assets/book_template.html。不改 schema、不改任何 book.json。

## 现状
「读给我听」用浏览器 speechSynthesis，声音不好。本机装有 edge-tts 7.2.8（/opt/homebrew/bin/edge-tts，python3.11 可 import edge_tts），作者要用 `zh-CN-XiaoxiaoNeural`（晓晓）。

## 要做
1. 新脚本 `scripts/make_audio.py <book.json> [--voice zh-CN-XiaoxiaoNeural] [--rate -5%]`：
   - 给每页 narration 生成 mp3，存在书目录 `audio/p01.mp3`、`audio/p02.mp3`……（顺序同正文页）；language=en 默认用 `en-US-AnaNeural`，bilingual 的 narration_en 另存 `audio/p01_en.mp3`
   - 已存在且旁白没变的不重复生成（可用一个 `audio/manifest.json` 记文本哈希）
   - 优先调用 python 的 edge_tts 库，没有就调用 edge-tts 命令行；都没有就打印清楚的提示并以非 0 退出
   - 需要联网（edge-tts 是在线服务）；网络失败要报清楚哪一页失败
2. `render_book.py`：
   - 如果书目录里有 `audio/pNN.mp3`，就 base64 内嵌进 HTML，「读给我听」播放这段录音（再点一次停止；翻页时停止上一页的播放）
   - 没有录音的页面，退回现在的 speechSynthesis，但优先挑名字含 Xiaoxiao / 晓晓 / Tingting / 婷婷 的中文声音
   - 加一个参数 `--with-audio`：渲染前先自动跑 make_audio.py（失败就警告并退回浏览器朗读，不中断渲染）
   - 路径安全规则沿用 fix2（audio 也必须在书目录内）
3. 测试：make_audio 的缓存逻辑、render 在有/无 audio 时的行为（测试里可以 mock edge_tts，不必真联网）；**另外真实跑一次** `python3.11 scripts/make_audio.py assets/sample_book.json` 确认能出 mp3（输出到 assets/audio/ 后，测完删掉，不要留在仓库里）
4. 结果追加到 tasks/out-T-CODEX.md 末尾「fix5」一节，写明：每页大约多大、总共多大、生成一本要多久
