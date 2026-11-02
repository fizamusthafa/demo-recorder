---
name: record-authenticated-demo
description: "Record a real product demo (Microsoft 365, Copilot in Word/Excel/PowerPoint, Teams, SharePoint, any SaaS) in a signed-in external Edge window driven by Playwright over CDP and captured with OBS or an exact-tab screencast. Use when asked to record, film, screen-capture or automate a demo in an authenticated browser, use OBS, use an external/real browser instead of a test browser, or produce raw footage for a demo video."
---

# Record an authenticated demo

You drive **one dedicated window** in a real, signed-in Edge profile and record **only that window**. The user signs in once by hand; you never see or type credentials. Every action is logged with OBS timecodes so the footage is easy to edit later.

All helper scripts are in this skill's `scripts/` folder. Runtime state (window id, controller token, timeline, OBS backup) goes in `.demo-recorder/` in the current directory. Raw recordings go in `recordings/` unless the user names another folder.

## Workflow

```
preflight → browser → OBS setup → framing check → rehearse → record (per take) → verify → restore
```

### 0. Preflight (once per machine)

```powershell
Push-Location <skill>/scripts; npm install; Pop-Location   # playwright-core (--prefix fails on Windows)
python -m pip install -r <skill>/scripts/requirements.txt   # websocket-client
```

OBS 28+ with **Tools › WebSocket Server Settings › Enable** (port 4455). If authentication is on, ask the user to set `OBS_WEBSOCKET_PASSWORD` in their environment; never ask them to paste it into chat. `ffmpeg` on PATH is only needed for the screencast fallback.

### 1. Start the browser

```powershell
<skill>/scripts/start-browser.ps1            # Edge on 127.0.0.1:9333 with a dedicated profile
node <skill>/scripts/browser.cjs init https://www.office.com
```

`init` opens a new 1920×1080 window and remembers it. If this is the first run, **stop and ask the user to sign in** in that window. Then:

```powershell
node <skill>/scripts/browser.cjs serve       # run in the background (async); keep it running
```

The `demo-browser` MCP server from this plugin connects to the same Edge, so you can also use Playwright MCP tools for exploration. Use `invoke.ps1` for anything you record, because it writes timeline marks.

### 2. Set up OBS

```powershell
python <skill>/scripts/record.py setup --out recordings      # saves current OBS settings first
python <skill>/scripts/record.py window "<unique part of the tab title>"
python <skill>/scripts/record.py shot preflight
```

**Look at `.demo-recorder/preflight.png` before recording.** The whole app and its side panes must be visible, sharp and not cropped. Fix framing first (see troubleshooting); a misframed take is wasted time.

`setup` mutes Desktop Audio and Mic/Aux so notifications and voices are not recorded; add `--audio` only if the demo needs the page's own sound (for example, playing an audio overview).

### 3. Rehearse, then record

Rehearse each step without recording. Check the real UI text with `browser.cjs inspect` and use role/name locators from it; never guess labels. Then, per take:

```powershell
python <skill>/scripts/record.py start
<skill>/scripts/invoke.ps1 -ScriptPath step-01-open-menu.js
<skill>/scripts/invoke.ps1 -Code 'await ctx.hold(4000); return await page.title();' -Mark "hold result"
python <skill>/scripts/record.py stop powerpoint-import
```

Action scripts receive `page`, `browser` and `ctx` (`ctx.hold(ms)`, `ctx.click(locator)`, `ctx.frame(match)`, `ctx.copilotPane()`, `ctx.root`). Write them like a human uses the app:

- Type prompts with `pressSequentially(text, { delay: 70-100 })`; short, natural prompts.
- Hold 4-8 s on anything the viewer must read (menus, skill text, results). Editing removes waits later; it cannot add missing reading time.
- Prefer `ctx.click(locator)` (DOM click) when the browser is on a second monitor; pointer clicks can land in the wrong place.
- One outcome per take. Stop the take and re-record rather than recording troubleshooting.

### 4. Fallback: record the tab itself

If OBS is unavailable or the window title is ambiguous, record the dedicated tab directly:

```powershell
node <skill>/scripts/capture-tab.cjs --script take.js --out recordings/excel-review.mp4
```

Use `ctx.mark('label')` in the script; marks are saved to `<name>.marks.json`. Prepare the page *before* the capture starts so the take begins on the right screen.

### 5. Verify and restore

- Check every take: duration, a contact sheet or 3-4 stills across the timeline, and that the outcome the demo claims is visible on screen.
- Save the produced artefacts (files, workbooks, decks) if the demo creates them, and verify them independently.
- **Always** run `python <skill>/scripts/record.py restore` when finished, even after a failure. Stop the controller and run `browser.cjs close`.

`.demo-recorder/timeline.jsonl` has before/after OBS timecodes for every action. Use it to choose edit points (for example with a demo-video editing skill).

## Rules

- Never type, read aloud, screenshot or store passwords, MFA codes or tokens. If sign-in or consent is needed, pause and ask the user.
- Use test tenants and fictional data. Before recording, close unrelated tabs and check the frame for e-mail addresses, customer names, URLs or notifications that should not be shared.
- Record only the dedicated window. Do not switch OBS to display capture without asking.
- Do not change tenant, admin or security settings to make a demo work.
- Never present a failed or partial result as success. If the product behaves differently from the plan, show what actually happened or re-plan the take.
- Keep the debugging port on 127.0.0.1 and close the browser when done; anyone with access to the port controls the signed-in session.

For known problems and fixes, read [references/troubleshooting.md](references/troubleshooting.md).
