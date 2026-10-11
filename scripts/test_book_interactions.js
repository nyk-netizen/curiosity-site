// Optional Node.js stdlib check for inline JavaScript behavior, without a browser.
// This checks event/data logic; it cannot verify layout or audible speech.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const documentText = fs.readFileSync(process.argv[2] || '/tmp/sample.html', 'utf8');
const payload = JSON.parse(documentText.match(/<script id="book-data" type="application\/json">([\s\S]*?)<\/script>/)[1]);
const source = documentText.match(/<script>\s*([\s\S]*?)<\/script>/)[1];
const decode = text => text.replace(/&(amp|lt|gt|quot|#x27);/g,
  (_, entity) => ({amp:'&', lt:'<', gt:'>', quot:'"', '#x27':"'"}[entity]));
const sections = [...documentText.matchAll(/<section (?:hidden )?class="page[^>]*>[\s\S]*?<\/section>/g)].map(match => match[0]);
const followMarkup = [...documentText.matchAll(/<button class="follow-button"[^>]*data-follow="(\d+)"[^>]*>([\s\S]*?)<\/button>/g)];
const initialWords = decode(documentText.match(/<textarea id="child-words"[^>]*>([\s\S]*?)<\/textarea>/)[1]);
const firstStory = sections.findIndex(section => /class="page story"/.test(section));
const storyCount = Object.keys(payload.narrations).length;
assert.equal(firstStory, documentText.includes('id="preview-banner"') ? 2 : 1);
assert.equal(sections.length, firstStory + storyCount + 1, 'No chapter follow-up pages');
assert.match(sections.at(-1), /aria-label="读完啦"/);
assert.equal(followMarkup.length, payload.followUps.length);
for (let i = 0; i < storyCount; i++) {
  assert.match(sections[firstStory + i], /class="page story"/);
  assert.ok(payload.narrations[String(firstStory + i)], 'Continuous narration indices');
  assert.doesNotMatch(sections[firstStory + i], /data-follow=/);
}
const ending = sections.at(-1);
assert.ok(ending.indexOf('id="child-words"') < ending.indexOf('class="follow-prompts"'), 'Child words come first');
assert.ok(ending.indexOf('class="follow-prompts"') < ending.indexOf('<fieldset>'), 'Feedback comes after prompts');
assert.doesNotMatch(ending, /data-read=/, 'Prompts have no read-aloud buttons');
followMarkup.forEach((match, i) => {
  assert.equal(Number(match[1]), i);
  assert.equal(decode(match[2]), payload.followUps[i], 'Button displays the question');
  assert.ok(ending.includes(match[0]), 'All prompts are on the ending page');
});

class Element {
  constructor() { this.listeners = {}; this.value = ''; this.checked = false; this.disabled = false; this.attributes = {}; this.dataset = {}; this.textContent = ''; }
  addEventListener(type, callback) { (this.listeners[type] ||= []).push(callback); }
  fire(type, details = {}) { for (const callback of this.listeners[type] || []) callback({target: this, ...details}); }
  setAttribute(name, value) { this.attributes[name] = value; }
  closest() { return null; }
  click() { this.fire('click'); }
  remove() {}
}
function start({saved = {}, deniedStorage = false, data = payload, audioSupport = false,
    voices = [], noSpeech = false, rejectPlayback = false, throwPlayback = false} = {}) {
  const ids = Object.fromEntries(['previous','next','child-words','parent-note','page-count','book-pages','export-feedback','save-status','book-data'].map(id => [id, new Element()]));
  ids['book-data'].textContent = JSON.stringify(data);
  ids.previous.disabled = true;
  ids['child-words'].value = initialWords;
  const pages = [...documentText.matchAll(/<section (?:hidden )?class="page[^>]*>/g)].map((match, i) => ({hidden: i !== 0, querySelector: () => null}));
  const follows = followMarkup.map(match => { const e = new Element(); e.dataset.follow = match[1]; e.textContent = decode(match[2]); return e; });
  const reads = Object.keys(data.narrations).map(index => { const e = new Element(); e.dataset.read = index; e.nextElementSibling = new Element(); return e; });
  const radios = ['loved','ok','bored','scared','confused'].map(value => { const e = new Element(); e.value = value; return e; });
  const storage = new Map(Object.entries(saved));
  const spoken = [], downloads = [], recordings = [];
  let canceled = 0;
  const doc = new Element();
  doc.getElementById = id => ids[id] || null;
  doc.querySelectorAll = selector => ({'.page': pages, '[data-follow]': follows, '[data-read]': reads, 'input[name="reaction"]': radios}[selector]);
  doc.querySelector = () => radios.find(r => r.checked) || null;
  doc.createElement = () => { const e = new Element(); e.click = () => downloads.push(e.download); return e; };
  doc.body = {appendChild() {}};
  doc.documentElement = {style: {setProperty() {}}};
  let blob;
  const context = {document: doc, window: {speechSynthesis: {cancel() { canceled++; }, getVoices: () => voices, speak: u => spoken.push(u)}, scrollTo() {}, addEventListener() {}},
    SpeechSynthesisUtterance: class { constructor(text) { this.text = text; } },
    localStorage: {getItem: key => { if (deniedStorage) throw Error('unavailable'); return storage.get(key); },
      setItem: (key, value) => { if (deniedStorage) throw Error('unavailable'); storage.set(key, value); }},
    URL: {createObjectURL: value => { blob = value; return 'blob:test'; }, revokeObjectURL() {}}, Blob, setTimeout() {}, Date};
  context.window.SpeechSynthesisUtterance = context.SpeechSynthesisUtterance;
  if (noSpeech) { delete context.window.speechSynthesis; delete context.window.SpeechSynthesisUtterance; }
  if (audioSupport) context.window.Audio = class {
    constructor(src) { this.src = src; this.currentTime = 0; this.played = 0; this.paused = 0; recordings.push(this); }
    play() {
      this.played++;
      if (throwPlayback) throw Error('play failed');
      return rejectPlayback ? Promise.reject(Error('play rejected')) : Promise.resolve();
    }
    pause() { this.paused++; }
  };
  vm.runInNewContext(source, context);
  return {ids, pages, follows, reads, radios, storage, spoken, downloads, recordings, doc,
    canceled: () => canceled, feedback: async () => JSON.parse(await blob.text())};
}
(async () => {
  const test = start();
  const {ids, pages, follows, reads, radios} = test;
  const total = sections.length;
  assert.equal(ids['child-words'].value, initialWords, 'Book child_words are prefilled');
  assert.equal(pages.length, total);
  assert.equal(test.spoken.length, 0, 'No automatic speech on load');
  ids.next.click(); assert.equal(ids['page-count'].textContent, `2 / ${total}`); assert.equal(pages[1].hidden, false);
  reads[0].click(); assert.equal(test.spoken[0].lang, 'zh-CN'); assert.equal(test.spoken[0].rate, 0.9);
  assert.equal(test.spoken[0].text, payload.narrations[String(firstStory)][0].text);
  const key = (value, target = new Element()) => test.doc.fire('keydown', {key: value, target, preventDefault() {}});
  key('ArrowRight'); assert.equal(ids['page-count'].textContent, `3 / ${total}`);
  const input = new Element(); input.closest = () => input;
  key('ArrowRight', input); assert.equal(ids['page-count'].textContent, `3 / ${total}`, 'Typing does not turn pages');
  key('ArrowLeft'); assert.equal(ids['page-count'].textContent, `2 / ${total}`);
  ids['book-pages'].fire('touchstart', {touches: [{clientX: 300, clientY: 100}]});
  ids['book-pages'].fire('touchend', {changedTouches: [{clientX: 100, clientY: 110}]});
  assert.equal(ids['page-count'].textContent, `3 / ${total}`);
  ids['book-pages'].fire('touchstart', {touches: [{clientX: 100, clientY: 100}]});
  ids['book-pages'].fire('touchend', {changedTouches: [{clientX: 170, clientY: 300}]});
  assert.equal(ids['page-count'].textContent, `3 / ${total}`, 'Vertical scroll does not turn pages');
  while (!ids.next.disabled) ids.next.click();
  assert.equal(pages.at(-1).hidden, false);
  follows[0].click(); follows[0].click();
  assert.equal(follows[0].attributes['aria-pressed'], 'true');
  assert.match(follows[0].textContent, /已选/);
  assert.equal(follows[0].textContent, `已选 · ${payload.followUps[0]}`);
  assert.equal(follows[1].textContent, payload.followUps[1]);
  ids['child-words'].value = ' 孩子的原话\n'; ids['child-words'].fire('input');
  ids['parent-note'].value = '明天再看看'; ids['parent-note'].fire('input');
  radios[0].checked = true; radios[0].fire('change');
  assert.equal(ids['page-count'].textContent, `${total} / ${total}`);
  ids['export-feedback'].click();
  const feedback = await test.feedback();
  assert.deepEqual(Object.keys(feedback), ['book_title','question','date','follow_ups_tapped','child_words','reaction','parent_note']);
  assert.equal(feedback.book_title, payload.title); assert.equal(feedback.question, payload.question);
  assert.match(feedback.date, /^\d{4}-\d{2}-\d{2}$/);
  assert.deepEqual(feedback.follow_ups_tapped, [payload.followUps[0]]);
  assert.equal(feedback.child_words, ' 孩子的原话\n'); assert.equal(feedback.reaction, 'loved');
  assert.equal(feedback.parent_note, '明天再看看'); assert.deepEqual(test.downloads, ['feedback.json']);
  const reload = start({saved: Object.fromEntries(test.storage)});
  assert.equal(reload.follows[0].attributes['aria-pressed'], 'true');
  assert.equal(reload.follows[0].textContent, `已选 · ${payload.followUps[0]}`);
  assert.equal(reload.ids['child-words'].value, ' 孩子的原话\n'); assert.equal(reload.radios[0].checked, true);
  const blocked = start({deniedStorage: true}); blocked.follows[1].click(); blocked.ids['export-feedback'].click();
  const blockedFeedback = await blocked.feedback();
  assert.deepEqual(blockedFeedback.follow_ups_tapped, [payload.followUps[1]]);
  assert.equal(blockedFeedback.child_words, initialWords, 'Prefilled child_words export unchanged');
  const english = start({data: {...payload, narrations: {'1': [{text:'Hello', lang:'en-US'}]}}});
  english.reads[0].click(); assert.equal(english.spoken[0].lang, 'en-US');
  const bilingual = start({data: {...payload, narrations: {'1': [{text:'你好', lang:'zh-CN'}, {text:'Hello', lang:'en-US'}]}}});
  bilingual.reads[0].click(); bilingual.spoken[0].onend(); assert.equal(bilingual.spoken[1].lang, 'en-US');
  const zh = {text:'你好', lang:'zh-CN'}, en = {text:'Hello', lang:'en-US'};
  const zhAudio = {...zh, audio:'data:audio/mpeg;base64,SUQz'}, enAudio = {...en, audio:'data:audio/mpeg;base64,SUQzZW4='};
  const speechData = lines => ({...payload, narrations: {'1': lines}});
  // Recordings play even on browsers without speechSynthesis; no auto-play.
  const audio = start({data:speechData([zhAudio, enAudio]), audioSupport:true, noSpeech:true});
  assert.equal(audio.recordings.length, 0);
  audio.reads[0].click();
  assert.equal(audio.recordings[0].src, zhAudio.audio);
  assert.equal(audio.recordings[0].played, 1);
  assert.equal(audio.spoken.length, 0);
  assert.equal(audio.reads[0].textContent, '停止朗读');
  const lateEnd = audio.recordings[0].onended;
  audio.recordings[0].currentTime = 3;
  audio.reads[0].click();
  assert.equal(audio.recordings[0].paused, 1);
  assert.equal(audio.recordings[0].currentTime, 0);
  assert.equal(audio.reads[0].textContent, '读给我听');
  lateEnd(); assert.equal(audio.recordings.length, 1, 'Stopped callbacks cannot play English');
  audio.reads[0].click(); audio.recordings[1].onended();
  assert.equal(audio.recordings[2].src, enAudio.audio, 'Bilingual recordings play in order');
  audio.recordings[2].onended(); assert.equal(audio.reads[0].textContent, '读给我听');
  audio.reads[0].click();
  const pageEnd = audio.recordings[3].onended;
  audio.ids.next.click();
  assert.equal(audio.recordings[3].paused, 1);
  pageEnd(); assert.equal(audio.recordings.length, 4, 'Page change cancels the bilingual sequence');
  const stoppedSpeech = start({data:speechData([zh, en])});
  stoppedSpeech.reads[0].click(); const speechEnd = stoppedSpeech.spoken[0].onend;
  stoppedSpeech.reads[0].click(); speechEnd();
  assert.equal(stoppedSpeech.spoken.length, 1);
  assert.equal(stoppedSpeech.canceled(), 2);
  stoppedSpeech.reads[0].click(); const speechPageEnd = stoppedSpeech.spoken[1].onend;
  stoppedSpeech.ids.next.click(); speechPageEnd(); assert.equal(stoppedSpeech.spoken.length, 2);
  for (const name of ['Microsoft Xiaoxiao Online', '晓晓', 'Tingting', '婷婷']) {
    const preferred = {name, lang:'zh_CN'};
    const voiceTest = start({data:speechData([zh]), voices:[{name:'Default',lang:'zh-CN'}, {name:'English Xiaoxiao',lang:'en-US'}, preferred]});
    voiceTest.reads[0].click(); assert.equal(voiceTest.spoken[0].voice, preferred);
  }
  const mixed = start({data:speechData([zhAudio, en]), audioSupport:true});
  mixed.reads[0].click(); mixed.recordings[0].onended(); assert.equal(mixed.spoken[0].lang, 'en-US');
  const mixedReverse = start({data:speechData([zh, enAudio]), audioSupport:true});
  mixedReverse.reads[0].click(); mixedReverse.spoken[0].onend(); assert.equal(mixedReverse.recordings[0].src, enAudio.audio);
  for (const options of [{rejectPlayback:true}, {throwPlayback:true}, {}]) {
    const fallback = start({data:speechData([zhAudio]), audioSupport:true, ...options});
    fallback.reads[0].click();
    if (!options.rejectPlayback && !options.throwPlayback) {
      const failure = fallback.recordings[0].onerror; failure(); failure();
    }
    await Promise.resolve();
    assert.equal(fallback.spoken.length, 1, 'Recording failure falls back exactly once');
    assert.equal(fallback.spoken[0].text, zh.text);
  }
  const lateRejection = start({data:speechData([zhAudio, enAudio]), audioSupport:true, rejectPlayback:true});
  lateRejection.reads[0].click(); lateRejection.ids.next.click(); await Promise.resolve();
  assert.equal(lateRejection.spoken.length, 0, 'Late play rejection cannot start speech after changing page');
  const unavailable = start({data:speechData([zh]), noSpeech:true});
  unavailable.reads[0].click(); assert.match(unavailable.reads[0].nextElementSibling.textContent, /暂不支持朗读/);
  assert.equal(unavailable.reads[0].textContent, '读给我听');
  console.log('通过：翻页、键盘/输入框、滑动、无自动朗读、zh/en/双语朗读参数、追问去重、localStorage 恢复、反馈全部字段、存储被禁用时导出。');
  console.log('独立 DOM 替身测试；不代表真实浏览器截图或实际听到声音。');
  console.log('通过：录音优先、点击停止、翻页取消、双语录音/混合回退、过期回调隔离、中文声音优选、录音失败回退。');
})().catch(error => { console.error(error); process.exitCode = 1; });
