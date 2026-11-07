"""Load a project's project.yaml into a plain dict with defaults filled in and paths resolved.

Runs in ordinary Python (needs PyYAML). Blender never reads the YAML: the CLI writes the resolved config to
build/.runtime.json and hands that to Blender, whose bundled Python has no PyYAML.
"""
import copy
import os

try:
    import yaml
except ImportError:                                   # only the CLI side needs it
    yaml = None

DEFAULTS = {
    "name": "Untitled",
    "blender": "auto",
    "style": "Hand-drawn 2D comic style, clean inked line art, flat colour.",
    "setting": "",
    "characters": {},
    "set": {
        "script": "set.py",
        "props": None,                 # optional project props module (props.py) with extra prop builders
        "bounds": None,                # [x0, x1, y0, y1]: where a dolly-in camera may go (default: no limit)
        "rooms": {},                   # name: [x0, x1, y0, y1], for the floor plan
        "palette": {},                 # colour name: [r, g, b] (0-1), merged over the kit's palette
        "features": {},                # name: {points: [[x, y, z], ...], text: "...", requires: "4W_..."}
        "cameras": {},                 # name: {pos: [x, y, z], look: [x, y, z], lens: 24, fourth: [], doors: {}}
    },
    "cast": {
        "rig": "default_no_toes",
        "grey": [0.36, 0.36, 0.37],    # flat mannequin grey (emission)
        "eyes": [0.03, 0.03, 0.035],
        "outline": 3.0,                # cast outline thickness (px)
        "ink": 1.4,                    # set line thickness (px)
    },
    "render": {
        "default_size": [1536, 1024],
        "background": [0.35, 0.33, 0.36],
        "background_strength": 0.35,
        "samples": 16,
    },
    "generation": {
        "provider": "dry",             # scenario | manual | dry
        "model": "model_openai-gpt-image-2-5-sunburst",
        "outputs": 2,
        "quality": "high",
        "credentials": "~/.comicblock/scenario.csv",
        "scenario_project": None,      # Scenario projectId (or env SCENARIO_PROJECT_ID)
        "poll_seconds": 12,
        "extra": {},                   # extra fields merged into the provider request body
    },
    "folders": {
        "build": "build",
        "blockout": "blockout",
        "gen": "gen",
        "review": "review",
        "manual": "manual",
        "cache": ".cache",
    },
}


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def find_project(path):
    """A project folder, or a project.yaml path, -> the folder. Raises if there is no project.yaml."""
    path = os.path.abspath(os.path.expanduser(path))
    if os.path.isfile(path):
        path = os.path.dirname(path)
    if not os.path.isfile(os.path.join(path, "project.yaml")):
        raise SystemExit("No project.yaml in %s" % path)
    return path


def load(path):
    if yaml is None:
        raise SystemExit("PyYAML is missing: pip install -r requirements.txt")
    root = find_project(path)
    with open(os.path.join(root, "project.yaml"), encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    cfg = _merge(DEFAULTS, raw)
    cfg["root"] = root
    cfg["paths"] = {k: os.path.join(root, v) for k, v in cfg["folders"].items()}
    for key, ch in cfg["characters"].items():
        ch.setdefault("name", key.title())
        ch.setdefault("height", 1.70)
        ch.setdefault("mpfb", {})
        ch.setdefault("sheets", [])
        ch.setdefault("look", "")
        if "height" not in ch or not (0.3 < float(ch["height"]) < 2.6):
            raise SystemExit("Character %s: height must be in metres (got %r)" % (key, ch.get("height")))
    return cfg


def resolve(cfg, rel):
    """A path from project.yaml: absolute, ~-prefixed, or relative to the project folder."""
    rel = os.path.expanduser(str(rel))
    return os.path.normpath(rel if os.path.isabs(rel) else os.path.join(cfg["root"], rel))
