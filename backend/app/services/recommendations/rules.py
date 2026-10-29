"""The recommendation rule catalogue and the logic that applies it to one alert.

Design (see docs/recommendations.md):

* Rules are plain data in version-controlled code. Each generated recommendation stores the
  rule id and version, so an old recommendation can always be traced to the text that
  produced it.
* A rule applies to the model's suspected categories. Its action is suggested only when all
  of its required evidence is present in stored data. Otherwise the alert gets a cautious
  "investigate further" recommendation that names the missing evidence; aggressive actions
  are never suggested on weak evidence.
* Nothing here treats an alert as a confirmed attack. Recommendations are suggestions for an
  analyst; anything that changes a system (rate limits, closed ports, blocks) needs a human
  decision, and blocks additionally need an approved firewall request.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Literal

from app.services.recommendations.evidence import AlertFacts, evaluate

Priority = Literal["low", "medium", "high"]
# investigate: look at more data; harden: change configuration; contain: limit or block traffic.
Kind = Literal["investigate", "harden", "contain"]

COMMON_LIMITATION = (
    "The alert is a model prediction from an uncalibrated score, not proof of an attack. "
    "Confirm with other evidence before acting."
)


@dataclass(frozen=True)
class Rule:
    rule_id: str
    version: str
    group: str
    categories: frozenset[str]
    kind: Kind
    action: str
    reason: str
    required_evidence: tuple[str, ...]
    priority: Priority
    limitations: str
    requires_human_approval: bool
    # Heuristic rules are not tied to a model category; they fire on a pattern in stored
    # alerts and say so in their reason. Unmet heuristics produce nothing (no fallback).
    heuristic_trigger: Callable[[AlertFacts], bool] | None = None


@dataclass(frozen=True)
class Draft:
    rule_id: str
    rule_version: str
    category: str
    action: str
    reason: str
    required_evidence: list[str]
    evidence_present: dict[str, dict[str, object]]
    priority: Priority
    limitations: str
    requires_human_approval: bool


EXPLOIT_LIKE = frozenset({"Exploits", "Shellcode", "Backdoor", "Worms"})

RULES: tuple[Rule, ...] = (
    Rule(
        rule_id="dos.review_load",
        version="1",
        group="dos",
        categories=frozenset({"DoS"}),
        kind="investigate",
        action=(
            "Review traffic volume and connection rates for {target} around the alert time "
            "and compare them with the service's normal load."
        ),
        reason=(
            "The model suspects denial-of-service activity. Rate and volume data show whether "
            "the service was actually under abnormal load."
        ),
        required_evidence=(),
        priority="medium",
        limitations=COMMON_LIMITATION + " One flow record cannot show a flood on its own.",
        requires_human_approval=False,
    ),
    Rule(
        rule_id="dos.rate_limit",
        version="1",
        group="dos",
        categories=frozenset({"DoS"}),
        kind="contain",
        action=(
            "If the load review confirms abnormal volume from {src}, consider rate limiting it "
            "at the service or network edge, or requesting a temporary block. For large "
            "floods, ask the upstream provider about DDoS mitigation."
        ),
        reason=(
            "Repeated, strongly scored DoS alerts from one recorded source, from a model whose "
            "DoS predictions have been reliable."
        ),
        required_evidence=(
            "source_address",
            "destination_address",
            "strong_score",
            "model_agrees",
            "reliable_category",
            "repeated_from_source",
        ),
        priority="high",
        limitations=COMMON_LIMITATION
        + " Blocking a spoofed or shared address can cut off legitimate users.",
        requires_human_approval=True,
    ),
    Rule(
        rule_id="recon.review_exposure",
        version="1",
        group="recon",
        categories=frozenset({"Reconnaissance"}),
        kind="harden",
        action=(
            "List the services exposed on {dst}. Close or restrict ports that are not needed "
            "and confirm the remaining services are patched."
        ),
        reason=(
            "The model suspects scanning of this host. Reducing exposed services limits what a "
            "scan can find, whether or not this alert is correct."
        ),
        required_evidence=("destination_address",),
        priority="medium",
        limitations=COMMON_LIMITATION
        + " Closing a port can break a service that is needed; check with its owner first.",
        requires_human_approval=True,
    ),
    Rule(
        rule_id="recon.watch_source",
        version="1",
        group="recon",
        categories=frozenset({"Reconnaissance"}),
        kind="contain",
        action=(
            "Watch {src} for follow-up activity. If scanning continues, consider requesting a "
            "temporary block."
        ),
        reason=(
            "One recorded source reached many different destination ports with strongly scored "
            "alerts, a pattern consistent with a port scan."
        ),
        required_evidence=(
            "source_address",
            "strong_score",
            "reliable_category",
            "many_ports_from_source",
        ),
        priority="medium",
        limitations=COMMON_LIMITATION
        + " Authorised vulnerability scanners and monitoring tools produce the same pattern.",
        requires_human_approval=True,
    ),
    Rule(
        rule_id="exploit.inspect_target",
        version="1",
        group="exploit",
        categories=EXPLOIT_LIKE,
        kind="investigate",
        action=(
            "Inspect the targeted service at {target}: check its logs around the alert time, "
            "verify its patch level, and look for signs of compromise on the host."
        ),
        reason=(
            "The model suspects exploit-related traffic ({category}) towards this service. Host "
            "and service evidence decides whether anything happened."
        ),
        required_evidence=("destination_address", "destination_service"),
        priority="high",
        limitations=COMMON_LIMITATION
        + " UNSW-NB15 exploit categories overlap; the exact category is often wrong.",
        requires_human_approval=False,
    ),
    Rule(
        rule_id="exploit.contain",
        version="1",
        group="exploit",
        categories=EXPLOIT_LIKE,
        kind="contain",
        action=(
            "If the host checks find signs of compromise, isolate the affected host and "
            "consider requesting a temporary block of {src}."
        ),
        reason=(
            "A strongly scored alert from a recorded source, where the model's top class is "
            "this category and its predictions for it have been reliable."
        ),
        required_evidence=("source_address", "strong_score", "model_agrees", "reliable_category"),
        priority="high",
        limitations=COMMON_LIMITATION
        + " Act on host findings, not on the alert alone; isolation disrupts the service.",
        requires_human_approval=True,
    ),
    Rule(
        rule_id="fuzzing.review_input_handling",
        version="1",
        group="fuzzing_analysis",
        categories=frozenset({"Fuzzers", "Analysis"}),
        kind="investigate",
        action=(
            "Review application and input-validation logs of {target} for malformed or "
            "unusual requests around the alert time."
        ),
        reason=(
            "The model suspects fuzzing or probing ({category}). Application logs show "
            "whether unusual input actually reached the service."
        ),
        required_evidence=("destination_service",),
        priority="low",
        limitations=COMMON_LIMITATION
        + " These categories are among the least reliable in UNSW-NB15; many such alerts "
        "are normal traffic.",
        requires_human_approval=False,
    ),
    Rule(
        rule_id="generic.investigate",
        version="1",
        group="generic",
        categories=frozenset({"Generic"}),
        kind="investigate",
        action=(
            "Investigate further before acting: look at what the connection to {target} was "
            "and whether related alerts exist."
        ),
        reason=(
            "'Generic' is a broad UNSW-NB15 category covering many techniques, so it does not "
            "point to a specific defence."
        ),
        required_evidence=(),
        priority="medium",
        limitations=COMMON_LIMITATION,
        requires_human_approval=False,
    ),
    Rule(
        rule_id="bruteforce_like.review_auth",
        version="1",
        group="bruteforce_like",
        categories=frozenset(),
        kind="harden",
        action=(
            "Review authentication logs on {dst} for failed logins from {src}. Check account "
            "lockout, login rate limits and multi-factor authentication for this service."
        ),
        reason=(
            "Heuristic, not a model prediction: UNSW-NB15 has no brute-force class. Repeated "
            "alerts from {src} to the authentication service on {dst} fit a password-guessing "
            "pattern."
        ),
        required_evidence=("source_address", "destination_address", "repeated_to_auth_service"),
        priority="medium",
        limitations=COMMON_LIMITATION
        + " Repeated connections can also come from a misconfigured client or backup job.",
        requires_human_approval=True,
        heuristic_trigger=lambda facts: facts.targets_auth_service,
    ),
)

UNSUPPORTED = Rule(
    rule_id="unknown.investigate",
    version="1",
    group="unknown",
    categories=frozenset(),
    kind="investigate",
    action="Investigate further before taking any action. No blocking is suggested.",
    reason=(
        "There is no specific guidance for the category '{category}', so only further "
        "investigation is recommended."
    ),
    required_evidence=(),
    priority="low",
    limitations=COMMON_LIMITATION,
    requires_human_approval=False,
)

FALLBACK = Rule(
    rule_id="fallback.investigate",
    version="1",
    group="fallback",
    categories=frozenset(),
    kind="investigate",
    action=(
        "Investigate further before considering stronger action; gather the missing evidence "
        "first. No blocking is suggested on the current evidence."
    ),
    reason="",  # built from the rules that were not suggested
    required_evidence=(),
    priority="low",
    limitations=COMMON_LIMITATION,
    requires_human_approval=False,
)

CATALOGUE: tuple[Rule, ...] = (*RULES, UNSUPPORTED, FALLBACK)


def _fill(template: str, facts: AlertFacts) -> str:
    target = (
        f"{facts.dst_ip}:{facts.dst_port}"
        if facts.dst_ip and facts.dst_port is not None
        else facts.dst_ip or "the affected service (its address is not recorded)"
    )
    return template.format(
        target=target,
        src=facts.src_ip or "the source",
        dst=facts.dst_ip or "the destination host",
        category=facts.category,
    )


def _draft(rule: Rule, facts: AlertFacts, evidence: dict[str, dict[str, object]]) -> Draft:
    return Draft(
        rule_id=rule.rule_id,
        rule_version=rule.version,
        category=facts.category,
        action=_fill(rule.action, facts),
        reason=_fill(rule.reason, facts),
        required_evidence=list(rule.required_evidence),
        evidence_present=evidence,
        priority=rule.priority,
        limitations=rule.limitations,
        requires_human_approval=rule.requires_human_approval,
    )


def recommend(facts: AlertFacts) -> list[Draft]:
    """Recommendations for one alert, in catalogue order, always at least one."""
    drafts: list[Draft] = []
    withheld: list[tuple[Rule, list[str]]] = []
    category_rules = [r for r in RULES if facts.category in r.categories]

    for rule in category_rules:
        evidence = evaluate(rule.required_evidence, facts)
        missing = [name for name, result in evidence.items() if not result["met"]]
        if missing:
            withheld.append((rule, missing))
        else:
            drafts.append(_draft(rule, facts, evidence))

    for rule in RULES:
        if rule.heuristic_trigger is None or not rule.heuristic_trigger(facts):
            continue
        evidence = evaluate(rule.required_evidence, facts)
        if all(result["met"] for result in evidence.values()):
            drafts.append(_draft(rule, facts, evidence))

    if not category_rules:
        drafts.append(_draft(UNSUPPORTED, facts, {}))

    if withheld:
        missing_names = sorted({name for _, names in withheld for name in names})
        evidence = evaluate(tuple(missing_names), facts)
        explained = "; ".join(
            f"{rule.rule_id} (missing: {', '.join(names)})" for rule, names in withheld
        )
        drafts.append(
            replace(
                _draft(FALLBACK, facts, evidence),
                reason=f"Stronger actions were not suggested because evidence is missing: "
                f"{explained}.",
                required_evidence=missing_names,
            )
        )
    return drafts
