"""Generate panels from their blockouts with the configured provider; log everything to gen/gen.json.

One job at a time. Stops at the first 429. Outputs: gen/<id>_<k>.png. Each run overwrites that panel's outputs, so
pick (or copy out) the keepers before re-running; earlier log entries are kept under "history".
"""
import datetime
import json
import os
import shutil

from . import panels as PN
from . import prompt as PR
from . import providers


def _log_path(cfg):
    return os.path.join(cfg["paths"]["gen"], "gen.json")


def load_log(cfg):
    p = _log_path(cfg)
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def save_log(cfg, log):
    os.makedirs(cfg["paths"]["gen"], exist_ok=True)
    with open(_log_path(cfg), "w", encoding="utf-8") as fh:
        json.dump(log, fh, indent=2)


def _record(log, pid, entry):
    old = log.get(pid)
    if old:
        entry["history"] = old.pop("history", []) + [old]
    log[pid] = entry


def run(cfg, ids, provider=None, outputs=None):
    specs = PN.load(cfg["root"])
    ids = PN.select(specs, ids)
    prov = providers.get(provider or cfg["generation"]["provider"], cfg)
    log = load_log(cfg) if prov.name not in ("dry",) else {}
    total, done = 0.0, []
    for pid in ids:
        req = PR.build(cfg, pid, specs[pid])
        if outputs:
            req["outputs"] = outputs
        missing = [r for _, r in req["refs"] if not r.startswith("asset_") and not os.path.isfile(r)]
        if missing:
            raise SystemExit("Panel %s: missing reference file(s): %s" % (pid, ", ".join(missing)))
        try:
            res = prov.generate(pid, req, cfg["paths"]["gen"])
        except providers.RateLimited as e:
            print("\nRATE LIMITED (429) on panel %s - stopping. The service said:\n%s\n" % (pid, e))
            print("Read it before trying again: it may be a plan cap, not an hourly limit. Do not retry in a loop.")
            if prov.name not in ("dry",):
                save_log(cfg, log)
            return 3
        if prov.name == "dry":
            continue
        entry = dict(time=datetime.datetime.now().isoformat(timespec="seconds"), provider=prov.name,
                     model=cfg["generation"]["model"], status=res.status, job=res.job, cost=res.cost,
                     outputs=[os.path.basename(f) for f in res.files], prompt=req["prompt"],
                     refs=[label for label, _ in req["refs"]], size=[req["width"], req["height"]], **res.meta)
        _record(log, pid, entry)
        save_log(cfg, log)
        total += res.cost or 0
        done.append(pid)
        if res.status not in ("success", "manual"):
            print("%-8s %s %s" % (pid, res.status.upper(), res.meta.get("error") or ""))
            print("         A refusal still charges. Check the blockout and prompt before re-running.")
        else:
            print("%-8s %s%s %s" % (pid, res.status, (" %s CU" % res.cost) if res.cost is not None else "",
                                   ", ".join(os.path.basename(f) for f in res.files)))
    if prov.spends:
        print("done; cost this run: %s" % total)
    if done and prov.name != "manual":
        print("Review every output at full size: python -m comicblock review %s %s" % (cfg["root"], " ".join(done)))
    return 0


def import_results(cfg, pid, images):
    """Copy images made by hand into gen/<id>_<k>.png and log them (manual provider)."""
    specs = PN.load(cfg["root"])
    PN.select(specs, [pid])
    os.makedirs(cfg["paths"]["gen"], exist_ok=True)
    out = []
    for k, src in enumerate(images, 1):
        if not os.path.isfile(src):
            raise SystemExit("No such file: %s" % src)
        dst = os.path.join(cfg["paths"]["gen"], "%s_%d%s" % (pid, k, os.path.splitext(src)[1].lower() or ".png"))
        shutil.copyfile(src, dst)
        out.append(os.path.basename(dst))
    log = load_log(cfg)
    prompt_file = os.path.join(cfg["paths"]["manual"], pid, "prompt.txt")
    _record(log, pid, dict(time=datetime.datetime.now().isoformat(timespec="seconds"), provider="manual",
                           status="imported", outputs=out,
                           prompt=open(prompt_file, encoding="utf-8").read().strip() if os.path.isfile(prompt_file) else None))
    save_log(cfg, log)
    print("imported", ", ".join(out))
