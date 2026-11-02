# Troubleshooting

Each fix here came from a real recording session.

## Browser

| Symptom | Cause | Fix |
|---|---|---|
| `browser.cjs` cannot connect | Edge was started without the debugging port, or another Edge already uses the profile | Close all windows of the demo profile and run `start-browser.ps1` again |
| "Could not attach to Edge" on the first run of a new profile | On a managed PC, Edge opens a sync confirmation or sign-in dialog that blocks automation | Close the dialog in the demo window and retry. If Edge signed the profile into your work account, sign that profile into the demo tenant instead |
| "Dedicated demo window is gone" | The window was closed | `node browser.cjs init <url>` |
| Office app renders wider than the window; side panes are cut off in OBS | Leftover viewport/device-metrics emulation from an earlier automation session | `node browser.cjs fix-size`, then reload the page |
| Clicks land in the wrong place | Window is on a monitor with different scaling | Use `ctx.click(locator)` (DOM click) or move the window to the primary monitor |
| Copilot pane not found | The pane is a cross-origin iframe that loads late | Wait for it: poll `ctx.copilotPane()` for up to 30 s after opening Copilot |
| Locator times out after a UI update | Labels changed | Run `browser.cjs inspect` and use the real role and name |

## OBS

| Symptom | Cause | Fix |
|---|---|---|
| "Expected exactly one window" | Several windows share the title, or the title changed (Edge adds "and N more pages") | Keep one tab in the dedicated window and match a unique part of the document title; switch the window source after navigating to a new document |
| Black or stale image | Window capture method or minimised window | Keep the window visible and not minimised; `setup` uses Windows 10+ capture (method 2) |
| Only part of the app is visible | Physical window size differs from 1920×1080 | `browser.cjs fix-size`, then `record.py window ...` again to refit |
| `stop` cannot rename the file | OBS still holds the file briefly | `record.py` retries for 30 s; otherwise rename manually |
| Authentication error | WebSocket auth is enabled | Set `OBS_WEBSOCKET_PASSWORD` in the environment |
| Your normal OBS setup changed | A session was not restored | `python record.py restore` (it reads `.demo-recorder/obs-state.json`) |

## Microsoft 365 specifics

- **Read-only document or "We repaired your presentation"**: use **File › Save a copy** and record in the copy.
- **Copilot only answers in chat instead of editing**: turn on **Allow editing** in the Copilot pane.
- **Custom skills**: after uploading, open **Custom skills** and wait for the skill to appear (select **Refresh** if needed) before sending the request. A request sent before discovery finished produced a generic answer.
- **Fresh state per take**: create a new copy of the practice file for each take so earlier output does not change Copilot's behaviour.
- **Long generations**: wait for the Stop button to disappear before the next action; trim the wait in editing.

## Screencast fallback

- Frames only arrive while the tab is visible; keep the window in front.
- The capture starts when the script starts. Navigate and open panes before running `capture-tab.cjs` if the first frame matters.
- `ffmpeg` must be on PATH, or pass `--ffmpeg`.
