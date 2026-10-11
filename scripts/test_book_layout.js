// Actual Chromium layout acceptance, using only Node.js standard libraries.
// Usage: node scripts/test_book_layout.js /tmp/sample.html /path/to/chrome
// Screenshots and measured results are saved in a temporary directory.
const {spawn} = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const assert = require('node:assert/strict');

const html = path.resolve(process.argv[2] || '/tmp/sample.html');
const chrome = process.argv[3] || process.env.CHROME_BIN ||
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const output = fs.mkdtempSync(path.join(os.tmpdir(), 'curiosity-layout-'));
const profile = path.join(output, 'profile');
const child = spawn(chrome, ['--headless', '--no-first-run', '--no-default-browser-check',
  '--disable-background-networking', '--remote-debugging-pipe', `--user-data-dir=${profile}`,
  'about:blank'], {stdio: ['ignore', 'ignore', 'pipe', 'pipe', 'pipe']});
let sequence = 0, buffer = '', logs = '';
const pending = new Map();
let loaded;
function fail(error) {
  for (const {reject, timer} of pending.values()) { clearTimeout(timer); reject(error); }
  pending.clear();
}
child.stderr.on('data', bytes => { logs = (logs + bytes.toString()).slice(-3000); });
child.on('error', fail);
child.on('exit', (code, signal) => fail(new Error(`Chromium exited: ${code ?? signal}\n${logs}`)));
child.stdio[3].on('error', fail);
child.stdio[4].on('data', bytes => {
  buffer += bytes.toString();
  let boundary;
  while ((boundary = buffer.indexOf('\0')) >= 0) {
    const raw = buffer.slice(0, boundary); buffer = buffer.slice(boundary + 1);
    if (!raw) continue;
    const message = JSON.parse(raw), request = pending.get(message.id);
    if (message.method === 'Page.loadEventFired' && loaded) { loaded(); loaded = null; }
    if (!request) continue;
    pending.delete(message.id); clearTimeout(request.timer);
    if (message.error) request.reject(new Error(JSON.stringify(message.error)));
    else request.resolve(message.result);
  }
});
function send(method, params = {}, sessionId) {
  return new Promise((resolve, reject) => {
    const id = ++sequence;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`Timed out: ${method}`)); }, 10000);
    pending.set(id, {resolve, reject, timer});
    child.stdio[3].write(JSON.stringify({id, method, params, sessionId}) + '\0');
  });
}
(async () => {
  await send('Browser.getVersion');
  const {targetId} = await send('Target.createTarget', {url:'about:blank'});
  const {sessionId} = await send('Target.attachToTarget', {targetId, flatten:true});
  const call = (method, params) => send(method, params, sessionId);
  const evaluate = async expression => {
    const result = await call('Runtime.evaluate', {expression, awaitPromise:true, returnByValue:true});
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  };
  await call('Page.enable');
  let loadTimer;
  const load = new Promise((resolve, reject) => {
    loaded = () => { clearTimeout(loadTimer); resolve(); };
    loadTimer = setTimeout(() => reject(new Error('Navigation timed out')), 10000);
  });
  await call('Page.navigate', {url:pathToFileURL(html).href});
  await load;
  // Wait for this document's inline script and fonts, rather than measuring an
  // unfinished navigation. A ten-second CDP timeout also bounds this wait.
  await evaluate(`new Promise(resolve => {
    const ready = () => document.getElementById('next') && document.readyState === 'complete'
      ? document.fonts.ready.then(() => resolve(true)) : setTimeout(ready, 20);
    ready();
  })`);
  await evaluate("document.getElementById('next').click()");
  const results = [];
  const viewports = [[1280,800],[1366,768],[1440,900],[1920,1080],[768,1024],[768,680],[375,812]];
  for (const [width, height] of viewports) {
    await call('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor:1, mobile:false});
    const measurement = await evaluate(`new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => {
      const page = document.querySelector('.story:not([hidden])');
      const picture = page.querySelector('.picture').getBoundingClientRect();
      resolve({width:innerWidth, height:innerHeight, scrollHeight:document.documentElement.scrollHeight,
        scrollWidth:document.documentElement.scrollWidth,
        readBottom:page.querySelector('.read-button').getBoundingClientRect().bottom,
        footerBottom:document.querySelector('footer').getBoundingClientRect().bottom,
        pictureWidth:picture.width, pictureHeight:picture.height,
        narrationSize:parseFloat(getComputedStyle(page.querySelector('.narration')).fontSize)});
    })))`);
    results.push(measurement);
    console.log(JSON.stringify(measurement));
    assert.equal(measurement.width, width); assert.equal(measurement.height, height);
    assert.ok(measurement.scrollWidth <= width, 'No horizontal overflow');
    assert.ok(Math.abs(measurement.pictureWidth / measurement.pictureHeight - 1.5) < .01, 'Picture remains 3:2');
    if (width >= 768) {
      assert.ok(measurement.scrollHeight <= height, 'Story fits without scrolling');
      assert.ok(measurement.readBottom < height, 'Read button is visible');
      assert.ok(measurement.footerBottom <= height, 'Navigation is visible');
    } else assert.ok(measurement.narrationSize >= 20, 'Mobile narration remains readable');
    const shot = await call('Page.captureScreenshot', {format:'png', captureBeyondViewport:false});
    fs.writeFileSync(path.join(output, `${width}x${height}.png`), Buffer.from(shot.data, 'base64'));
  }
  fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify(results, null, 2));
  console.log(`通过：实际浏览器布局；截图和数据：${output}`);
})().catch(error => { console.error(`未通过：${error.message}`); process.exitCode = 1; })
  .finally(() => { child.kill(); fs.rmSync(profile, {recursive:true, force:true}); });
