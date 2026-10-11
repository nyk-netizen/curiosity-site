// Optional Node.js stdlib check for inline JavaScript behavior, without a browser.
// This checks event/data logic; it cannot verify layout or audible speech.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const documentText = fs.readFileSync(process.argv[2] || '/tmp/sample.html', 'utf8');
const payload = JSON.parse(documentText.match(/<script id="book-data" type="application\/json">([\s\S]*?)<\/script>/)[1]);
const source = documentText.match(/<script>\s*([\s\S]*?)<\/script>/)[1];

class Element {
  constructor() { this.listeners = {}; this.value = ''; this.checked = false; this.disabled = false; this.attributes = {}; this.dataset = {}; this.textContent = ''; }
  addEventListener(type, callback) { (this.listeners[type] ||= []).push(callback); }
  fire(type, details = {}) { for (const callback of this.listeners[type] || []) callback({target: this, ...details}); }
  setAttribute(name, value) { this.attributes[name] = value; }
  closest() { return null; }
  click() { this.fire('click'); }
  remove() {}
}
function start({saved = {}, deniedStorage = false, data = payload} = {}) {
  const ids = Object.fromEntries(['previous','next','child-words','parent-note','page-count','book-pages','export-feedback','save-status','book-data'].map(id => [id, new Element()]));
  ids['book-data'].textContent = JSON.stringify(data);
  ids.previous.disabled = true;
  ids['child-words'].value = '原先的话';
  const pages = [...documentText.matchAll(/<section (?:hidden )?class="page[^>]*>/g)].map((match, i) => ({hidden: i !== 0, querySelector: () => null}));
  const follows = data.followUps.map((_, i) => { const e = new Element(); e.dataset.follow = String(i); return e; });
  const reads = Object.keys(data.narrations).map(index => { const e = new Element(); e.dataset.read = index; e.nextElementSibling = new Element(); return e; });
  const radios = ['loved','ok','bored','scared','confused'].map(value => { const e = new Element(); e.value = value; return e; });
  const storage = new Map(Object.entries(saved));
  const spoken = [], downloads = [];
  const doc = new Element();
  doc.getElementById = id => ids[id] || null;
  doc.querySelectorAll = selector => ({'.page': pages, '[data-follow]': follows, '[data-read]': reads, 'input[name="reaction"]': radios}[selector]);
  doc.querySelector = () => radios.find(r => r.checked) || null;
  doc.createElement = () => { const e = new Element(); e.click = () => downloads.push(e.download); return e; };
  doc.body = {appendChild() {}};
  doc.documentElement = {style: {setProperty() {}}};
  let blob;
  const context = {document: doc, window: {speechSynthesis: {cancel() {}, getVoices: () => [], speak: u => spoken.push(u)}, scrollTo() {}, addEventListener() {}},
    SpeechSynthesisUtterance: class { constructor(text) { this.text = text; } },
    localStorage: {getItem: key => { if (deniedStorage) throw Error('unavailable'); return storage.get(key); },
      setItem: (key, value) => { if (deniedStorage) throw Error('unavailable'); storage.set(key, value); }},
    URL: {createObjectURL: value => { blob = value; return 'blob:test'; }, revokeObjectURL() {}}, Blob, setTimeout() {}, Date};
  context.window.SpeechSynthesisUtterance = context.SpeechSynthesisUtterance;
  vm.runInNewContext(source, context);
  return {ids, pages, follows, reads, radios, storage, spoken, downloads, doc, feedback: async () => JSON.parse(await blob.text())};
}
(async () => {
  const test = start();
  const {ids, pages, follows, reads, radios} = test;
  assert.equal(pages.length, 12);
  assert.equal(test.spoken.length, 0, 'No automatic speech on load');
  ids.next.click(); assert.equal(ids['page-count'].textContent, '2 / 12'); assert.equal(pages[1].hidden, false);
  reads[0].click(); assert.equal(test.spoken[0].lang, 'zh-CN'); assert.equal(test.spoken[0].rate, 0.9);
  assert.equal(test.spoken[0].text, payload.narrations['1'][0].text);
  const key = (value, target = new Element()) => test.doc.fire('keydown', {key: value, target, preventDefault() {}});
  key('ArrowRight'); assert.equal(ids['page-count'].textContent, '3 / 12');
  const input = new Element(); input.closest = () => input;
  key('ArrowRight', input); assert.equal(ids['page-count'].textContent, '3 / 12', 'Typing does not turn pages');
  key('ArrowLeft'); assert.equal(ids['page-count'].textContent, '2 / 12');
  ids['book-pages'].fire('touchstart', {touches: [{clientX: 300, clientY: 100}]});
  ids['book-pages'].fire('touchend', {changedTouches: [{clientX: 100, clientY: 110}]});
  assert.equal(ids['page-count'].textContent, '3 / 12');
  ids['book-pages'].fire('touchstart', {touches: [{clientX: 100, clientY: 100}]});
  ids['book-pages'].fire('touchend', {changedTouches: [{clientX: 170, clientY: 300}]});
  assert.equal(ids['page-count'].textContent, '3 / 12', 'Vertical scroll does not turn pages');
  ids.next.click(); follows[0].click(); follows[0].click();
  assert.equal(follows[0].attributes['aria-pressed'], 'true');
  assert.match(follows[0].textContent, /已选/);
  ids['child-words'].value = ' 孩子的原话\n'; ids['child-words'].fire('input');
  ids['parent-note'].value = '明天再看看'; ids['parent-note'].fire('input');
  radios[0].checked = true; radios[0].fire('change');
  while (!ids.next.disabled) ids.next.click();
  assert.equal(ids['page-count'].textContent, '12 / 12');
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
  assert.equal(reload.ids['child-words'].value, ' 孩子的原话\n'); assert.equal(reload.radios[0].checked, true);
  const blocked = start({deniedStorage: true}); blocked.follows[1].click(); blocked.ids['export-feedback'].click();
  assert.deepEqual((await blocked.feedback()).follow_ups_tapped, [payload.followUps[1]]);
  const english = start({data: {...payload, narrations: {'1': [{text:'Hello', lang:'en-US'}]}}});
  english.reads[0].click(); assert.equal(english.spoken[0].lang, 'en-US');
  const bilingual = start({data: {...payload, narrations: {'1': [{text:'你好', lang:'zh-CN'}, {text:'Hello', lang:'en-US'}]}}});
  bilingual.reads[0].click(); bilingual.spoken[0].onend(); assert.equal(bilingual.spoken[1].lang, 'en-US');
  console.log('通过：翻页、键盘/输入框、滑动、无自动朗读、zh/en/双语朗读参数、追问去重、localStorage 恢复、反馈全部字段、存储被禁用时导出。');
  console.log('独立 DOM 替身测试；不代表真实浏览器截图或实际听到声音。');
})().catch(error => { console.error(error); process.exitCode = 1; });
