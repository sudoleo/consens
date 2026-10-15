"""Read-only model and preset check for the scheduled task consens-model-release-check.

Reads the production model config (a single Firestore .get(), never a write),
the public OpenRouter catalog and the state of the previous run, checks the
consensus presets and probes models live under provider.zdr=true. The only
file it writes is the task state next to the task's SKILL.md.

The scheduled task runs unattended, so every step is one fixed command that
.claude/settings.local.json allows without a prompt:

    venv/Scripts/python.exe scripts/model_release_check.py collect
    venv/Scripts/python.exe scripts/model_release_check.py probe <openrouter-id> [...]
    venv/Scripts/python.exe scripts/model_release_check.py save

collect   config, catalog diff, preset findings, one ZDR probe per model in use
          (a 429 is retried twice; still throttled shows as GEDROSSELT, not FAIL)
probe     three ZDR probes per given OpenRouter ID (``--times`` to change)
save      stores what collect saw, so the next run only reports what is new
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

STATE_DIR = Path.home() / ".claude" / "scheduled-tasks" / "consens-model-release-check"
STATE_FILE = STATE_DIR / "last-seen.json"
PENDING_FILE = STATE_DIR / "pending.json"
MODELS_URL = "https://openrouter.ai/api/v1/models"
CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
OPEN_WEIGHT_PRESET = "balanced"  # label "Open Models"
PROBE_MAX_TOKENS = 200
PROBE_TIMEOUT = 90
MAX_PROBE_IDS = 8

# Catalog entries that are never a candidate for an answer model: batch/free
# duplicates, previews, media and code models, and Meta's "contributor" tier,
# whose terms let prompts flow into Meta's products (contradicts ZDR).
NOISE = re.compile(
    r":(batch|free|extended|thinking)$|preview|-exp\b|-beta\b|image|audio|lyria|voxtral|tts|"
    r"realtime|embed|guard|codex|codestral|devstral|-code\b|contributor|multi-agent|customtools"
)


def _utf8_stdout():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def _env():
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")


def load_prod_config() -> dict:
    """The production models document. Only .get(): this script never writes."""
    from app.core.security import db_firestore
    return db_firestore.collection("app_config").document("models").get().to_dict() or {}


def fetch_catalog() -> dict:
    with urlopen(MODELS_URL, timeout=30) as response:
        rows = json.load(response).get("data") or []
    return {row["id"]: row for row in rows if isinstance(row, dict) and isinstance(row.get("id"), str)}


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def price(row: dict | None) -> str:
    pricing = (row or {}).get("pricing") or {}
    try:
        return f"${float(pricing['prompt']) * 1e6:.2f}/${float(pricing['completion']) * 1e6:.2f}"
    except (KeyError, TypeError, ValueError):
        return "$?"


def created(row: dict | None) -> str:
    stamp = (row or {}).get("created")
    if not isinstance(stamp, (int, float)):
        return "?"
    return datetime.fromtimestamp(stamp, timezone.utc).strftime("%Y-%m-%d")


def stem(openrouter_id: str) -> str:
    """Model line without version numbers: gpt-5.6-luna and gpt-6-luna share one."""
    publisher, _, name = openrouter_id.partition("/")
    return f"{publisher}/{re.sub(r'[0-9]+(?:[.-][0-9]+)*', '#', name.split(':')[0])}"


class Config:
    """Production config resolved to OpenRouter IDs, via the app's own mapping."""

    def __init__(self, prod: dict):
        from app.core import config as cfg
        self.cfg = cfg
        self.prod = prod
        self.families = list(cfg.PROVIDERS)
        self.prefixes = {key: provider.openrouter_prefix for key, provider in cfg.PROVIDERS.items()}
        self.premium = set(prod.get("premium") or [])
        self.defaults = dict(prod.get("defaults") or {})
        self.family_by_model = {}
        for family, provider in cfg.PROVIDERS.items():
            for model in [*provider.models, *(prod.get(family) or [])]:
                self.family_by_model.setdefault(model, family)

    def openrouter_id(self, model: str, family: str | None = None) -> str:
        family = family or self.family_by_model.get(model)
        return self.cfg.openrouter_model_id(model, family) if family else model

    def engine(self, value: str) -> tuple[str | None, str]:
        """Consensus engine (alias like "Gemini-Pro" or a model ID) -> (family, OpenRouter ID)."""
        alias = self.cfg.CONSENSUS_ENGINE_ALIASES.get(value)
        if alias:
            family, model = alias
            return family, self.openrouter_id(model, family)
        family = self.family_by_model.get(value)
        return family, self.openrouter_id(value, family)

    def in_family(self, openrouter_id: str) -> bool:
        return any(openrouter_id.startswith(prefix) for prefix in self.prefixes.values())

    def configured(self) -> dict[str, set[str]]:
        """Every OpenRouter ID the production config refers to, with where it is used."""
        uses: dict[str, set[str]] = {}

        def add(model, family, use):
            if isinstance(model, str) and model:
                uses.setdefault(self.openrouter_id(model, family), set()).add(use)

        for family in self.families:
            for model in self.prod.get(family) or []:
                add(model, family, f"Liste {family}")
        for family, model in self.defaults.items():
            add(model, family, f"Default {family}")
        for field in ("judge_models", "judge_models_pro", "chat_memory_models"):
            for family, model in (self.prod.get(field) or {}).items():
                add(model, family, f"{field} {family}")
        for tier, models in (self.prod.get("watch_models") or {}).items():
            for family, model in (models or {}).items():
                add(model, family, f"watch {tier}")
        for tier, model in (self.prod.get("watch_consensus_models") or {}).items():
            add(model, None, f"watch_consensus {tier}")
        for preset_id, preset in self.presets().items():
            for family, model in preset["answers"].items():
                add(model, family, f"Preset {preset['label']}")
            _family, engine_id = self.engine(preset["consensus"])
            uses.setdefault(engine_id, set()).add(f"Engine {preset['label']}")
        return uses

    def presets(self) -> dict[str, dict]:
        definitions = {preset["id"]: preset for preset in self.cfg.CONSENSUS_PRESET_DEFINITIONS}
        stored = self.prod.get("preset_models") or {}
        result = {}
        for preset_id, definition in definitions.items():
            supplied = stored.get(preset_id) if isinstance(stored.get(preset_id), dict) else {}
            result[preset_id] = {
                "label": definition["label"],
                "pro_only": bool(definition["pro_only"]),
                "answers": dict(self.cfg._preset_answer_mapping(supplied)),
                "consensus": str(supplied.get("consensus") or ""),
            }
        return result


