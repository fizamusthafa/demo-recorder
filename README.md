# demo-recorder

A GitHub Copilot plugin for recording **real product demos in a signed-in browser**.

Copilot drives one dedicated window in your own Edge profile (you sign in once, by hand) and records just that window with OBS. Every action is logged with OBS timecodes, so the raw footage is easy to cut afterwards. If OBS is not available, it can record the browser tab directly.

It contains:

| Part | What it does |
|---|---|
| Skill `record-authenticated-demo` | The workflow, safety rules and lessons learned, plus helper scripts |
| MCP server `demo-browser` | Playwright MCP connected to the same Edge over CDP (`127.0.0.1:9333`) |
| MCP server `obs` | [obs-mcp](https://www.npmjs.com/package/obs-mcp) for ad-hoc OBS control (`127.0.0.1:4455`) |

Windows is supported for OBS window capture. The screencast fallback also works on macOS and Linux.

## Install

```powershell
copilot plugin marketplace add fizamusthafa/demo-recorder
copilot plugin install demo-recorder@demo-recorder
```

Restart Copilot afterwards. Check with `copilot plugin list`. Get later versions with `copilot plugin update demo-recorder@demo-recorder`.

`copilot plugin install fizamusthafa/demo-recorder` also works, but Copilot marks direct repo installs as deprecated.

## One-time setup

1. **Node.js 20+ and Python 3.10+.**
2. **OBS Studio 28+**: *Tools › WebSocket Server Settings › Enable WebSocket server* (port 4455). If you enable authentication, set the password as an environment variable, not in chat:
   ```powershell
   setx OBS_WEBSOCKET_PASSWORD "your-password"
   ```
3. **Script dependencies**. Copilot runs these the first time, or you can:
   ```powershell
   $skill = (Get-ChildItem "$env:USERPROFILE\.copilot\installed-plugins" -Recurse -Directory -Filter record-authenticated-demo | Select-Object -First 1).FullName
   Push-Location "$skill\scripts"; npm install; Pop-Location
   python -m pip install -r "$skill\scripts\requirements.txt"
   ```
4. Optional: **ffmpeg** on PATH for the tab-screencast fallback and rough cuts.

## Use it

Ask Copilot, for example:

> Record a demo of uploading a custom skill in PowerPoint for the web and asking "Do a committee readiness check". Use my demo tenant.

Copilot will start Edge with a dedicated profile, ask you to sign in the first time, set up OBS, show you a framing check, then record take by take. When it finishes it restores your OBS settings.

Raw videos land in `recordings/`; timeline marks in `.demo-recorder/timeline.jsonl`.

## Editing

Ask Copilot for a rough cut, or run it yourself:

```powershell
python "$skill\scripts\cut-list.py" --rough-cut
```

It writes a cut list per take (cut idle time, speed up long waits, keep reading time) and renders `<take>.rough.mp4` with ffmpeg. [The editing guide](skills/record-authenticated-demo/references/editing.md) covers clip structure, what to keep on screen, overlays, a privacy pass and tested ffmpeg recipes (trim, speed-up, blur, GIF, contact sheet).

## Safety

- Copilot never types or stores credentials; you sign in yourself.
- The browser debugging port and controller listen on `127.0.0.1` only. Close the demo browser when you are done.
- Use a demo tenant and fictional data. Check each frame for e-mail addresses, names and notifications before sharing a video.

## Update or remove

```powershell
copilot plugin update demo-recorder@demo-recorder
copilot plugin uninstall demo-recorder
```

The Edge profile is in `%LOCALAPPDATA%\demo-recorder\edge-profile`; delete it to sign out completely.
