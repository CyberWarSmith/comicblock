"""Dry run: print exactly what would be sent. Spends nothing, writes nothing."""
import os

from .base import Provider, Result


class DryProvider(Provider):
    name = "dry"

    def generate(self, pid, req, out_dir):
        print("=" * 100)
        print("REQUEST %s  %dx%d  outputs %d  model %s" % (pid, req["width"], req["height"], req["outputs"], self.gen["model"]))
        print("features in frame:", ", ".join(req["features"]) or "-")
        print("references, in order:")
        for i, (label, ref) in enumerate(req["refs"], 1):
            ok = ref.startswith("asset_") or os.path.isfile(ref)
            print("  %d. %-14s %s%s" % (i, label, ref, "" if ok else "   <-- MISSING"))
        print("prompt (%d chars):" % len(req["prompt"]))
        print(req["prompt"])
        return Result("dry")