def newer_siblings(openrouter_id: str, catalog: dict) -> list[str]:
    """Catalog models of the same line that came out after this one."""
    own = catalog.get(openrouter_id)
    if not own or not isinstance(own.get("created"), (int, float)):
        return []
    line = stem(openrouter_id)
    return sorted(
        other for other, row in catalog.items()
        if other != openrouter_id and not NOISE.search(other)
        and stem(other) == line
        and isinstance(row.get("created"), (int, float)) and row["created"] > own["created"]
    )


def preset_findings(conf: Config, catalog: dict, configured: dict) -> list[tuple[str, str]]:
    """(stable key, text). The key lets the next run report only what is new."""
    findings = []
    presets = conf.presets()
    premium_ids = {conf.openrouter_id(model) for model in conf.premium}

    def newer(key, owner, openrouter_id, free):
        # A Free slot cannot take a premium model (the app would swap it), so
        # e.g. Grok 4.7 is never a successor for Grok 4.3 in Daily.
        for sibling in newer_siblings(openrouter_id, catalog):
            if free and sibling in premium_ids:
                continue
            tag = "konfiguriert" if sibling in configured else "nicht konfiguriert"
            findings.append((f"{key}:newer:{sibling}",
                             f"{owner}: {openrouter_id} {price(catalog.get(openrouter_id))} -> neuer "
                             f"{sibling} {price(catalog.get(sibling))} ({tag})"))

    for preset_id, preset in presets.items():
        label = preset["label"]
        answers = preset["answers"]
        if not preset["consensus"]:
            findings.append((f"{preset_id}:engine:missing", f"{label}: keine Consensus-Engine gespeichert"))
        if len(answers) < conf.cfg.MAX_RUN_FAMILIES:
            findings.append((f"{preset_id}:families:{len(answers)}",
                             f"{label}: nur {len(answers)} von {conf.cfg.MAX_RUN_FAMILIES} Familien belegt"))
        slots = [(family, model, conf.openrouter_id(model, family)) for family, model in answers.items()]
        if preset["consensus"]:
            family, engine_id = conf.engine(preset["consensus"])
            slots.append((family or "?", preset["consensus"], engine_id))
        for index, (family, model, openrouter_id) in enumerate(slots):
            role = "Engine" if index == len(answers) else family
            if index < len(answers) and model not in (conf.prod.get(family) or []):
                findings.append((f"{preset_id}:{family}:not-allowed:{model}",
                                 f"{label}/{role}: {model} fehlt in der {family}-Modellliste (App ersetzt es still)"))
            if openrouter_id not in catalog:
                findings.append((f"{preset_id}:{role}:gone:{openrouter_id}",
                                 f"{label}/{role}: {openrouter_id} gibt es bei OpenRouter nicht mehr"))
            # Open Models promises open weights; the catalog's Hugging Face
            # entry is the evidence (the writer is exempt, it stays Daily's).
            if (preset_id == OPEN_WEIGHT_PRESET and index < len(answers) and openrouter_id in catalog
                    and not catalog[openrouter_id].get("hugging_face_id")):
                findings.append((f"{preset_id}:{role}:closed:{openrouter_id}",
                                 f"{label}/{role}: {openrouter_id} hat keine offenen Gewichte (kein Hugging-Face-Eintrag)"))
            if not preset["pro_only"] and (model in conf.premium or model.endswith("-Pro")):
                findings.append((f"{preset_id}:{role}:premium:{model}",
                                 f"{label}/{role}: Premium-Modell {model} in einem Free-Preset (App ersetzt es still)"))
            newer(f"{preset_id}:{role}", f"{label}/{role}", openrouter_id, not preset["pro_only"])
    ids = list(presets)
    for position, first in enumerate(ids):
        for second in ids[position + 1:]:
            a, b = presets[first], presets[second]
            if a["answers"] and a["answers"] == b["answers"] and a["consensus"] == b["consensus"]:
                findings.append((f"same:{first}:{second}",
                                 f"{a['label']} und {b['label']} sind identisch (gleiche Modelle, gleiche Engine)"))
    for family, model in conf.defaults.items():
        newer(f"default:{family}", f"Default/{family}", conf.openrouter_id(model, family), True)
    return findings


