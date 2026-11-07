"""Manual: prepare everything for a web tool, without an API.

Writes manual/<id>/ with prompt.txt and the references numbered in the order to attach them (01_blockout.png first,
then the sheets). Paste the prompt, attach the images in that order, generate, save the results anywhere, then:

    python -m comicblock import <project> <id> result1.png result2.png
"""
import os
import shutil

from .base import Provider, Result


class ManualProvider(Provider):
    name = "manual"

    def generate(self, pid, req, out_dir):
        d = os.path.join(self.cfg["paths"]["manual"], pid)
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d)
        lines = []
        for i, (label, ref) in enumerate(req["refs"], 1):
            if ref.startswith("asset_"):
                lines.append("%02d  %s  (provider asset id %s: download it or swap in the local file)" % (i, label, ref))
                continue
            ext = os.path.splitext(ref)[1] or ".png"
            name = "%02d_%s%s" % (i, label, ext)
            shutil.copyfile(ref, os.path.join(d, name))
            lines.append("%02d  %s" % (i, name))
        with open(os.path.join(d, "prompt.txt"), "w", encoding="utf-8") as fh:
            fh.write(req["prompt"] + "\n")
        with open(os.path.join(d, "README.txt"), "w", encoding="utf-8") as fh:
            fh.write("Panel %s  -  %d x %d, %d outputs\n\n" % (pid, req["width"], req["height"], req["outputs"]))
            fh.write("1. In your image tool, choose a model that accepts several reference images.\n")
            fh.write("2. Attach these images IN THIS ORDER (the blockout must be first):\n   ")
            fh.write("\n   ".join(lines))
            fh.write("\n3. Paste prompt.txt as the prompt. Set the size as close to %d x %d as the tool allows.\n" % (req["width"], req["height"]))
            fh.write("4. Save the results, then: python -m comicblock import <project> %s <file> [<file> ...]\n" % pid)
        print("manual: %s  (prompt.txt + %d references in order)" % (d, len(req["refs"])))
        return Result("manual", meta={"folder": d})
