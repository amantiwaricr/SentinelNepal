# Defensive Recommendations

SentinelNepal suggests what an analyst could do about an alert. The suggestions come from a
small set of **transparent rules** written in code
(`backend/app/services/recommendations/rules.py`), not from a language model or a paid
service. Anyone can read the rules, and the dashboard lists them on the Recommendations page
(`GET /api/v1/recommendations/rules`).

## The one idea to remember

> A recommendation is only as strong as the evidence behind it.

An alert is a model prediction with an uncalibrated score. It can be wrong, and for several
UNSW-NB15 categories it often is (see `model-evaluation.md`). So each rule states the
evidence it needs. When any of that evidence is missing, the rule's action is **not**
suggested; the alert gets an "investigate further" recommendation that names what is missing.

## How a recommendation is made

1. **Collect the facts** about the alert, all from stored data:
   the suspected category and attack score; the model's highest-scoring class; the source and
   destination addresses, port and service, if the record has them; the model's recorded
   precision for this category (testing file, or validation split if the testing file was not
   evaluated); and counts of other stored alerts from the same source, in the same analysis
   run (or, for live traffic, within a day).
2. **Pick the rules** for the suspected category.
3. **Check each rule's required evidence.** If everything is present, the rule's action is
   suggested. If not, it is withheld.
4. **Explain anything withheld** in one `fallback.investigate` recommendation, which lists
   the withheld rules and the missing evidence and suggests no blocking.
5. **Store** the result with the rule id and version and the evidence exactly as observed, so
   it can be explained later even if the rules change.

Recommendations are generated the first time someone opens the alert, then reused.

## Evidence checks

| Name | Met when |
|---|---|
| `source_address` | The source IP address is recorded |
| `destination_address` | The destination IP address is recorded |
| `destination_service` | The destination port or service is recorded |
| `strong_score` | The attack score is at least 0.8 |
| `model_agrees` | The model's highest-scoring class is the suspected category (not just above the threshold) |
| `reliable_category` | The model's recorded precision for the category is at least 50% |
| `repeated_from_source` | At least 5 stored alerts from the same source |
| `many_ports_from_source` | Alerts from the same source to at least 5 different destination ports |
| `repeated_to_auth_service` | At least 5 alerts from the same source to the same authentication service (SSH, FTP, SMTP, …) |

## Rules (version 1)

| Rule | Categories | Kind | Needs | Approval |
|---|---|---|---|---|
| `dos.review_load` | DoS | investigate | — | no |
| `dos.rate_limit` | DoS | contain | source, destination, strong score, model agrees, reliable category, repeated from source | yes |
| `recon.review_exposure` | Reconnaissance | harden | destination | yes |
| `recon.watch_source` | Reconnaissance | contain | source, strong score, reliable category, many ports | yes |
| `exploit.inspect_target` | Exploits, Shellcode, Backdoor, Worms | investigate | destination, service | no |
| `exploit.contain` | Exploits, Shellcode, Backdoor, Worms | contain | source, strong score, model agrees, reliable category | yes |
| `fuzzing.review_input_handling` | Fuzzers, Analysis | investigate | service | no |
| `generic.investigate` | Generic | investigate | — | no |
| `bruteforce_like.review_auth` | *heuristic* | harden | source, destination, repeated to auth service | yes |
| `unknown.investigate` | any other category | investigate | — | no |
| `fallback.investigate` | when evidence is missing | investigate | — | no |

*Investigate* means look at more data. *Harden* means change a configuration (close a port,
add rate limits). *Contain* means limit or block traffic. Anything other than investigating
needs a person's decision, and a block additionally needs an admin-approved firewall request.

**Brute force.** UNSW-NB15 has no brute-force class, so the model cannot predict it. The
`bruteforce_like` rule is a heuristic over stored alerts (repeated alerts from one source to
an authentication service) and its reason starts with "Heuristic, not a model prediction".

## What to expect with real data

- **Partitioned UNSW-NB15 files** (`UNSW_NB15_testing-set.csv`) have no IP addresses or
  ports. Most rules then cannot be applied, so most alerts get only the fallback, which says
  the addresses are missing. That is the honest answer for those files.
- **Full-record files** (`UNSW-NB15_1.csv` …) include addresses, so address-based rules can
  apply. Containment rules still need the category to be reliable; with the current `full`
  model, DoS (48.9%), Shellcode (25.2%), Fuzzers (25.4%), Backdoor (5.4%) and Analysis
  (4.2%) are below 50% precision on the testing file (default decision, from
  `ml/reports/random_forest-full-20261028T135634Z/evaluation.json`), so those alerts never
  get containment suggestions.

## Changing a rule

Edit `rules.py`, increase the rule's `version`, and update `tests/unit/test_recommendation_rules.py`.
Stored recommendations keep the version that produced them.
