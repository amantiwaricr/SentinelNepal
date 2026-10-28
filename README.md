# SentinelNepal

Machine-learning-based network intrusion detection and incident response system —
Tribhuvan University BSc CSIT final-year project.

> **Status:** Phase 0 (planning). No application code exists yet. Setup instructions will be
> added in Phase 1.

SentinelNepal scores network flow records with a model trained on the public UNSW-NB15
dataset, raises alerts for analyst review, suggests defensive measures, and lets an
administrator approve temporary, reversible IP blocks in an isolated Ubuntu lab using
nftables. Model output is treated as evidence for investigation, never as proof of an attack.

## Documentation

- [Architecture](docs/architecture.md)
- [Implementation plan](docs/implementation-plan.md)
- [Threat model](docs/threat-model.md)
- [Project status](docs/PROJECT_STATUS.md)
- [Contributor and agent rules](AGENTS.md)