def _request_config(openrouter_id: str) -> dict:
    from app.core import config as cfg
    return cfg.MODEL_REQUEST_CONFIG.get(openrouter_id.split("/", 1)[-1], {})


def probe_once(openrouter_id: str, key: str) -> str:
    """One live call under ZDR, with the provider routing the app itself uses."""
    request_config = _request_config(openrouter_id)
    body = {
        "model": openrouter_id,
        "max_tokens": PROBE_MAX_TOKENS,
        "messages": [{"role": "user", "content": "Reply with OK."}],
        "provider": {**(request_config.get("provider") or {}), "zdr": True},
    }
    if request_config.get("reasoning"):
        body["reasoning"] = request_config["reasoning"]
    request = Request(CHAT_URL, data=json.dumps(body).encode("utf-8"), headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "X-Title": "consens.io model check",
    })
    try:
        with urlopen(request, timeout=PROBE_TIMEOUT) as response:
            data = json.load(response)
    except HTTPError as exc:
        try:
            error = json.loads(exc.read().decode("utf-8", "replace")).get("error")
            message = str(error.get("message", "") if isinstance(error, dict) else error or "")
        except (OSError, ValueError, AttributeError):
            message = ""
        if exc.code == 404 and "data policy" in message.lower():
            return "kein ZDR (404)"
        return f"HTTP {exc.code} {message[:80]}".strip()
    except (URLError, TimeoutError, OSError) as exc:
        return f"Fehler {type(exc).__name__}"
    if data.get("error"):
        error = data["error"]
        return f"Fehler {error.get('code', '')} {str(error.get('message', ''))[:80]}".strip()
    if not data.get("choices"):
        return "Fehler leere Antwort"
    return f"ok via {data.get('provider') or '?'}"


def probe_many(ids: list[str], times: int, retries_on_429: int = 0) -> dict[str, list[str]]:
    """``times`` counted attempts per model. ``retries_on_429`` repeats a
    throttled attempt after a pause, so one busy moment at a provider does not
    read as a broken model."""
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY fehlt in .env")

    def run(openrouter_id):
        results = []
        for attempt in range(times):
            if attempt:
                time.sleep(1.5)
            result = probe_once(openrouter_id, key)
            for retry in range(retries_on_429):
                if not result.startswith("HTTP 429"):
                    break
                time.sleep(5 * (retry + 1))
                result = probe_once(openrouter_id, key)
            results.append(result)
        return openrouter_id, results

    with ThreadPoolExecutor(max_workers=6) as pool:
        return dict(pool.map(run, ids))


def summary(results: list[str]) -> str:
    ok = sum(result.startswith("ok") for result in results)
    failures = sorted({result for result in results if not result.startswith("ok")})
    return f"ZDR {ok}/{len(results)}" + (f" ({'; '.join(failures)})" if failures else "")


