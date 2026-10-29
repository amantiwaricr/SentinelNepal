# Feature mapping: UNSW-NB15 → live traffic

> Status: **Phase 6.** Live traffic is decoded by **TShark** (Wireshark's command-line tool)
> and grouped into flows by SentinelNepal (`ml/sentinel_ml/live/`). The live model uses the
> `full_no_ttl` profile. Every approximation below is a documented formula; none has been
> validated against UNSW-NB15 ground truth, because the dataset's packet captures are not
> part of this project. The earlier Zeek-based mapping is kept for reference.

## Why this matters

The model learns from feature values that UNSW-NB15 computed with Argus and Bro (Zeek's
predecessor) in a 2015 testbed. A live collector can only feed the model features it can
actually compute. Where a feature cannot be computed, SentinelNepal does **not** substitute a
made-up value: a model that needs it cannot be approved for live use (the compatibility gate
in [architecture.md](architecture.md) §10).

## Why TShark rather than Zeek

Zeek's default `conn.log` summarises each connection and leaves out TTL, TCP window,
per-packet timing and handshake times, so only 27 of the 39 features were obtainable (the
`live_compatible` profile). TShark reports those fields for every packet, so SentinelNepal
can compute 38 of 39 and use the `full_no_ttl` model. TShark still does all packet decoding;
SentinelNepal only groups its output fields into flows, the step Argus performed for the
dataset. The price is that flow boundaries and several formulas are SentinelNepal's own.

## Availability levels

| Level | Meaning |
|---|---|
| exact | The same quantity is available directly. |
| derived | Computed from available fields with the stated formula. |
| approximate | A related quantity; Argus may compute it differently. |
| unavailable | Cannot be obtained; a model needing it is refused for live use. |

## TShark mapping (used for live monitoring)

Single source of truth: `ml/sentinel_ml/live/mapping.py`. Regenerate with
`sentinel-ml feature-table --source tshark`; a test fails if this table drifts from the code.

<!-- BEGIN GENERATED: sentinel-ml feature-table tshark -->
| Dataset feature | TShark source | Transformation | Availability | Limitation | In `full_no_ttl` |
|---|---|---|---|---|---|
| `dur` | frame.time_epoch | last - first packet (s) | derived | Flow boundaries come from SentinelNepal's timeouts, not Argus's. | yes |
| `proto` | ip.proto / ipv6.nxt | number -> dataset name; others 'unas' | approximate | Only IP traffic is captured; the dataset also has ARP and rarer protocols. | yes |
| `service` | ports, http/ftp fields | HTTP/FTP seen, else server port -> name, else '-' | approximate | Port-based; the dataset labelled services with Bro's protocol detection. | yes |
| `state` | tcp.flags, icmp.type | lossy map to Argus states (FIN, CON, REQ, RST, INT, ECO) | approximate | Argus has more states; mapping not validated. | yes |
| `spkts` | packets src -> dst | count | exact | Depends on flow boundaries. | yes |
| `dpkts` | packets dst -> src | count | exact | Depends on flow boundaries. | yes |
| `sbytes` | ip.len (ipv6.plen + 40) | sum src -> dst | approximate | IP-level bytes; Argus byte accounting may differ. | yes |
| `dbytes` | ip.len (ipv6.plen + 40) | sum dst -> src | approximate | IP-level bytes; Argus byte accounting may differ. | yes |
| `sttl` | ip.ttl / ipv6.hlim | first packet src -> dst | approximate | Network-specific (UNSW-NB15 testbed hosts; 64 in the Docker lab); not used live. | no |
| `dttl` | ip.ttl / ipv6.hlim | first packet dst -> src | approximate | Network-specific; excluded from the live model. | no |
| `sload` | derived | sbytes * 8 / dur (0 if dur = 0) | derived | Inherits sbytes approximation. | yes |
| `dload` | derived | dbytes * 8 / dur (0 if dur = 0) | derived | Inherits dbytes approximation. | yes |
| `sloss` | tcp.analysis.retransmission | count src -> dst | approximate | TShark's retransmission analysis, not Argus's loss estimate. | yes |
| `dloss` | tcp.analysis.retransmission | count dst -> src | approximate | TShark's retransmission analysis, not Argus's loss estimate. | yes |
| `sinpkt` | frame.time_epoch | mean gap between src packets (ms) | derived | - | yes |
| `dinpkt` | frame.time_epoch | mean gap between dst packets (ms) | derived | - | yes |
| `sjit` | frame.time_epoch | std. deviation of src packet gaps (ms) | approximate | Argus's jitter formula is not published in the dataset. | yes |
| `djit` | frame.time_epoch | std. deviation of dst packet gaps (ms) | approximate | Argus's jitter formula is not published in the dataset. | yes |
| `swin` | tcp.window_size_value | first advertised window src -> dst | approximate | Raw window value; Argus's representation is unverified. | yes |
| `dwin` | tcp.window_size_value | first advertised window dst -> src | approximate | Raw window value; Argus's representation is unverified. | yes |
| `tcprtt` | tcp.flags, frame.time_epoch | synack + ackdat (s) | derived | 0 without a complete handshake. | yes |
| `synack` | tcp.flags, frame.time_epoch | SYN -> SYN-ACK (s) | derived | 0 without a SYN-ACK. | yes |
| `ackdat` | tcp.flags, frame.time_epoch | SYN-ACK -> ACK (s) | derived | 0 without the final ACK. | yes |
| `smean` | derived | sbytes / spkts | derived | Inherits sbytes approximation. | yes |
| `dmean` | derived | dbytes / dpkts | derived | Inherits dbytes approximation. | yes |
| `trans_depth` | http.request.method | number of HTTP requests in the flow | approximate | Bro's pipelining depth is approximated by the request count. | yes |
| `response_body_len` | http.content_length | sum of response Content-Length | approximate | Declared length, not the uncompressed body size. | yes |
| `ct_srv_src` | flow window | count over the last 100 completed flows, this one included | derived | Window over SentinelNepal's flows. | yes |
| `ct_state_ttl` | - | - | unavailable | The dataset's TTL/state ranges are not published. | no |
| `ct_dst_ltm` | flow window | count over the last 100 completed flows, this one included | derived | Window over SentinelNepal's flows. | yes |
| `ct_src_dport_ltm` | flow window | count over the last 100 completed flows, this one included | derived | Window over SentinelNepal's flows. | yes |
| `ct_dst_sport_ltm` | flow window | count over the last 100 completed flows, this one included | derived | Window over SentinelNepal's flows. | yes |
| `ct_dst_src_ltm` | flow window | count over the last 100 completed flows, this one included | derived | Window over SentinelNepal's flows. | yes |
| `is_ftp_login` | ftp.request.command | 1 if USER and PASS were sent | approximate | Does not check that the login succeeded. | yes |
| `ct_ftp_cmd` | ftp.request.command | number of FTP commands in the flow | derived | FTP control flows only. | yes |
| `ct_flw_http_mthd` | http.request.method | number of GET/POST requests in the flow | approximate | Per-flow count; the dataset's exact definition is ambiguous. | yes |
| `ct_src_ltm` | flow window | count over the last 100 completed flows, this one included | derived | Window over SentinelNepal's flows. | yes |
| `ct_srv_dst` | flow window | count over the last 100 completed flows, this one included | derived | Window over SentinelNepal's flows. | yes |
| `is_sm_ips_ports` | derived | src_ip == dst_ip and src_port == dst_port | derived | - | yes |
<!-- END GENERATED -->

TTL features (`sttl`, `dttl`, `ct_state_ttl`) are excluded from the live model: in
UNSW-NB15 they mostly identify the testbed hosts, and in the Docker lab every packet has the
same TTL.

## Zeek mapping (reference, not used)

Single source of truth: `ml/sentinel_ml/schema.py` (`LIVE_FEATURE_MAP`). Regenerate with
`sentinel-ml feature-table`.

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

1. The `full` model cannot score live traffic: `ct_state_ttl` is unavailable. The
   `full_no_ttl` model can, with 15 of its 36 features approximated (listed above).
2. Its metrics describe Argus-computed dataset values; live values come from different
   tools and a different network, so live behaviour can differ from the reported metrics.
3. Live inference therefore needs an admin's explicit approval of the model, after the
   compatibility check passes, and stays observation-only until then.
4. A saved lab capture can be converted to the dataset's CSV layout with
   `sentinel-ml pcap-features capture.pcapng --output flows.csv` to inspect the values.
