# Editing the recording

Advice from editing real Microsoft 365 Copilot demos (PowerPoint, Excel, Notebooks) for executive workshops. Raw takes are 2-5 minutes; a good clip is 1-3 minutes.

## 1. Decide before you cut

- **One takeaway per clip**, written as an outcome: "A custom skill turns a deck into a committee check." Every segment either moves toward that outcome or goes.
- **Order:** outcome first (2-3 s still of the result), then the setup, the action, the result held long enough to read, and a short recap.
- **Landscape 16:9 at 1920x1080** is enough for workshops and internal sharing. Only make 9:16 or 1:1 versions for social channels.

## 2. Get a rough cut automatically

```powershell
python <skill>/scripts/cut-list.py --rough-cut          # all takes in .demo-recorder/timeline.jsonl
python <skill>/scripts/cut-list.py --marks recordings/x.marks.json --rough-cut   # capture-tab takes
```

`cut-list.py` writes `<take>.cuts.md` with a suggestion per segment and `<video>.rough.mp4`:

| Segment | Suggestion | Why |
|---|---|---|
| Idle time between actions (the agent deciding what to do next) | cut to 0.5 s | Nothing happens on screen |
| Action longer than 6 s (loading, Copilot generating) | speed up 6x, first and last second at 1x | Viewers see that it works and how long it roughly takes, without waiting |
| Action labelled `hold`, `read`, `show` or `pause` | keep | Deliberate reading time |

Label invoke steps with `-Mark` so the cut list reads like a script. Treat the rough cut as a starting point: watch it, then fine-tune.

## 3. What to keep on screen

- **Real UI choices.** Show the actual menus (for example *Add › Create manually / Upload / Record a skill*), not a description of them. Viewers trust what they can see.
- **What the agent used.** If a skill, file or prompt drives the result, show it for 3-4 s (open the skill text, zoom on the key lines).
- **Natural prompts.** Short, typed at human speed. Do not cut the typing completely; speed it up 2x if it is long.
- **Let the product do the clever part.** If Copilot picks the right skill on its own, do not name the skill in the prompt. Prove it afterwards instead ("Which skill did you use?") or show the indicator in the UI.
- **The result, held.** Hold 4-8 s on the finished output, zoomed if the text is small. If you only have time for one zoom, put it here.
- **Honest compression.** Speed up waits; do not hide that they exist. For executive audiences add a small label such as "about 40 s, sped up".

## 4. Overlays (less is more)

- Title: the outcome, at most 6 words. Captions: what just happened, at most 8 words, no full stop.
- Zoom 1.3-1.6x with an ease-in-out of about 0.5 s; one zoom per moment, never zoom while the user is typing.
- Silent first: the clip must work without sound. Add voice-over or quiet music only if the user asks.
- Explainer scenes must be concrete. Real before/after screenshots beat abstract icons; viewers could not follow generic illustrations.
- Branding: use the customer's colours and type for titles and lower thirds only; keep the product UI untouched. Use a customer logo only with permission.

## 5. Privacy pass (every final, every frame)

Check for sign-in names, e-mail addresses, tenant or SharePoint URLs, other people's files in recent lists, notifications and chat pop-ups. Blur or crop them (recipe below), or re-record. Fictional data only.

## 6. ffmpeg recipes

Set `$ff` to `ffmpeg` (or a full path). Times are in seconds.

```powershell
# Contact sheet: one still every 5 s, to review a take quickly
& $ff -i take.mp4 -vf "fps=1/5,scale=480:-1,tile=4x3" -frames:v 1 sheet.png

# Trim
& $ff -ss 12 -to 41.5 -i take.mp4 -c:v libx264 -crf 18 -pix_fmt yuv420p -an trimmed.mp4

# Speed up 20-52 s by 6x, keep the rest
& $ff -i take.mp4 -filter_complex "[0:v]trim=0:20,setpts=PTS-STARTPTS[a];[0:v]trim=20:52,setpts=(PTS-STARTPTS)/6[b];[0:v]trim=52,setpts=PTS-STARTPTS[c];[a][b][c]concat=n=3:v=1:a=0,fps=30[v]" -map "[v]" -c:v libx264 -crf 18 -pix_fmt yuv420p sped.mp4

# Blur a region (x=1300, y=10, 600x40), for example a sign-in name
& $ff -i take.mp4 -filter_complex "[0:v]split[m][c];[c]crop=600:40:1300:10,boxblur=10[b];[m][b]overlay=1300:10" -c:v libx264 -crf 18 -pix_fmt yuv420p blurred.mp4

# Short GIF for step-by-step docs (keep under ~3 MB)
& $ff -ss 10 -t 6 -i take.mp4 -vf "fps=10,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=4" -loop 0 step.gif

# Final export for web pages and Teams
& $ff -i edit.mp4 -c:v libx264 -crf 20 -preset slow -pix_fmt yuv420p -movflags +faststart final.mp4
```

## 7. Polished edits

For zooms, captions, title cards and branded explainers, hand the raw takes and the cut list to a video-editing skill if one is installed (for example a Remotion-based `demo-video-edit` skill). Give it the takeaway, the cut list and the brand colours, and review its proposals before it renders.

## 8. QA before sharing

- Watch the final once at 1x, full screen, without sound.
- Check the length against the plan and that every claim in a caption is visible on screen.
- Make a contact sheet of the final and run the privacy pass on it.
