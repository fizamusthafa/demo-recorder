// Controls ONE dedicated window in the external, signed-in Edge over CDP.
//   node browser.cjs init [url]          open a dedicated 1920x1080 window and remember it
//   node browser.cjs goto <url>
//   node browser.cjs fix-size            undo viewport emulation and restore 1920x1080
//   node browser.cjs inspect [chars]     print visible text of the page and app frames
//   node browser.cjs screenshot <file>
//   node browser.cjs eval <file.js>      run an action script: (page, browser, ctx) => ...
//   node browser.cjs serve               loopback controller used by invoke.ps1
//   node browser.cjs close               close the dedicated window
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const http = require('node:http');
const { chromium } = require('playwright-core');

const port = Number(process.env.DEMO_CDP_PORT || 9333);
const home = path.resolve(process.env.DEMO_RECORDER_HOME || '.demo-recorder');
const stateFile = path.join(home, 'browser.json');
const controlFile = path.join(home, 'control.json');
fs.mkdirSync(home, { recursive: true });

async function dedicatedPage(browser, create) {
  const cdp = await browser.newBrowserCDPSession();
  let state = fs.existsSync(stateFile) ? JSON.parse(fs.readFileSync(stateFile, 'utf8')) : null;
  if (create || !state) {
    const { targetId } = await cdp.send('Target.createTarget', { url: 'about:blank', newWindow: true });
    const { windowId } = await cdp.send('Browser.getWindowForTarget', { targetId });
    state = { targetId, windowId };
    fs.writeFileSync(stateFile, JSON.stringify(state, null, 2));
  }
  // A freshly created target reaches Playwright's page list asynchronously.
  for (let attempt = 0; attempt < 40; attempt++) {
    for (const page of browser.contexts().flatMap((c) => c.pages())) {
      const session = await page.context().newCDPSession(page);
      const info = await session.send('Target.getTargetInfo');
      await session.detach();
      if (info.targetInfo.targetId === state.targetId) return { page, cdp, state };
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw Error('The dedicated demo window is gone. Run: node browser.cjs init');
}

async function connect() {
  try {
    return await chromium.connectOverCDP(`http://127.0.0.1:${port}`, { timeout: 20000 });
  } catch (error) {
    throw Error(`Could not attach to Edge on 127.0.0.1:${port}. If Edge shows a dialog (sync, sign-in, restore pages), close it and retry. ${error.message.split('\n')[0]}`);
  }
}

async function fixSize(page, cdp, state) {
  await cdp.send('Browser.setWindowBounds', { windowId: state.windowId, bounds: { windowState: 'normal' } });
  await cdp.send('Browser.setWindowBounds', { windowId: state.windowId, bounds: { left: 0, top: 0, width: 1920, height: 1080 } });
  const session = await page.context().newCDPSession(page);
  // Leftover emulation makes Office apps render wider than the real window.
  await session.send('Emulation.clearDeviceMetricsOverride');
  await session.detach();
  return page.evaluate(() => ({ inner: [innerWidth, innerHeight], outer: [outerWidth, outerHeight], dpr: devicePixelRatio }));
}

async function runScript(code, page, browser) {
  const helpers = {
    root: process.cwd(),
    home,
    fs,
    path,
    hold: (ms) => page.waitForTimeout(ms),
    frame: (match) => page.frames().find((f) => f.name().includes(match) || f.url().includes(match)),
    copilotPane: () => page.frames().find((f) => f.url().includes('taskpane')),
    click: (locator) => locator.evaluate((e) => e.click()),
  };
  const action = new Function('page', 'browser', 'ctx', `return (async () => {${code}\n})();`);
  return action(page, browser, helpers);
}

async function main() {
  const [command, ...args] = process.argv.slice(2);
  const browser = await connect();
  try {
    const { page, cdp, state } = await dedicatedPage(browser, command === 'init');
    page.setDefaultTimeout(30000);
    await page.bringToFront();
    if (command === 'init') {
      console.log(JSON.stringify(await fixSize(page, cdp, state)));
      if (args[0]) await page.goto(args[0], { waitUntil: 'domcontentloaded', timeout: 60000 });
    } else if (command === 'goto') {
      await page.goto(args[0], { waitUntil: 'domcontentloaded', timeout: 60000 });
      console.log(JSON.stringify({ title: await page.title(), url: page.url() }));
    } else if (command === 'fix-size') {
      console.log(JSON.stringify(await fixSize(page, cdp, state)));
    } else if (command === 'inspect') {
      const limit = Number(args[0] || 4000);
      for (const f of page.frames()) {
        const text = await f.locator('body').innerText().catch(() => '');
        if (text.trim()) console.log(`--- ${f === page.mainFrame() ? 'main' : f.name() || f.url().split('?')[0]}\n${text.slice(0, limit)}`);
      }
    } else if (command === 'screenshot') {
      await page.screenshot({ path: path.resolve(args[0] || path.join(home, 'browser.png')) });
    } else if (command === 'eval') {
      const result = await runScript(fs.readFileSync(args[0], 'utf8'), page, browser);
      if (result !== undefined) console.log(JSON.stringify(result, null, 2));
    } else if (command === 'close') {
      await cdp.send('Target.closeTarget', { targetId: state.targetId });
      fs.rmSync(stateFile, { force: true });
    } else if (command === 'serve') {
      const token = crypto.randomBytes(24).toString('hex');
      const controlPort = Number(process.env.DEMO_CONTROL_PORT || 9341);
      const server = http.createServer(async (req, res) => {
        if (req.method !== 'POST' || req.headers.authorization !== `Bearer ${token}`) { res.writeHead(403); res.end(); return; }
        let body = '';
        for await (const chunk of req) body += chunk;
        try {
          const result = await runScript(JSON.parse(body).script, page, browser);
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ ok: true, result }));
        } catch (error) {
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ ok: false, error: String(error) }));
        }
      });
      await new Promise((resolve) => server.listen(controlPort, '127.0.0.1', resolve));
      fs.writeFileSync(controlFile, JSON.stringify({ port: controlPort, token }));
      console.log(`Controller ready on 127.0.0.1:${controlPort}. Stop with Ctrl+C.`);
      const stop = () => { fs.rmSync(controlFile, { force: true }); server.close(); process.exit(0); };
      process.once('SIGINT', stop);
      process.once('SIGTERM', stop);
      await new Promise(() => {});
    } else {
      throw Error(`Unknown command: ${command}`);
    }
  } finally {
    if (command !== 'serve') await browser.close();
  }
}

main().catch((error) => { console.error(error.message || error); process.exitCode = 1; });
