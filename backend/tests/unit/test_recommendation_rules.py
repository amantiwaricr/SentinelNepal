"""The recommendation rules: evidence decides what is suggested, and nothing overclaims."""

import re
from dataclasses import replace

import pytest

from app.services.recommendations.evidence import CHECKS, AlertFacts
from app.services.recommendations.rules import CATALOGUE, RULES, recommend

# Synthetic facts: a strongly scored alert with full evidence (documentation addresses).
STRONG = AlertFacts(
    category="Exploits",
    attack_score=0.95,
    default_decision="Exploits",
    src_ip="192.0.2.10",
    dst_ip="203.0.113.5",
    dst_port=80,
    service="http",
    category_precision=0.8,
    precision_source="test",
    alerts_from_source=12,
    distinct_ports_from_source=7,
    alerts_to_same_target=6,
)
# A row from a partitioned UNSW-NB15 file: no addresses, ports or related counts.
NO_ADDRESSES = replace(
    STRONG,
    src_ip=None,
    dst_ip=None,
    dst_port=None,
    alerts_from_source=None,
    distinct_ports_from_source=None,
    alerts_to_same_target=None,
)


def ids(facts: AlertFacts) -> list[str]:
    return [d.rule_id for d in recommend(facts)]


def test_full_evidence_gets_the_specific_actions() -> None:
    assert ids(STRONG) == ["exploit.inspect_target", "exploit.contain"]
    contain = recommend(STRONG)[1]
    assert "192.0.2.10" in contain.action
    assert contain.requires_human_approval
    assert all(e["met"] for e in contain.evidence_present.values())


def test_missing_addresses_downgrade_to_investigation_and_say_why() -> None:
    drafts = recommend(NO_ADDRESSES)
    assert [d.rule_id for d in drafts] == ["fallback.investigate"]
    fallback = drafts[0]
    assert "exploit.contain (missing: source_address)" in fallback.reason
    assert "destination_address" in fallback.required_evidence
    assert fallback.evidence_present["destination_address"]["met"] is False
    assert not fallback.requires_human_approval
    assert "No blocking is suggested" in fallback.action


def test_unreliable_category_never_gets_containment() -> None:
    weak = replace(STRONG, category_precision=0.2)
    assert ids(weak) == ["exploit.inspect_target", "fallback.investigate"]
    assert "reliable_category" in recommend(weak)[1].reason


def test_unrecorded_model_precision_counts_as_missing_evidence() -> None:
    assert "exploit.contain" not in ids(replace(STRONG, category_precision=None))


def test_score_below_strong_or_disagreeing_model_withholds_containment() -> None:
    assert "exploit.contain" not in ids(replace(STRONG, attack_score=0.7))
    assert "exploit.contain" not in ids(replace(STRONG, default_decision="Normal"))


@pytest.mark.parametrize(
    ("category", "expected"),
    [
        ("DoS", ["dos.review_load", "dos.rate_limit"]),
        ("Reconnaissance", ["recon.review_exposure", "recon.watch_source"]),
        ("Shellcode", ["exploit.inspect_target", "exploit.contain"]),
        ("Fuzzers", ["fuzzing.review_input_handling"]),
        ("Analysis", ["fuzzing.review_input_handling"]),
        ("Generic", ["generic.investigate"]),
    ],
)
def test_each_category_maps_to_its_rule_group(category: str, expected: list[str]) -> None:
    facts = replace(STRONG, category=category, default_decision=category)
    assert ids(facts) == expected


def test_scan_rule_needs_many_ports() -> None:
    facts = replace(STRONG, category="Reconnaissance", default_decision="Reconnaissance")
    assert "recon.watch_source" not in ids(replace(facts, distinct_ports_from_source=2))


def test_unknown_category_gets_cautious_guidance_only() -> None:
    drafts = recommend(replace(STRONG, category="Something-new"))
    assert [d.rule_id for d in drafts] == ["unknown.investigate"]
    assert "No blocking is suggested" in drafts[0].action
    assert not drafts[0].requires_human_approval


def test_bruteforce_heuristic_needs_an_auth_service_and_repetition() -> None:
    ssh = replace(STRONG, dst_port=22, service="ssh")
    assert "bruteforce_like.review_auth" in ids(ssh)
    draft = next(d for d in recommend(ssh) if d.rule_id == "bruteforce_like.review_auth")
    assert draft.reason.startswith("Heuristic, not a model prediction")
    assert "bruteforce_like.review_auth" not in ids(replace(ssh, alerts_to_same_target=2))
    assert "bruteforce_like.review_auth" not in ids(STRONG)  # http is not an auth service
    # An unmet heuristic adds no fallback noise.
    assert ids(replace(ssh, alerts_to_same_target=2)) == ids(STRONG)


def test_every_alert_gets_at_least_one_recommendation() -> None:
    for category in ("DoS", "Reconnaissance", "Exploits", "Fuzzers", "Generic", "x"):
        assert recommend(replace(NO_ADDRESSES, category=category))


def test_catalogue_is_consistent() -> None:
    rule_ids = [rule.rule_id for rule in CATALOGUE]
    assert len(rule_ids) == len(set(rule_ids))
    for rule in CATALOGUE:
        assert set(rule.required_evidence) <= set(CHECKS)
        # Anything that changes a system needs a person to decide.
        assert rule.requires_human_approval == (rule.kind != "investigate"), rule.rule_id
        if rule.kind == "contain":
            assert {"source_address", "strong_score", "reliable_category"} <= set(
                rule.required_evidence
            ), rule.rule_id
        assert "not proof" in rule.limitations


OVERCLAIM = re.compile(r"\b(detected|confirmed|definitely|proves?|is malicious)\b", re.IGNORECASE)


def test_no_rule_presents_an_alert_as_proof() -> None:
    for rule in RULES:
        for text in (rule.action, rule.reason):
            assert not OVERCLAIM.search(text), (rule.rule_id, text)
