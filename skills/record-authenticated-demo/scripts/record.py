"""OBS session for a demo recording. Saves your OBS settings first and restores them at the end.

    python record.py setup [--out DIR] [--audio]   save settings, create/select scene + window source, 1080p, mute mic/desktop
    python record.py window <title substring>      point the window source at exactly one matching window
    python record.py shot <name>                   save a still of the source to check framing BEFORE recording
    python record.py start
    python record.py stop <name>                   stop and rename the file to <name>.mp4/.mkv
    python record.py status
    python record.py restore                       put every saved OBS setting back
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from obs import request  # noqa: E402

HOME = Path(os.environ.get("DEMO_RECORDER_HOME", ".demo-recorder")).resolve()
STATE = HOME / "obs-state.json"
SCENE = os.environ.get("DEMO_OBS_SCENE", "Demo Recorder")
SOURCE = os.environ.get("DEMO_OBS_SOURCE", "Demo Browser")
AUDIO_INPUTS = ("Desktop Audio", "Mic/Aux")


def inputs():
    return {i["inputName"]: i for i in request("GetInputList")["inputs"]}


def setup(out, audio):
    if request("GetRecordStatus")["outputActive"]:
        raise SystemExit("OBS is already recording; stop it first.")
    if STATE.exists():
        raise SystemExit(f"A previous session was not restored. Run: python record.py restore ({STATE})")
    out.mkdir(parents=True, exist_ok=True)
    existing = inputs()
    state = {
        "scene": request("GetSceneList")["currentProgramSceneName"],
        "video": request("GetVideoSettings"),
        "directory": request("GetRecordDirectory")["recordDirectory"],
        "mutes": {n: request("GetInputMute", {"inputName": n})["inputMuted"] for n in AUDIO_INPUTS if n in existing},
        "createdScene": False,
        "sourceSettings": None,
    }
    scenes = [s["sceneName"] for s in request("GetSceneList")["scenes"]]
    if SCENE not in scenes:
        request("CreateScene", {"sceneName": SCENE})
        state["createdScene"] = True
    if SOURCE in existing:
        state["sourceSettings"] = request("GetInputSettings", {"inputName": SOURCE})["inputSettings"]
    else:
        request("CreateInput", {"sceneName": SCENE, "inputName": SOURCE, "inputKind": "window_capture",
                                "inputSettings": {"method": 2, "cursor": True, "client_area": True, "capture_audio": audio}})
    HOME.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    request("SetVideoSettings", {"baseWidth": 1920, "baseHeight": 1080, "outputWidth": 1920, "outputHeight": 1080})
    request("SetRecordDirectory", {"recordDirectory": str(out.resolve())})
    request("SetCurrentProgramScene", {"sceneName": SCENE})
    for name in state["mutes"]:
        request("SetInputMute", {"inputName": name, "inputMuted": True})
    print(f"OBS ready: scene '{SCENE}', source '{SOURCE}', 1920x1080, recordings in {out.resolve()}")


def fit_source():
    item = request("GetSceneItemId", {"sceneName": SCENE, "sourceName": SOURCE})["sceneItemId"]
    request("SetSceneItemTransform", {"sceneName": SCENE, "sceneItemId": item, "sceneItemTransform": {
        "positionX": 0, "positionY": 0, "boundsType": "OBS_BOUNDS_SCALE_INNER", "boundsWidth": 1920, "boundsHeight": 1080,
        "boundsAlignment": 0, "alignment": 5}})


def window(match):
    items = request("GetInputPropertiesListPropertyItems", {"inputName": SOURCE, "propertyName": "window"})["propertyItems"]
    found = [i for i in items if match.lower() in i["itemName"].lower()]
    if len(found) != 1:
        names = "\n  ".join(i["itemName"] for i in found) or "(none)"
        raise SystemExit(f"Expected exactly one window matching '{match}', found {len(found)}:\n  {names}")
    request("SetInputSettings", {"inputName": SOURCE, "inputSettings": {"window": found[0]["itemValue"]}, "overlay": True})
    time.sleep(1)
    fit_source()
    state = json.loads(STATE.read_text(encoding="utf-8"))
    state["window"] = found[0]["itemValue"]
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"Capturing: {found[0]['itemName']}")


def start():
    if not STATE.exists():
        raise SystemExit("Run: python record.py setup")
    target = json.loads(STATE.read_text(encoding="utf-8")).get("window")
    items = request("GetInputPropertiesListPropertyItems", {"inputName": SOURCE, "propertyName": "window"})["propertyItems"]
    if not target or target not in [i["itemValue"] for i in items]:
        raise SystemExit("No captured window. Run: python record.py window <unique title>")
    request("StartRecord")
    log_take("take-start")
    print("Recording")


def log_take(phase, **fields):
    from datetime import datetime, timezone
    entry = {"phase": phase, "utc": datetime.now(timezone.utc).isoformat(), **fields}
    with open(HOME / "timeline.jsonl", "a", encoding="utf-8") as timeline:
        timeline.write(json.dumps(entry) + "\n")


def shot(name):
    path = HOME / f"{name}.png"
    request("SaveSourceScreenshot", {"sourceName": SOURCE, "imageFormat": "png", "imageFilePath": str(path),
                                     "imageWidth": 1920, "imageHeight": 1080})
    print(path)


def stop(name):
    source = Path(request("StopRecord")["outputPath"])
    target = source.with_name(name + source.suffix)
    if target.exists():
        log_take("take-stop", label=name, file=str(source))
        raise SystemExit(f"{target} already exists; the recording stays at {source}")
    log_take("take-stop", label=name, file=str(target))
    for attempt in range(15):
        try:
            source.rename(target)
            break
        except PermissionError:
            time.sleep(2)  # OBS can hold the file briefly after StopRecord
    else:
        raise SystemExit(f"OBS still holds {source}; rename it manually")
    print(target)


def restore():
    if request("GetRecordStatus")["outputActive"]:
        raise SystemExit("Stop recording before restoring OBS.")
    state = json.loads(STATE.read_text(encoding="utf-8"))
    request("SetCurrentProgramScene", {"sceneName": state["scene"]})
    if state["sourceSettings"] is not None:
        request("SetInputSettings", {"inputName": SOURCE, "inputSettings": state["sourceSettings"], "overlay": False})
    request("SetVideoSettings", state["video"])
    request("SetRecordDirectory", {"recordDirectory": state["directory"]})
    for name, muted in state["mutes"].items():
        request("SetInputMute", {"inputName": name, "inputMuted": muted})
    STATE.replace(STATE.with_name("obs-state.restored.json"))
    print("OBS settings restored. The demo scene and source were kept for next time.")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Edge window titles contain zero-width spaces
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["setup", "window", "shot", "start", "stop", "status", "restore"])
    parser.add_argument("value", nargs="?")
    parser.add_argument("--out", type=Path, default=Path("recordings"))
    parser.add_argument("--audio", action="store_true", help="capture the browser window's audio")
    a = parser.parse_args()
    if a.action in ("window", "shot", "stop") and not a.value:
        parser.error(f"{a.action} needs a value")
    if a.action == "setup":
        setup(a.out, a.audio)
    elif a.action == "window":
        window(a.value)
    elif a.action == "shot":
        shot(a.value)
    elif a.action == "start":
        start()
    elif a.action == "stop":
        stop(a.value)
    elif a.action == "status":
        print(json.dumps(request("GetRecordStatus")))
    else:
        restore()


if __name__ == "__main__":
    main()
