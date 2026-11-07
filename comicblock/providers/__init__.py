"""Image-generation providers.

A provider turns one request (prompt + ordered reference images + size + output count) into image files. The
method needs a model that takes SEVERAL reference images and follows the layout of the first one; a text-only or
single-image model breaks it (FLUX with a canny ControlNet held the room but lost likeness).

Built in:
    scenario  Scenario's API (GPT Image 2.5 Sunburst by default; any Scenario model id in project.yaml)
    manual    writes the prompt and numbered references to manual/<id>/ for any web tool; `comicblock import` after
    dry       prints the prompt and references; spends nothing

To add a service, subclass Provider in a new module here, implement generate(), and register it in PROVIDERS.
"""
from .base import Provider, RateLimited, Result  # noqa: F401


def get(name, cfg):
    from . import dry, manual, scenario
    providers = {"dry": dry.DryProvider, "manual": manual.ManualProvider, "scenario": scenario.ScenarioProvider}
    if name not in providers:
        raise SystemExit("Unknown provider %r (have: %s)" % (name, ", ".join(providers)))
    return providers[name](cfg)
