"""Turn the recording timeline into a per-take cut list for editing.

    python cut-list.py                                   reads .demo-recorder/timeline.jsonl
    python cut-list.py --marks recordings/x.marks.json   reads marks from capture-tab.cjs
    python cut-list.py --slow 6 --gap 1.5 --out cuts/ --rough-cut

For each take it writes <take>.cuts.md (a table to read) and <take>.cuts.json (for tools).
Each segment gets a suggestion: keep, cut (idle time between actions) or speed up (a long
action such as a Copilot generation). Suggestions are based on timing only; check the
frames before you cut.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sys

HOLD = re.compile(r"\b(hold|read|show|pause)", re.I)


def ts(entry):
    return datetime.fromisoformat(entry["utc"].replace("Z", "+00:00"))


def clock(seconds):
    m, s = divmod(max(seconds, 0), 60)
    return f"{int(m):02d}:{s:05.2f}"


def takes_from_timeline(path):
    entries = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    takes, current = [], None
    for entry in entries:
        if entry.get("phase") == "take-start":
            current = {"start": ts(entry), "events": []}
        elif entry.get("phase") == "take-stop" and current:
            current.update(name=entry.get("label", f"take-{len(takes) + 1}"), file=entry.get("file"),
                           duration=(ts(entry) - current["start"]).total_seconds())
            takes.append(current)
            current = None
        elif current and entry.get("phase") in ("before", "after"):
            rec = entry.get("recording") or {}
            t = rec["outputDuration"] / 1000 if rec.get("outputActive") and "outputDuration" in rec \
                else (ts(entry) - current["start"]).total_seconds()
            current["events"].append((entry["phase"], entry.get("label", "action"), t))
    for take in takes:
        segments, cursor, opened = [], 0.0, None
        for phase, label, t in take["events"]:
            if phase == "before":
                if t > cursor:
                    segments.append({"label": "(between actions)", "start": cursor, "end": t, "kind": "gap"})
                opened = (label, t)
            elif opened:
                segments.append({"label": opened[0], "start": opened[1], "end": t, "kind": "action"})
                cursor, opened = t, None
        if take["duration"] > cursor:
            segments.append({"label": "(after last action)", "start": cursor, "end": take["duration"], "kind": "gap"})
        take["segments"] = segments
    return takes


def takes_from_marks(path):
    marks = json.loads(path.read_text(encoding="utf-8"))
    name = path.name.replace(".marks.json", "")
    segments, previous = [], {"label": "(start)", "seconds": 0.0}
    for mark in marks:
        if mark["seconds"] > previous["seconds"]:
            segments.append({"label": previous["label"], "start": previous["seconds"], "end": mark["seconds"], "kind": "action"})
        previous = mark
    video = path.with_name(name + ".mp4")
    return [{"name": name, "file": str(video), "duration": previous["seconds"], "segments": segments}]


def suggest(segment, slow, gap):
    length = segment["end"] - segment["start"]
    if segment["kind"] == "gap":
        return "cut, keep 0.5 s" if length > gap else "keep"
    if HOLD.search(segment["label"]):
        return "keep (reading time)"
    if length > slow:
        return "speed up 4-8x; keep first and last second"
    return "keep"


def rough_cut(take, ffmpeg, speed):
    """Render <file>.rough.mp4: idle gaps shortened to 0.5 s, slow actions sped up (first/last second at 1x)."""
    import subprocess
    pieces = []
    for s in take["segments"]:
        start, end = s["start"], s["end"]
        if s["suggestion"].startswith("cut"):
            pieces.append((start, start + 0.5, 1))
        elif s["suggestion"].startswith("speed"):
            pieces += [(start, start + 1, 1), (start + 1, end - 1, speed), (end - 1, end, 1)]
        else:
            pieces.append((start, end, 1))
    merged = []
    for piece in pieces:
        if merged and merged[-1][2] == piece[2] == 1 and abs(merged[-1][1] - piece[0]) < 0.01:
            merged[-1] = (merged[-1][0], piece[1], 1)
        elif piece[1] - piece[0] > 0.05:
            merged.append(piece)
    chains = [f"[0:v]trim={a:.3f}:{b:.3f},setpts=(PTS-STARTPTS)/{k}[p{i}]" for i, (a, b, k) in enumerate(merged)]
    graph = ";".join(chains) + ";" + "".join(f"[p{i}]" for i in range(len(merged))) + \
        f"concat=n={len(merged)}:v=1:a=0,fps=30,format=yuv420p[v]"
    source = Path(take["file"])
    target = source.with_name(source.stem + ".rough.mp4")
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), "-filter_complex", graph,
                    "-map", "[v]", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-movflags", "+faststart",
                    str(target)], check=True)
    return target


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    home = Path(os.environ.get("DEMO_RECORDER_HOME", ".demo-recorder"))
    parser.add_argument("--timeline", type=Path, default=home / "timeline.jsonl")
    parser.add_argument("--marks", type=Path, help="marks.json written by capture-tab.cjs")
    parser.add_argument("--slow", type=float, default=6.0, help="actions longer than this (s) are speed-up candidates")
    parser.add_argument("--gap", type=float, default=1.5, help="idle time longer than this (s) is a cut candidate")
    parser.add_argument("--out", type=Path, default=home)
    parser.add_argument("--rough-cut", action="store_true", help="also render <video>.rough.mp4 with ffmpeg (no audio)")
    parser.add_argument("--speed", type=int, default=6, help="speed factor for slow actions in the rough cut")
    parser.add_argument("--ffmpeg", default=os.environ.get("FFMPEG", "ffmpeg"))
    a = parser.parse_args()
    source = a.marks or a.timeline
    if not source.exists():
        raise SystemExit(f"{source} not found. Record with invoke.ps1 / record.py, or pass --marks.")
    takes = takes_from_marks(a.marks) if a.marks else takes_from_timeline(a.timeline)
    if not takes:
        raise SystemExit("No complete takes in the timeline (record.py start ... stop <name>).")
    a.out.mkdir(parents=True, exist_ok=True)
    for take in takes:
        saved = 0.0
        for s in take["segments"]:
            s["suggestion"] = suggest(s, a.slow, a.gap)
            length = s["end"] - s["start"]
            if s["suggestion"].startswith("cut"):
                saved += max(length - 0.5, 0)
            elif s["suggestion"].startswith("speed"):
                saved += max(length - 2, 0) * 0.8
        estimate = take["duration"] - saved
        rows = "\n".join(f"| {clock(s['start'])} | {clock(s['end'])} | {s['end'] - s['start']:.1f} s | {s['label']} | {s['suggestion']} |"
                         for s in take["segments"])
        md = (f"# Cut list: {take['name']}\n\nFile: `{take.get('file')}`  \n"
              f"Raw length {clock(take['duration'])}; about {clock(estimate)} after the suggested cuts.\n\n"
              f"| In | Out | Length | Segment | Suggestion |\n|---|---|---|---|---|\n{rows}\n")
        (a.out / f"{take['name']}.cuts.md").write_text(md, encoding="utf-8")
        (a.out / f"{take['name']}.cuts.json").write_text(json.dumps(
            {k: take[k] for k in ("name", "file", "duration", "segments")}, indent=2), encoding="utf-8")
        print(f"{a.out / (take['name'] + '.cuts.md')}  raw {clock(take['duration'])} -> about {clock(estimate)}")
        if a.rough_cut:
            if not take.get("file") or not Path(take["file"]).exists():
                print(f"  skipped rough cut: video not found ({take.get('file')})")
            else:
                print(f"  rough cut: {rough_cut(take, a.ffmpeg, a.speed)}")


if __name__ == "__main__":
    main()
