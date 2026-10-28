# Feature mapping: UNSW-NB15 → live Zeek metadata

> Status: **preliminary (Phase 2).** Derived from the dataset's published feature
> descriptions and Zeek's documented log fields. It has **not** yet been verified against real
> Zeek output; Phase 6 does that. Until then, live inference stays disabled (observation-only
> mode) — see the compatibility gate in [architecture.md](architecture.md) §10.

## Why this matters

The model learns from feature values that UNSW-NB15 computed with Argus and Bro (Zeek's
predecessor) in a 2015 testbed. A live collector can only feed the model features it can
actually compute. Where a feature cannot be computed, SentinelNepal does **not** substitute a
made-up value; instead the `live_compatible` model is trained only on features that live
traffic can provide.

## Availability levels

| Level | Meaning |
|---|---|
| exact | The same quantity is available directly. |
| derived | Computed from available fields with the stated formula. |
| approximate | A related quantity; must be validated before live use. |
| unavailable | Not obtainable from default Zeek logs; excluded from `live_compatible`. |

## Mapping table

Single source of truth: `ml/sentinel_ml/schema.py` (`LIVE_FEATURE_MAP`). Regenerate this
table with `sentinel-ml feature-table`; a test fails if it drifts from the code.

<!-- BEGIN GENERATED: sentinel-ml feature-table -->
| Dataset feature | Live source (Zeek) | Transformation | Availability | Limitation | In `live_compatible` |
|---|---|---|---|---|---|
| `dur` | conn.duration | seconds | exact | Argus and Zeek may split flows differently. | yes |
| `proto` | conn.proto | lower-case | approximate | Zeek reports tcp/udp/icmp only; the dataset has many more IP protocols. | yes |
| `service` | conn.service | map Zeek names to dataset names; none -> '-' | approximate | Vocabularies differ (e.g. Zeek 'ssl' is absent from the dataset). | yes |
| `state` | conn.conn_state + history | lossy map Zeek states -> Argus states | approximate | No one-to-one mapping; must be validated. | yes |
| `spkts` | conn.orig_pkts | direct | exact | Counting may differ slightly between tools. | yes |
| `dpkts` | conn.resp_pkts | direct | exact | Counting may differ slightly between tools. | yes |
| `sbytes` | conn.orig_ip_bytes | direct | approximate | Header accounting may differ from Argus. | yes |
| `dbytes` | conn.resp_ip_bytes | direct | approximate | Header accounting may differ from Argus. | yes |
| `sttl` | - | - | unavailable | TTL is not in conn.log. | no |
| `dttl` | - | - | unavailable | TTL is not in conn.log. | no |
| `sload` | derived | sbytes * 8 / dur (0 if dur = 0) | derived | Inherits sbytes approximation. | yes |
| `dload` | derived | dbytes * 8 / dur (0 if dur = 0) | derived | Inherits dbytes approximation. | yes |
| `sloss` | - | - | unavailable | conn.missed_bytes is a different concept. | no |
| `dloss` | - | - | unavailable | conn.missed_bytes is a different concept. | no |
| `sinpkt` | derived | dur / (spkts - 1) mean inter-arrival | approximate | Mean only; per-packet timing is not in conn.log. | yes |
| `dinpkt` | derived | dur / (dpkts - 1) mean inter-arrival | approximate | Mean only; per-packet timing is not in conn.log. | yes |
| `sjit` | - | - | unavailable | Needs per-packet timing. | no |
| `djit` | - | - | unavailable | Needs per-packet timing. | no |
| `swin` | - | - | unavailable | TCP window is not in conn.log. | no |
| `dwin` | - | - | unavailable | TCP window is not in conn.log. | no |
| `tcprtt` | - | - | unavailable | Handshake timing needs a custom Zeek script. | no |
| `synack` | - | - | unavailable | Handshake timing needs a custom Zeek script. | no |
| `ackdat` | - | - | unavailable | Handshake timing needs a custom Zeek script. | no |
| `smean` | derived | sbytes / spkts | derived | Inherits sbytes approximation. | yes |
| `dmean` | derived | dbytes / dpkts | derived | Inherits dbytes approximation. | yes |
| `trans_depth` | http.trans_depth | join on uid | derived | HTTP flows only. | yes |
| `response_body_len` | http.response_body_len | join on uid | derived | HTTP flows only. | yes |
| `ct_srv_src` | collector window | count over last 100 connections | derived | Window semantics approximated. | yes |
| `ct_state_ttl` | - | - | unavailable | Depends on TTL values. | no |
| `ct_dst_ltm` | collector window | count over last 100 connections | derived | Window semantics approximated. | yes |
| `ct_src_dport_ltm` | collector window | count over last 100 connections | derived | Window semantics approximated. | yes |
| `ct_dst_sport_ltm` | collector window | count over last 100 connections | derived | Window semantics approximated. | yes |
| `ct_dst_src_ltm` | collector window | count over last 100 connections | derived | Window semantics approximated. | yes |
| `is_ftp_login` | ftp.log | join on uid | derived | FTP flows only. | yes |
| `ct_ftp_cmd` | ftp.log | join on uid | derived | FTP flows only. | yes |
| `ct_flw_http_mthd` | http.log | join on uid | derived | HTTP flows only. | yes |
| `ct_src_ltm` | collector window | count over last 100 connections | derived | Window semantics approximated. | yes |
| `ct_srv_dst` | collector window | count over last 100 connections | derived | Window semantics approximated. | yes |
| `is_sm_ips_ports` | derived | src_ip == dst_ip and src_port == dst_port | derived | - | yes |
<!-- END GENERATED -->

## Columns that are never model features

Defined in `EXCLUDED_COLUMNS` in `schema.py`, each with its reason:

- `id` — row number; can correlate with the label through row order.
- `rate` — only in the partitioned files, undocumented formula.
- `stcpb`, `dtcpb` — random TCP initial sequence numbers.
- `label`, `attack_cat` — targets.
- `src_ip`, `dst_ip`, `src_port`, `dst_port`, `start_time`, `last_time` — identifiers and
  timestamps, kept only as investigation metadata. In the testbed, attacker hosts use a small
  fixed address range, so IPs would let a model memorise hosts instead of learning behaviour.

## Consequences

1. The `full` model cannot score live traffic: about a third of its inputs are unavailable.
2. Even `live_compatible` metrics describe Argus-computed dataset values. Zeek computes some
   of them differently (see "approximate"), so live behaviour may differ from reported metrics.
3. Phase 6 must compare Zeek-derived values with dataset values (ideally by running Zeek on
   a slice of the published UNSW-NB15 PCAPs) before an admin may approve live inference.
