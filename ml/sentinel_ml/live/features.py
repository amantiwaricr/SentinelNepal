"""UNSW-NB15 flow features computed from a TShark-built flow.

Definitions follow the dataset's feature descriptions (NUSW-NB15_features.csv): durations
and TCP handshake times in seconds, inter-packet times and jitter in milliseconds, loads in
bits per second. Where Argus's exact method is not published, the formula used here is
documented in ``mapping.py`` and the feature is marked approximate.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

from sentinel_ml.live.flows import Flow

PROTOCOL_NAMES = {
    1: "icmp",
    2: "igmp",
    6: "tcp",
    17: "udp",
    47: "gre",
    50: "esp",
    51: "ah",
    58: "ipv6-icmp",
    89: "ospf",
    132: "sctp",
}
UNASSIGNED_PROTOCOL = "unas"

# Server port -> UNSW-NB15 service name (the dataset's 13-value vocabulary).
SERVICE_PORTS = {
    80: "http",
    8080: "http",
    443: "ssl",
    21: "ftp",
    20: "ftp-data",
    25: "smtp",
    53: "dns",
    22: "ssh",
    110: "pop3",
    67: "dhcp",
    68: "dhcp",
    161: "snmp",
    162: "snmp",
    1812: "radius",
    1813: "radius",
    6667: "irc",
}
ICMP_ECHO_TYPES = {0, 8, 128, 129}

# Same window as the dataset's ct_* features: "in 100 connections according to the last time".
WINDOW_SIZE = 100


def service_of(flow: Flow) -> str:
    if flow.http_requests:
        return "http"
    if flow.ftp_commands:
        return "ftp"
    for port in (flow.dport, flow.sport):
        if port is not None and port in SERVICE_PORTS:
            return SERVICE_PORTS[port]
    return "-"


def state_of(flow: Flow) -> str:
    """Approximation of Argus's flow state codes, which UNSW-NB15 uses."""
    both_ways = flow.fwd.packets > 0 and flow.rev.packets > 0
    if flow.proto == 6:
        if flow.rst:
            return "RST"
        if flow.fin_from_src or flow.fin_from_dst:
            return "FIN"
        if flow.syn_at is not None and flow.synack_at is None:
            return "REQ"
        return "CON" if both_ways else "INT"
    if flow.proto in (1, 58) and flow.icmp_types & ICMP_ECHO_TYPES:
        return "ECO"
    return "CON" if both_ways else "INT"


def _rate(byte_count: int, seconds: float) -> float:
    return byte_count * 8.0 / seconds if seconds > 0 else 0.0


def flow_features(flow: Flow) -> dict[str, Any]:
    """Per-flow features (everything except the ct_* window counts)."""
    dur = max(0.0, flow.last - flow.start)
    fwd, rev = flow.fwd, flow.rev
    synack = (
        flow.synack_at - flow.syn_at
        if flow.syn_at is not None and flow.synack_at is not None
        else 0.0
    )
    ackdat = (
        flow.ack_at - flow.synack_at
        if flow.synack_at is not None and flow.ack_at is not None
        else 0.0
    )
    return {
        "dur": dur,
        "proto": PROTOCOL_NAMES.get(flow.proto, UNASSIGNED_PROTOCOL),
        "service": service_of(flow),
        "state": state_of(flow),
        "spkts": fwd.packets,
        "dpkts": rev.packets,
        "sbytes": fwd.bytes,
        "dbytes": rev.bytes,
        "sttl": fwd.first_ttl or 0,
        "dttl": rev.first_ttl or 0,
        "sload": _rate(fwd.bytes, dur),
        "dload": _rate(rev.bytes, dur),
        "sloss": fwd.retransmissions,
        "dloss": rev.retransmissions,
        "sinpkt": fwd.mean_gap_ms(),
        "dinpkt": rev.mean_gap_ms(),
        "sjit": fwd.jitter_ms(),
        "djit": rev.jitter_ms(),
        "swin": fwd.first_window or 0,
        "dwin": rev.first_window or 0,
        "tcprtt": synack + ackdat,
        "synack": synack,
        "ackdat": ackdat,
        "smean": fwd.bytes / fwd.packets if fwd.packets else 0.0,
        "dmean": rev.bytes / rev.packets if rev.packets else 0.0,
        "trans_depth": flow.http_requests,
        "response_body_len": flow.http_response_bytes,
        "is_ftp_login": int(flow.ftp_user and flow.ftp_pass),
        "ct_ftp_cmd": flow.ftp_commands,
        "ct_flw_http_mthd": flow.http_methods,
        "is_sm_ips_ports": int(flow.src == flow.dst and flow.sport == flow.dport),
    }


@dataclass(frozen=True)
class _Seen:
    src: str
    dst: str
    sport: int | None
    dport: int | None
    service: str


class ConnectionWindow:
    """The dataset's ct_* counts over the last 100 completed connections (this one included)."""

    def __init__(self, size: int = WINDOW_SIZE) -> None:
        self.recent: deque[_Seen] = deque(maxlen=size)

    def add(self, flow: Flow, service: str) -> dict[str, int]:
        current = _Seen(flow.src, flow.dst, flow.sport, flow.dport, service)
        self.recent.append(current)
        window = list(self.recent)

        def count(match: Any) -> int:
            return sum(1 for seen in window if match(seen))

        c = current
        return {
            "ct_srv_src": count(lambda s: s.service == c.service and s.src == c.src),
            "ct_srv_dst": count(lambda s: s.service == c.service and s.dst == c.dst),
            "ct_dst_ltm": count(lambda s: s.dst == c.dst),
            "ct_src_ltm": count(lambda s: s.src == c.src),
            "ct_src_dport_ltm": count(lambda s: s.src == c.src and s.dport == c.dport),
            "ct_dst_sport_ltm": count(lambda s: s.dst == c.dst and s.sport == c.sport),
            "ct_dst_src_ltm": count(lambda s: s.src == c.src and s.dst == c.dst),
        }


def flow_record(flow: Flow, window: ConnectionWindow) -> dict[str, Any]:
    """Features plus connection metadata for one completed flow, ready to send."""
    features = flow_features(flow)
    features.update(window.add(flow, features["service"]))
    return {
        "flow_id": f"{flow.proto}:{flow.src}:{flow.sport}:{flow.dst}:{flow.dport}:{flow.start:.6f}",
        "feature_source": "tshark",
        "start_time": flow.start,
        "last_time": flow.last,
        "src_ip": flow.src,
        "dst_ip": flow.dst,
        "src_port": flow.sport,
        "dst_port": flow.dport,
        "features": features,
    }
