"""The provider interface."""


class RateLimited(Exception):
    """The service refused for rate or quota (HTTP 429). The caller stops the whole run: retrying can lengthen the
    limit, and the 429 may be a plan cap rather than an hourly rate. Read the message."""


class Result:
    def __init__(self, status, files=(), cost=None, job=None, meta=None):
        self.status = status          # "success", "failure", "manual", "dry"
        self.files = list(files)      # local paths of the outputs, in order
        self.cost = cost              # provider units (Scenario: CU), or None
        self.job = job
        self.meta = meta or {}


class Provider:
    name = "base"
    spends = False                    # True when generate() costs money

    def __init__(self, cfg):
        self.cfg = cfg
        self.gen = cfg["generation"]

    def generate(self, pid, req, out_dir):
        """req: prompt.build() output. Write outputs as out_dir/<pid>_<k>.png (k from 1); return a Result.
        Raise RateLimited on a 429."""
        raise NotImplementedError
