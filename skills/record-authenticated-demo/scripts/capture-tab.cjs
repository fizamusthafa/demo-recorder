// Records the dedicated browser tab itself (no OBS, no window-title matching) while an
// action script runs, then encodes an H.264 MP4 at 30 fps with ffmpeg.
//   node capture-tab.cjs --script actions.js --out demo.mp4 [--ffmpeg C:\path\ffmpeg.exe]
// The action script is an async function body (no module.exports) with `page` and `ctx` in
// scope: ctx.mark(label), ctx.hold(ms), ctx.click(locator).
// Marks are written next to the video as <name>.marks.json for editing.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { spawnSync } = require('node:child_process');
const { chromium } = require('playwright-core');

const args = Object.fromEntries(process.argv.slice(2).reduce((pairs, a, i, all) => (a.startsWith('--') ? [...pairs, [a.slice(2), all[i + 1]]] : pairs), []));
if (!args.script || !args.out) throw Error('Usage: node capture-tab.cjs --script actions.js --out demo.mp4');
const ffmpeg = args.ffmpeg || process.env.FFMPEG || 'ffmpeg';
const home = path.resolve(process.env.DEMO_RECORDER_HOME || '.demo-recorder');
const port = Number(process.env.DEMO_CDP_PORT || 9333);

async function main() {
  const state = JSON.parse(fs.readFileSync(path.join(home, 'browser.json'), 'utf8'));
  const browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`);
  const frameDir = fs.mkdtempSync(path.join(os.tmpdir(), 'demo-frames-'));
  const frames = [];
  const marks = [];
  let started = false;
  let cdp;
  try {
    let page;
    for (const candidate of browser.contexts()[0].pages()) {
      const s = await candidate.context().newCDPSession(candidate);
      const info = await s.send('Target.getTargetInfo');
      await s.detach();
      if (info.targetInfo.targetId === state.targetId) page = candidate;
    }
    if (!page) throw Error('Dedicated window not found. Run: node browser.cjs init');
    await page.bringToFront();
    cdp = await page.context().newCDPSession(page);
    const epoch = Date.now() / 1000;
    const ctx = {
      mark: (label) => marks.push({ label, seconds: Date.now() / 1000 - epoch }),
      hold: (ms) => page.waitForTimeout(ms),
      click: (locator) => locator.evaluate((e) => e.click()),
      frame: (match) => page.frames().find((f) => f.name().includes(match) || f.url().includes(match)),
    };
    cdp.on('Page.screencastFrame', (event) => {
      const file = path.join(frameDir, `f${String(frames.length).padStart(6, '0')}.jpg`);
      fs.writeFileSync(file, Buffer.from(event.data, 'base64'));
      frames.push({ file, seconds: event.metadata.timestamp - epoch });
      cdp.send('Page.screencastFrameAck', { sessionId: event.sessionId }).catch(() => {});
    });
    await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 92, maxWidth: 1920, maxHeight: 1080 });
    started = true;
    const action = new Function('page', 'ctx', `return (async () => {${fs.readFileSync(args.script, 'utf8')}\n})();`);
    await action(page, ctx);
    ctx.mark('end');
    await cdp.send('Page.stopScreencast');
    started = false;
    if (frames.length < 2) throw Error('No frames captured; is the window visible and not minimised?');
    const end = marks.at(-1).seconds;
    const list = frames.flatMap((f, i) => [`file '${f.file.replace(/\\/g, '/')}'`, `duration ${Math.max(0.001, (frames[i + 1]?.seconds ?? end) - f.seconds).toFixed(6)}`]);
    list.push(`file '${frames.at(-1).file.replace(/\\/g, '/')}'`);
    fs.writeFileSync(path.join(frameDir, 'list.txt'), list.join('\n'));
    const out = path.resolve(args.out);
    const r = spawnSync(ffmpeg, ['-y', '-hide_banner', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', path.join(frameDir, 'list.txt'),
      '-vf', 'fps=30,scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2',
      '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], { stdio: 'inherit' });
    if (r.error) throw Error(`ffmpeg not found (${r.error.message}); pass --ffmpeg or set FFMPEG`);
    if (r.status !== 0) throw Error(`ffmpeg failed with ${r.status}`);
    fs.writeFileSync(out.replace(/\.mp4$/i, '') + '.marks.json', JSON.stringify(marks, null, 2));
    console.log(`${out}: ${frames.length} frames over ${end.toFixed(1)} s`);
  } finally {
    if (started) await cdp.send('Page.stopScreencast').catch(() => {});
    fs.rmSync(frameDir, { recursive: true, force: true });
    await browser.close();
  }
}

main().catch((error) => { console.error(error.message || error); process.exitCode = 1; });
