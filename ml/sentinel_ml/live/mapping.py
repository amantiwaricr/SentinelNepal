"""How each UNSW-NB15 feature is obtained from TShark output, and the compatibility check.

Availability uses the same scale as the Zeek mapping in ``sentinel_ml.schema``:
exact, derived (documented formula over available fields), approximate (related quantity;
Argus may compute it differently), unavailable. None of the approximations has been
validated against UNSW-NB15 ground truth, because the dataset's packet captures are not
part of this project; live results therefore come with that caveat.
"""

from __future__ import annotations

from dataclasses import dataclass

from sentinel_ml.schema import Availability, LiveMapping

_A = Availability
_WINDOW = "count over the last 100 completed flows, this one included"


def _m(
    source: str, transformation: str, availability: Availability, limitation: str
) -> LiveMapping:
    return LiveMapping(source, transformation, availability, limitation)


TSHARK_FEATURE_MAP: dict[str, LiveMapping] = {
    "dur": _m(
        "frame.time_epoch",
        "last - first packet (s)",
        _A.DERIVED,
        "Flow boundaries come from SentinelNepal's timeouts, not Argus's.",
    ),
    "proto": _m(
        "ip.proto / ipv6.nxt",
        "number -> dataset name; others 'unas'",
        _A.APPROXIMATE,
        "Only IP traffic is captured; the dataset also has ARP and rarer protocols.",
    ),
    "service": _m(
        "ports, http/ftp fields",
        "HTTP/FTP seen, else server port -> name, else '-'",
        _A.APPROXIMATE,
        "Port-based; the dataset labelled services with Bro's protocol detection.",
    ),
    "state": _m(
        "tcp.flags, icmp.type",
        "lossy map to Argus states (FIN, CON, REQ, RST, INT, ECO)",
        _A.APPROXIMATE,
        "Argus has more states; mapping not validated.",
    ),
    "spkts": _m("packets src -> dst", "count", _A.EXACT, "Depends on flow boundaries."),
    "dpkts": _m("packets dst -> src", "count", _A.EXACT, "Depends on flow boundaries."),
    "sbytes": _m(
        "ip.len (ipv6.plen + 40)",
        "sum src -> dst",
        _A.APPROXIMATE,
        "IP-level bytes; Argus byte accounting may differ.",
    ),
    "dbytes": _m(
        "ip.len (ipv6.plen + 40)",
        "sum dst -> src",
        _A.APPROXIMATE,
        "IP-level bytes; Argus byte accounting may differ.",
    ),
    "sttl": _m(
        "ip.ttl / ipv6.hlim",
        "first packet src -> dst",
        _A.APPROXIMATE,
        "Network-specific (UNSW-NB15 testbed hosts; 64 in the Docker lab); not used live.",
    ),
    "dttl": _m(
        "ip.ttl / ipv6.hlim",
        "first packet dst -> src",
        _A.APPROXIMATE,
        "Network-specific; excluded from the live model.",
    ),
    "sload": _m(
        "derived", "sbytes * 8 / dur (0 if dur = 0)", _A.DERIVED, "Inherits sbytes approximation."
    ),
    "dload": _m(
        "derived", "dbytes * 8 / dur (0 if dur = 0)", _A.DERIVED, "Inherits dbytes approximation."
    ),
    "sloss": _m(
        "tcp.analysis.retransmission",
        "count src -> dst",
        _A.APPROXIMATE,
        "TShark's retransmission analysis, not Argus's loss estimate.",
    ),
    "dloss": _m(
        "tcp.analysis.retransmission",
        "count dst -> src",
        _A.APPROXIMATE,
        "TShark's retransmission analysis, not Argus's loss estimate.",
    ),
    "sinpkt": _m("frame.time_epoch", "mean gap between src packets (ms)", _A.DERIVED, "-"),
    "dinpkt": _m("frame.time_epoch", "mean gap between dst packets (ms)", _A.DERIVED, "-"),
    "sjit": _m(
        "frame.time_epoch",
        "std. deviation of src packet gaps (ms)",
        _A.APPROXIMATE,
        "Argus's jitter formula is not published in the dataset.",
    ),
    "djit": _m(
        "frame.time_epoch",
        "std. deviation of dst packet gaps (ms)",
        _A.APPROXIMATE,
        "Argus's jitter formula is not published in the dataset.",
    ),
    "swin": _m(
        "tcp.window_size_value",
        "first advertised window src -> dst",
        _A.APPROXIMATE,
        "Raw window value; Argus's representation is unverified.",
    ),
    "dwin": _m(
        "tcp.window_size_value",
        "first advertised window dst -> src",
        _A.APPROXIMATE,
        "Raw window value; Argus's representation is unverified.",
    ),
    "tcprtt": _m(
        "tcp.flags, frame.time_epoch",
        "synack + ackdat (s)",
        _A.DERIVED,
        "0 without a complete handshake.",
    ),
    "synack": _m(
        "tcp.flags, frame.time_epoch", "SYN -> SYN-ACK (s)", _A.DERIVED, "0 without a SYN-ACK."
    ),
    "ackdat": _m(
        "tcp.flags, frame.time_epoch", "SYN-ACK -> ACK (s)", _A.DERIVED, "0 without the final ACK."
    ),
    "smean": _m("derived", "sbytes / spkts", _A.DERIVED, "Inherits sbytes approximation."),
    "dmean": _m("derived", "dbytes / dpkts", _A.DERIVED, "Inherits dbytes approximation."),
    "trans_depth": _m(
        "http.request.method",
        "number of HTTP requests in the flow",
        _A.APPROXIMATE,
        "Bro's pipelining depth is approximated by the request count.",
    ),
    "response_body_len": _m(
        "http.content_length",
        "sum of response Content-Length",
        _A.APPROXIMATE,
        "Declared length, not the uncompressed body size.",
    ),
    "ct_srv_src": _m("flow window", _WINDOW, _A.DERIVED, "Window over SentinelNepal's flows."),
    "ct_state_ttl": _m(
        "-", "-", _A.UNAVAILABLE, "The dataset's TTL/state ranges are not published."
    ),
    "ct_dst_ltm": _m("flow window", _WINDOW, _A.DERIVED, "Window over SentinelNepal's flows."),
    "ct_src_dport_ltm": _m(
        "flow window", _WINDOW, _A.DERIVED, "Window over SentinelNepal's flows."
    ),
    "ct_dst_sport_ltm": _m(
        "flow window", _WINDOW, _A.DERIVED, "Window over SentinelNepal's flows."
    ),
    "ct_dst_src_ltm": _m("flow window", _WINDOW, _A.DERIVED, "Window over SentinelNepal's flows."),
    "is_ftp_login": _m(
        "ftp.request.command",
        "1 if USER and PASS were sent",
        _A.APPROXIMATE,
        "Does not check that the login succeeded.",
    ),
    "ct_ftp_cmd": _m(
        "ftp.request.command",
        "number of FTP commands in the flow",
        _A.DERIVED,
        "FTP control flows only.",
    ),
    "ct_flw_http_mthd": _m(
        "http.request.method",
        "number of GET/POST requests in the flow",
        _A.APPROXIMATE,
        "Per-flow count; the dataset's exact definition is ambiguous.",
    ),
    "ct_src_ltm": _m("flow window", _WINDOW, _A.DERIVED, "Window over SentinelNepal's flows."),
    "ct_srv_dst": _m("flow window", _WINDOW, _A.DERIVED, "Window over SentinelNepal's flows."),
    "is_sm_ips_ports": _m("derived", "src_ip == dst_ip and src_port == dst_port", _A.DERIVED, "-"),
}


@dataclass(frozen=True)
class CompatibilityReport:
    source: str
    compatible: bool
    unavailable: list[str]
    approximate: list[str]

    @property
    def reason(self) -> str:
        if not self.compatible:
            return f"Features not obtainable from {self.source}: {', '.join(self.unavailable)}"
        return (
            f"All features obtainable from {self.source}; {len(self.approximate)} are "
            "approximations not validated against UNSW-NB15 ground truth"
        )


def check_compatibility(features: list[str] | tuple[str, ...]) -> CompatibilityReport:
    """Whether a model's features can all be computed from TShark-built flows."""
    unknown = [f for f in features if f not in TSHARK_FEATURE_MAP]
    unavailable = unknown + [
        f
        for f in features
        if f in TSHARK_FEATURE_MAP
        and TSHARK_FEATURE_MAP[f].availability is Availability.UNAVAILABLE
    ]
    approximate = [
        f
        for f in features
        if f in TSHARK_FEATURE_MAP
        and TSHARK_FEATURE_MAP[f].availability is Availability.APPROXIMATE
    ]
    return CompatibilityReport("TShark", not unavailable, unavailable, approximate)
