"""The TShark field list and the parser for its tab-separated output.

The collector runs, without a shell::

    tshark -r <file.pcapng> -n -Y "ip or ipv6" -T fields -E separator=/t -E occurrence=f \
           -E quote=n -e <FIELDS...>

``occurrence=f`` keeps the outer header of tunnelled or ICMP-quoted packets.
"""

from __future__ import annotations

import ipaddress
import math
from dataclasses import dataclass

FIELDS: tuple[str, ...] = (
    "frame.time_epoch",
    "ip.src",
    "ip.dst",
    "ipv6.src",
    "ipv6.dst",
    "ip.proto",
    "ipv6.nxt",
    "ip.len",
    "ipv6.plen",
    "ip.ttl",
    "ipv6.hlim",
    "tcp.srcport",
    "tcp.dstport",
    "udp.srcport",
    "udp.dstport",
    "tcp.flags",
    "tcp.window_size_value",
    "tcp.analysis.retransmission",
    "http.request.method",
    "http.content_length",
    "ftp.request.command",
    "icmp.type",
)

IPV6_HEADER_BYTES = 40

TCP_FIN, TCP_SYN, TCP_RST, TCP_ACK = 0x01, 0x02, 0x04, 0x10


def tshark_args(pcap_path: str) -> list[str]:
    """Argument list for reading one capture file (no shell, no user-controlled options)."""
    args = ["tshark", "-r", pcap_path, "-n", "-Y", "ip or ipv6", "-T", "fields"]
    args += ["-E", "separator=/t", "-E", "occurrence=f", "-E", "quote=n"]
    for field in FIELDS:
        args += ["-e", field]
    return args


class PacketParseError(ValueError):
    pass


@dataclass(frozen=True)
class Packet:
    ts: float
    src: str
    dst: str
    proto: int
    ip_len: int
    ttl: int | None
    sport: int | None
    dport: int | None
    tcp_flags: int | None = None
    window: int | None = None
    retransmission: bool = False
    http_method: str | None = None
    http_content_length: int | None = None
    ftp_command: str | None = None
    icmp_type: int | None = None


def _int(value: str, name: str, *, lo: int = 0, hi: int = 2**32) -> int | None:
    if value == "":
        return None
    try:
        number = int(value, 0) if value.startswith("0x") else int(value)
    except ValueError:
        raise PacketParseError(f"{name}: not an integer") from None
    if not lo <= number <= hi:
        raise PacketParseError(f"{name}: out of range")
    return number


def _ip(value: str, name: str) -> str:
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        raise PacketParseError(f"{name}: not an IP address") from None


def parse_line(line: str) -> Packet:
    """One TShark output line -> Packet. Raises PacketParseError for malformed lines."""
    parts = line.rstrip("\r\n").split("\t")
    if len(parts) != len(FIELDS):
        raise PacketParseError(f"expected {len(FIELDS)} fields, got {len(parts)}")
    f = dict(zip(FIELDS, parts, strict=True))
    try:
        ts = float(f["frame.time_epoch"])
    except ValueError:
        raise PacketParseError("frame.time_epoch: not a number") from None
    if not math.isfinite(ts) or ts <= 0:
        raise PacketParseError("frame.time_epoch: invalid")

    if f["ip.src"]:
        src, dst = _ip(f["ip.src"], "ip.src"), _ip(f["ip.dst"], "ip.dst")
        proto = _int(f["ip.proto"], "ip.proto", hi=255)
        ip_len = _int(f["ip.len"], "ip.len", hi=65535)
        ttl = _int(f["ip.ttl"], "ip.ttl", hi=255)
    elif f["ipv6.src"]:
        src, dst = _ip(f["ipv6.src"], "ipv6.src"), _ip(f["ipv6.dst"], "ipv6.dst")
        proto = _int(f["ipv6.nxt"], "ipv6.nxt", hi=255)
        payload = _int(f["ipv6.plen"], "ipv6.plen", hi=65535)
        ip_len = None if payload is None else payload + IPV6_HEADER_BYTES
        ttl = _int(f["ipv6.hlim"], "ipv6.hlim", hi=255)
    else:
        raise PacketParseError("no IP header")
    if proto is None or ip_len is None:
        raise PacketParseError("missing protocol or length")

    sport = _int(f["tcp.srcport"] or f["udp.srcport"], "srcport", hi=65535)
    dport = _int(f["tcp.dstport"] or f["udp.dstport"], "dstport", hi=65535)
    method = f["http.request.method"] or None
    command = f["ftp.request.command"] or None
    return Packet(
        ts=ts,
        src=src,
        dst=dst,
        proto=proto,
        ip_len=ip_len,
        ttl=ttl,
        sport=sport,
        dport=dport,
        tcp_flags=_int(f["tcp.flags"], "tcp.flags", hi=0xFFF),
        window=_int(f["tcp.window_size_value"], "tcp.window_size_value", hi=65535),
        retransmission=f["tcp.analysis.retransmission"] != "",
        # Free text from the wire: keep it short and plain.
        http_method=method[:16] if method else None,
        http_content_length=_int(f["http.content_length"], "http.content_length", hi=2**40),
        ftp_command=command[:16].upper() if command else None,
        icmp_type=_int(f["icmp.type"], "icmp.type", hi=255),
    )
