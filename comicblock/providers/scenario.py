"""Scenario (scenario.com) provider: upload references, submit a custom-model generation, poll, download.

Credentials: a CSV with columns id,secret (a Scenario API key pair) at generation.credentials in project.yaml
(default ~/.comicblock/scenario.csv), or the environment variables SCENARIO_API_KEY and SCENARIO_API_SECRET.
Keep it outside the repo. The project id comes from generation.scenario_project or SCENARIO_PROJECT_ID.

Rules learned the expensive way:
- One job at a time. STOP at the first 429 and read the message: it may be the plan's API cap, not the hourly
  rate limit, and retries can lengthen the limit. Never retry in a loop.
- Refusals still charge. Flat-grey mannequins pass content filters; shaded nude ones don't. Famous costume names
  can be refused too.
"""
import base64
import csv
import hashlib
import json
import os
import time
import urllib.error
import urllib.request

from .base import Provider, RateLimited, Result

API = "https://api.cloud.scenario.com/v1"


class ScenarioProvider(Provider):
    name = "scenario"
    spends = True

    def __init__(self, cfg):
        super().__init__(cfg)
        self.project = self.gen.get("scenario_project") or os.environ.get("SCENARIO_PROJECT_ID")
        self._auth = None
        self.cache_path = os.path.join(cfg["paths"]["cache"], "scenario_uploads.json")

    # ------------------------------------------------------------------ http

    def credentials(self):
        key, secret = os.environ.get("SCENARIO_API_KEY"), os.environ.get("SCENARIO_API_SECRET")
        if not (key and secret):
            path = os.path.expanduser(str(self.gen.get("credentials") or ""))
            if not path or not os.path.isfile(path):
                raise SystemExit("Scenario credentials not found: put a CSV with columns id,secret at %s (outside "
                                 "the repo), or set SCENARIO_API_KEY and SCENARIO_API_SECRET." % (path or "?"))
            with open(path, newline="", encoding="utf-8-sig") as fh:
                row = next(csv.DictReader(fh))
            key, secret = row.get("id"), row.get("secret")
            if not (key and secret):
                raise SystemExit("%s needs a header row with columns id,secret" % path)
        return key, secret

    def _headers(self, json_body):
        if self._auth is None:
            k, s = self.credentials()
            self._auth = "Basic " + base64.b64encode(("%s:%s" % (k, s)).encode()).decode()
        h = {"Authorization": self._auth, "Accept": "application/json"}
        if json_body:
            h["Content-Type"] = "application/json"
        return h

    def call(self, path, body=None, method=None):
        url = API + path
        if self.project:
            url += ("&" if "?" in path else "?") + "projectId=" + self.project
        req = urllib.request.Request(url, headers=self._headers(body is not None),
                                     data=json.dumps(body).encode() if body is not None else None,
                                     method=method or ("POST" if body is not None else "GET"))
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, {"error": e.read().decode(errors="replace")[:1000]}

    # ------------------------------------------------------------------ uploads (cached by content hash)

    def _cache(self):
        if os.path.isfile(self.cache_path):
            with open(self.cache_path, encoding="utf-8") as fh:
                return json.load(fh)
        return {}

    def upload(self, path):
        if path.startswith("asset_"):
            return path
        data = open(path, "rb").read()
        digest = hashlib.sha256(data).hexdigest()
        cache = self._cache()
        if digest in cache:
            return cache[digest]
        mime = "image/jpeg" if path.lower().endswith((".jpg", ".jpeg")) else "image/png"
        st, r = self.call("/assets", {"image": "data:%s;base64,%s" % (mime, base64.b64encode(data).decode()),
                                      "name": os.path.basename(path)})
        if st == 429:
            raise RateLimited(str(r)[:800])
        if st != 200:
            raise SystemExit("Scenario upload of %s failed: %s %s" % (path, st, str(r)[:400]))
        cache[digest] = r["asset"]["id"]
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        with open(self.cache_path, "w", encoding="utf-8") as fh:
            json.dump(cache, fh, indent=1)
        return cache[digest]

    # ------------------------------------------------------------------ generate

    def generate(self, pid, req, out_dir):
        refs = [self.upload(ref) for _, ref in req["refs"]]
        body = {"prompt": req["prompt"], "referenceImages": refs, "numOutputs": req["outputs"],
                "quality": self.gen.get("quality", "high"), "width": req["width"], "height": req["height"]}
        body.update(self.gen.get("extra") or {})
        st, r = self.call("/generate/custom/" + self.gen["model"], body)
        if st == 429:
            raise RateLimited(str(r)[:800])
        if st != 200:
            return Result("submit_failed", meta={"http": st, "error": str(r)[:800], "refs": refs})
        job = r["job"]["jobId"]
        deadline = time.time() + 20 * 60
        jj = {}
        while time.time() < deadline:
            time.sleep(float(self.gen.get("poll_seconds", 12)))
            st, x = self.call("/jobs/" + job)
            if st == 429:
                raise RateLimited("while polling job %s: %s" % (job, str(x)[:600]))
            jj = x.get("job", {})
            if jj.get("status") in ("success", "failure", "canceled"):
                break
        os.makedirs(out_dir, exist_ok=True)
        files, assets = [], []
        for n, aid in enumerate(jj.get("metadata", {}).get("assetIds", []), 1):
            _, a = self.call("/assets/" + aid)
            fn = os.path.join(out_dir, "%s_%d.png" % (pid, n))
            urllib.request.urlretrieve(a["asset"]["url"], fn)
            files.append(fn)
            assets.append(aid)
        return Result(jj.get("status", "timeout"), files, cost=jj.get("billing", {}).get("cuCost"), job=job,
                      meta={"refs": refs, "assets": assets, "error": jj.get("error") or jj.get("statusMessage")})