def cmd_collect(args) -> int:
    _env()
    state = load_json(STATE_FILE)
    seen_ids = set(state.get("ids") or [])
    seen_findings = set(state.get("findings") or [])
    conf = Config(load_prod_config())
    catalog = fetch_catalog()
    family_ids = sorted(model for model in catalog if conf.in_family(model))
    configured = conf.configured()

    print(f"Letzter Lauf: {state.get('date', 'nie')} | Prod-Revision {conf.prod.get('revision', '?')} | "
          f"{len(family_ids)} Katalogmodelle in den Familien")

    fresh = [model for model in family_ids
             if model not in seen_ids and model not in configured and not NOISE.search(model)]
    print(f"\nNEU BEI OPENROUTER SEIT DEM LETZTEN LAUF ({len(fresh)}):")
    for model in fresh:
        row = catalog[model]
        print(f"  {model}  {created(row)}  {price(row)}  ctx {row.get('context_length', '?')}")

    gone = sorted(model for model in configured if model not in catalog)
    print(f"\nKONFIGURIERT, ABER NICHT MEHR BEI OPENROUTER ({len(gone)}):")
    for model in gone:
        print(f"  {model}  ({', '.join(sorted(configured[model]))})")

    print("\nPRESETS (Prod):")
    for preset_id, preset in conf.presets().items():
        parts = [f"{family} {model} {price(catalog.get(conf.openrouter_id(model, family)))}"
                 for family, model in preset["answers"].items()]
        _family, engine_id = conf.engine(preset["consensus"]) if preset["consensus"] else (None, "-")
        tier = "Pro" if preset["pro_only"] else "Free"
        print(f"  {preset['label']} ({preset_id}, {tier}): {' | '.join(parts)}")
        print(f"    Engine {preset['consensus'] or '-'} -> {engine_id}")

    findings = preset_findings(conf, catalog, configured)
    print(f"\nBEFUNDE PRESETS/DEFAULTS ({len(findings)}, NEU = noch nie gemeldet):")
    for key, text in findings:
        print(f"  {'NEU ' if key not in seen_findings else 'alt '} {text}")

    # One live probe per model that is actually in use: family defaults, the
    # standard judge, preset answers and engines. Configured-but-idle list
    # entries are not probed (cost).
    in_use = sorted(model for model, uses in configured.items()
                    if model in catalog and any(use.startswith(("Default ", "Preset ", "Engine "))
                                                or use == "judge_models openai" for use in uses))
    results = {} if args.no_probe else probe_many(in_use, 1, retries_on_429=2)
    print(f"\nZDR-PROBE DER GENUTZTEN MODELLE (1x, {len(in_use)}):")
    for model in in_use:
        status = results[model][0] if results else "nicht geprobt"
        if not results:
            flag = "-   "
        elif status.startswith("ok"):
            flag = "ok  "
        else:
            flag = "GEDROSSELT" if status.startswith("HTTP 429") else "FAIL"
        uses = ", ".join(sorted(use for use in configured[model] if not use.startswith("Liste ")))
        print(f"  {flag} {model}  {status}  [{uses}]")

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    PENDING_FILE.write_text(json.dumps({
        "ids": family_ids,
        "findings": sorted(key for key, _text in findings),
        "date": datetime.now().strftime("%Y-%m-%d"),
    }), encoding="utf-8")
    return 0


def cmd_probe(args) -> int:
    _env()
    ids = list(dict.fromkeys(args.ids))
    if len(ids) > MAX_PROBE_IDS:
        raise SystemExit(f"Hoechstens {MAX_PROBE_IDS} Modelle pro Aufruf (Kosten).")
    catalog = fetch_catalog()
    results = probe_many(ids, args.times)
    for model in ids:
        print(f"  {model}  {price(catalog.get(model))}  {summary(results[model])}")
    return 0


def cmd_save(_args) -> int:
    pending = load_json(PENDING_FILE)
    if not pending.get("ids"):
        raise SystemExit("Kein Stand aus 'collect' vorhanden.")
    STATE_FILE.write_text(json.dumps(pending), encoding="utf-8")
    PENDING_FILE.unlink(missing_ok=True)
    print(f"Gespeichert: {len(pending['ids'])} IDs, {len(pending.get('findings') or [])} Befunde, {pending['date']}")
    return 0


def main(argv=None) -> int:
    _utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    collect = sub.add_parser("collect")
    collect.add_argument("--no-probe", action="store_true", help="ohne Live-Aufrufe (zum Testen)")
    collect.set_defaults(func=cmd_collect)
    probe = sub.add_parser("probe")
    probe.add_argument("ids", nargs="+")
    probe.add_argument("--times", type=int, default=3)
    probe.set_defaults(func=cmd_probe)
    sub.add_parser("save").set_defaults(func=cmd_save)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
