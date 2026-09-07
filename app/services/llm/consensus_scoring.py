"""Pure agreement scoring for normalized Differences data."""

from __future__ import annotations


AGREEMENT_LEVEL_THRESHOLDS = [
    (85, "very"),
    (65, "largely"),
    (40, "partially"),
    (20, "hardly"),
]

# Eine einzelne Stimme belegt nichts: "1/1" liest sich wie eine Bestaetigung,
# ist aber nur ein Modell. Solche Claims sind seit dem Coverage-Judge sichtbar
# (grau, "zu wenige Modelle haben das behandelt") - in den Score gehen sie
# weiterhin NICHT ein, sonst hoebe fehlende Abdeckung die Zahl.
MIN_SCORED_CLAIM_SUPPORT = 2


def compute_agreement_score(data: dict) -> dict:
    claims = data.get("claims") or []
    differences = data.get("differences") or []
    model_count = len(data.get("models_compared") or [])
    ratios = []
    thin = 0
    for claim in claims:
        agree = len(claim.get("agree") or [])
        dissent = len(claim.get("dissent") or [])
        if agree + dissent < MIN_SCORED_CLAIM_SUPPORT:
            thin += 1
            continue
        ratios.append(agree / (agree + dissent))
    # Agreement describes measured claims; coverage describes whether that
    # measurement represents the answer. Missing evidence is not agreement.
    evidence = data.get("evidence_coverage") or {}
    thin += max(0, int(evidence.get("unindexed_sentences") or 0))
    total = len(ratios) + thin
    coverage = len(ratios) / total if total else 0.0
    incomplete = bool(evidence.get("truncated_answers") or evidence.get("unindexed_sentences"))
    status = "insufficient" if not ratios or coverage < 0.5 else (
        "limited" if coverage < 0.8 or incomplete else "sufficient"
    )
    base = sum(ratios) / len(ratios) if ratios else 0.0
    contradictions = [item for item in differences if item.get("type") == "contradiction"]
    major = sum(1 for item in contradictions if item.get("severity") != "minor")
    minor = len(contradictions) - major
    emphases = len(differences) - len(contradictions)
    score = base - 0.25 * major - 0.10 * minor - 0.05 * emphases
    caps = [1.0]
    if status == "limited":
        # Partial coverage cannot support a high overall agreement verdict.
        caps.append(0.64)
    if differences:
        caps.append(0.84)
    if major >= 2:
        caps.append(0.39)
    elif major == 1:
        caps.append(0.64)
    if model_count == 3:
        caps.append(0.90)
    elif model_count == 2:
        caps.append(0.75)
    elif model_count <= 1:
        caps.append(0.50)
    score_pct = int(round(max(0.0, min(score, *caps)) * 100)) if status != "insufficient" else None
    level = "insufficient" if score_pct is None else "not"
    for threshold, name in AGREEMENT_LEVEL_THRESHOLDS:
        if score_pct is not None and score_pct >= threshold:
            level = name
            break
    return {
        "score": score_pct,
        "level": level,
        "model_count": model_count,
        "major_contradictions": major,
        "minor_contradictions": minor,
        "emphases": emphases,
        # Wie breit die Zahl ueberhaupt getragen ist: gewertete Aussagen und
        # die, die zu wenige Modelle behandelt haben. Ohne diese beiden Zahlen
        # sieht ein Score aus 2 Claims genauso aus wie einer aus 40.
        "scored_claims": len(ratios),
        "thin_claims": thin,
        "coverage_percent": int(round(coverage * 100)),
        "coverage_status": status,
        "total_claims": total,
        "evidence_incomplete": incomplete,
    }

