"""Group decoded packets into bidirectional flows, as Argus did for UNSW-NB15.

A flow is identified by protocol and the two endpoints. The side that sent the first packet
we saw is the *source* (originator). A flow ends when it has been idle for ``idle_timeout``
seconds (``closed_timeout`` once TCP has seen FIN from both sides or a RST), or when it has
lasted ``active_timeout`` seconds, after which a new flow starts. Time always comes from
packet timestamps, so replaying an old capture gives the same flows as live capture.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from sentinel_ml.live.tshark import TCP_ACK, TCP_FIN, TCP_RST, TCP_SYN, Packet

FlowKey = tuple[int, str, int, str, int]  # proto, ip_a, port_a, ip_b, port_b (sorted ends)


def flow_key(packet: Packet) -> FlowKey:
    a = (packet.src, packet.sport or 0)
    b = (packet.dst, packet.dport or 0)
    lo, hi = sorted((a, b))
    return (packet.proto, lo[0], lo[1], hi[0], hi[1])


@dataclass
class Direction:
    """Per-direction counters of one flow."""

    packets: int = 0
    bytes: int = 0
    first_ttl: int | None = None
    first_window: int | None = None
    retransmissions: int = 0
    times: list[float] = field(default_factory=list)

    def add(self, packet: Packet) -> None:
        self.packets += 1
        self.bytes += packet.ip_len
        self.times.append(packet.ts)
        if self.first_ttl is None:
            self.first_ttl = packet.ttl
        if self.first_window is None and packet.window is not None:
            self.first_window = packet.window
        if packet.retransmission:
            self.retransmissions += 1

    def gaps_ms(self) -> list[float]:
        return [(b - a) * 1000.0 for a, b in zip(self.times, self.times[1:], strict=False)]

    def mean_gap_ms(self) -> float:
        gaps = self.gaps_ms()
        return sum(gaps) / len(gaps) if gaps else 0.0

    def jitter_ms(self) -> float:
        gaps = self.gaps_ms()
        return statistics.pstdev(gaps) if len(gaps) > 1 else 0.0


@dataclass
class Flow:
    proto: int
    src: str
    sport: int | None
    dst: str
    dport: int | None
    start: float
    last: float
    fwd: Direction = field(default_factory=Direction)
    rev: Direction = field(default_factory=Direction)
    # TCP handshake timestamps and flags seen.
    syn_at: float | None = None
    synack_at: float | None = None
    ack_at: float | None = None
    fin_from_src: bool = False
    fin_from_dst: bool = False
    rst: bool = False
    # Application evidence decoded by TShark.
    http_requests: int = 0
    http_methods: int = 0  # GET/POST requests, for ct_flw_http_mthd
    http_response_bytes: int = 0
    ftp_commands: int = 0
    ftp_user: bool = False
    ftp_pass: bool = False
    icmp_types: set[int] = field(default_factory=set)
    packets_seen: int = 0

    @property
    def tcp_closed(self) -> bool:
        return self.rst or (self.fin_from_src and self.fin_from_dst)

    def add(self, packet: Packet) -> None:
        forward = packet.src == self.src and (packet.sport or None) == (self.sport or None)
        (self.fwd if forward else self.rev).add(packet)
        self.last = max(self.last, packet.ts)
        self.packets_seen += 1
        flags = packet.tcp_flags
        if flags is not None:
            syn, ack = bool(flags & TCP_SYN), bool(flags & TCP_ACK)
            if syn and not ack and forward and self.syn_at is None:
                self.syn_at = packet.ts
            elif syn and ack and not forward and self.synack_at is None:
                self.synack_at = packet.ts
            elif ack and not syn and forward and self.synack_at is not None and self.ack_at is None:
                self.ack_at = packet.ts
            if flags & TCP_FIN:
                if forward:
                    self.fin_from_src = True
                else:
                    self.fin_from_dst = True
            if flags & TCP_RST:
                self.rst = True
        if packet.http_method:
            self.http_requests += 1
            if packet.http_method.upper() in ("GET", "POST"):
                self.http_methods += 1
        if packet.http_content_length is not None and not forward:
            self.http_response_bytes += packet.http_content_length
        if packet.ftp_command:
            self.ftp_commands += 1
            self.ftp_user |= packet.ftp_command == "USER"
            self.ftp_pass |= packet.ftp_command == "PASS"
        if packet.icmp_type is not None:
            self.icmp_types.add(packet.icmp_type)


def _new_flow(packet: Packet) -> Flow:
    flow = Flow(
        proto=packet.proto,
        src=packet.src,
        sport=packet.sport,
        dst=packet.dst,
        dport=packet.dport,
        start=packet.ts,
        last=packet.ts,
    )
    flow.add(packet)
    return flow


class FlowBuilder:
    """Turns a time-ordered packet stream into completed flows.

    ``max_flows`` bounds memory: when exceeded, the least recently active flow is ended
    early (and counted in ``evicted``).
    """

    def __init__(
        self,
        *,
        idle_timeout: float = 30.0,
        closed_timeout: float = 2.0,
        active_timeout: float = 300.0,
        max_flows: int = 50_000,
    ) -> None:
        self.idle_timeout = idle_timeout
        self.closed_timeout = closed_timeout
        self.active_timeout = active_timeout
        self.max_flows = max_flows
        self.active: dict[FlowKey, Flow] = {}
        self.evicted = 0
        self.clock = 0.0

    def _expired(self, flow: Flow, now: float) -> bool:
        if flow.proto == 6 and flow.tcp_closed and now - flow.last >= self.closed_timeout:
            return True
        return now - flow.last >= self.idle_timeout or now - flow.start >= self.active_timeout

    def add(self, packet: Packet) -> Iterator[Flow]:
        """Add one packet; yields any flows that finished before it."""
        self.clock = max(self.clock, packet.ts)
        yield from self.expire(self.clock)
        key = flow_key(packet)
        flow = self.active.get(key)
        if flow is None:
            if len(self.active) >= self.max_flows:
                oldest = min(self.active, key=lambda k: self.active[k].last)
                self.evicted += 1
                yield self.active.pop(oldest)
            self.active[key] = _new_flow(packet)
        else:
            flow.add(packet)

    def add_all(self, packets: Iterable[Packet]) -> Iterator[Flow]:
        for packet in packets:
            yield from self.add(packet)

    def expire(self, now: float) -> Iterator[Flow]:
        """Flows that have ended by time ``now`` (packet time), oldest last-packet first."""
        done = [k for k, f in self.active.items() if self._expired(f, now)]
        for key in sorted(done, key=lambda k: self.active[k].last):
            yield self.active.pop(key)

    def flush(self) -> Iterator[Flow]:
        """End every open flow (on shutdown or at the end of an offline capture)."""
        for key in sorted(self.active, key=lambda k: self.active[k].last):
            yield self.active[key]
        self.active.clear()
