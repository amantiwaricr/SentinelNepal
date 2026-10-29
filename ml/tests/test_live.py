"""Live feature extraction: TShark fields -> flows -> UNSW-NB15 features.

All packets are SYNTHETIC (RFC 5737 documentation addresses), built in the test.
"""

import shutil
from pathlib import Path

import pytest

from sentinel_ml.live.features import ConnectionWindow, flow_features, flow_record
from sentinel_ml.live.flows import FlowBuilder
from sentinel_ml.live.mapping import TSHARK_FEATURE_MAP, check_compatibility
from sentinel_ml.live.pcap import pcap_to_records
from sentinel_ml.live.tshark import FIELDS, Packet, PacketParseError, parse_line, tshark_args
from sentinel_ml.schema import ALL_FEATURES, PROFILES, Availability
from sentinel_ml.testing import synthetic_tcp, synthetic_udp, write_synthetic_pcap

C, S = "192.0.2.10", "192.0.2.20"


def line(**values: str) -> str:
    return "\t".join(values.get(f, "") for f in FIELDS)


def pkt(ts: float, src: str, dst: str, sport: int, dport: int, flags: int, **kw: object) -> Packet:
    defaults: dict[str, object] = {"proto": 6, "ip_len": 40, "ttl": 64, "window": 64240}
    defaults.update(kw)
    return Packet(ts=ts, src=src, dst=dst, sport=sport, dport=dport, tcp_flags=flags, **defaults)  # type: ignore[arg-type]


def http_session() -> list[Packet]:
    return [
        pkt(1000.000, C, S, 40000, 80, 0x02),
        pkt(1000.010, S, C, 80, 40000, 0x12, ttl=63, window=65160),
        pkt(1000.012, C, S, 40000, 80, 0x10),
        pkt(1000.020, C, S, 40000, 80, 0x18, ip_len=69, http_method="GET"),
        pkt(1000.030, C, S, 40000, 80, 0x18, ip_len=69, retransmission=True),
        pkt(1000.040, S, C, 80, 40000, 0x18, ip_len=83, http_content_length=5),
        pkt(1000.050, C, S, 40000, 80, 0x11),
        pkt(1000.060, S, C, 80, 40000, 0x11),
    ]


def test_parse_line_ipv4_tcp() -> None:
    packet = parse_line(
        line(
            **{
                "frame.time_epoch": "1000.5",
                "ip.src": C,
                "ip.dst": S,
                "ip.proto": "6",
                "ip.len": "60",
                "ip.ttl": "64",
                "tcp.srcport": "40000",
                "tcp.dstport": "22",
                "tcp.flags": "0x0012",
                "tcp.window_size_value": "502",
                "tcp.analysis.retransmission": "1",
                "ftp.request.command": "user",
            }
        )
    )
    assert packet.tcp_flags == 0x12 and packet.window == 502 and packet.retransmission
    assert packet.sport == 40000 and packet.dport == 22 and packet.ftp_command == "USER"


def test_parse_line_ipv6_udp_counts_the_fixed_header() -> None:
    packet = parse_line(
        line(
            **{
                "frame.time_epoch": "1000",
                "ipv6.src": "2001:db8::1",
                "ipv6.dst": "2001:db8::2",
                "ipv6.nxt": "17",
                "ipv6.plen": "20",
                "ipv6.hlim": "64",
                "udp.srcport": "5353",
                "udp.dstport": "53",
            }
        )
    )
    assert packet.ip_len == 60 and packet.proto == 17 and packet.dport == 53


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"frame.time_epoch": "abc"}, "frame.time_epoch"),
        ({"frame.time_epoch": "nan"}, "frame.time_epoch"),
        ({"ip.src": "not-an-ip"}, "ip.src"),
        ({"ip.len": "70000"}, "ip.len"),
        ({"tcp.srcport": "99999"}, "srcport"),
        ({"ip.src": "", "ip.dst": ""}, "no IP header"),
    ],
)
def test_malformed_lines_are_rejected(override: dict[str, str], message: str) -> None:
    values = {"frame.time_epoch": "1000", "ip.src": C, "ip.dst": S, "ip.proto": "6", "ip.len": "40"}
    values.update(override)
    with pytest.raises(PacketParseError, match=message):
        parse_line(line(**values))


def test_wrong_number_of_fields_is_rejected() -> None:
    with pytest.raises(PacketParseError, match="expected"):
        parse_line("1000\t192.0.2.10")


def test_tshark_arguments_are_a_fixed_list() -> None:
    args = tshark_args("/captures/x; rm -rf /.pcapng")
    assert args[:3] == ["tshark", "-r", "/captures/x; rm -rf /.pcapng"]  # one argument, no shell
    assert args.count("-e") == len(FIELDS)


def test_tcp_session_features_follow_the_dataset_definitions() -> None:
    builder = FlowBuilder()
    assert list(builder.add_all(http_session())) == []
    (flow,) = builder.flush()
    f = flow_features(flow)
    assert f["proto"] == "tcp" and f["service"] == "http" and f["state"] == "FIN"
    assert f["dur"] == pytest.approx(0.060)
    assert (f["spkts"], f["dpkts"]) == (5, 3)
    assert (f["sbytes"], f["dbytes"]) == (40 + 40 + 69 + 69 + 40, 40 + 83 + 40)
    assert f["sload"] == pytest.approx(258 * 8 / 0.060)
    assert (f["sttl"], f["dttl"]) == (64, 63)
    assert (f["swin"], f["dwin"]) == (64240, 65160)
    assert (f["sloss"], f["dloss"]) == (1, 0)
    assert f["synack"] == pytest.approx(0.010) and f["ackdat"] == pytest.approx(0.002)
    assert f["tcprtt"] == pytest.approx(0.012)
    # Source gaps 12, 8, 10, 20 ms -> mean 12.5 ms.
    assert f["sinpkt"] == pytest.approx(12.5)
    assert f["sjit"] > 0
    assert f["smean"] == pytest.approx(258 / 5)
    assert (f["trans_depth"], f["ct_flw_http_mthd"], f["response_body_len"]) == (1, 1, 5)


@pytest.mark.parametrize(
    ("packets", "state"),
    [
        ([pkt(1, C, S, 40000, 22, 0x02)], "REQ"),
        ([pkt(1, C, S, 40000, 22, 0x02), pkt(1.01, S, C, 22, 40000, 0x14)], "RST"),
        ([pkt(1, C, S, 40000, 22, 0x02), pkt(1.01, S, C, 22, 40000, 0x12)], "CON"),
    ],
)
def test_tcp_states(packets: list[Packet], state: str) -> None:
    builder = FlowBuilder()
    list(builder.add_all(packets))
    (flow,) = builder.flush()
    assert flow_features(flow)["state"] == state


def test_udp_state_and_service() -> None:
    builder = FlowBuilder()
    query = Packet(ts=1, src=C, dst=S, proto=17, ip_len=49, ttl=64, sport=5353, dport=53)
    list(builder.add(query))
    (one_way,) = builder.flush()
    assert flow_features(one_way)["state"] == "INT"
    reply = Packet(ts=1.1, src=S, dst=C, proto=17, ip_len=65, ttl=64, sport=53, dport=5353)
    list(builder.add_all([query, reply]))
    (both,) = builder.flush()
    f = flow_features(both)
    assert (f["state"], f["service"], f["proto"]) == ("CON", "dns", "udp")
    assert (f["synack"], f["swin"]) == (0.0, 0)


def test_flows_end_on_idle_close_and_active_timeouts() -> None:
    builder = FlowBuilder(idle_timeout=10, closed_timeout=2, active_timeout=60)
    list(builder.add_all(http_session()))
    # A packet 3 s later ends the closed TCP flow but not a fresh UDP one.
    later = Packet(ts=1003.1, src=C, dst=S, proto=17, ip_len=40, ttl=64, sport=1, dport=2)
    done = list(builder.add(later))
    assert len(done) == 1 and done[0].dport == 80
    assert list(builder.expire(1012)) == []
    assert len(list(builder.expire(1013.2))) == 1  # idle 10 s
    # A long-lived flow is split at the active timeout.
    builder = FlowBuilder(idle_timeout=100, active_timeout=60)
    ticks = [
        Packet(ts=t, src=C, dst=S, proto=17, ip_len=40, ttl=64, sport=1, dport=2)
        for t in range(0, 130, 5)
    ]
    flows = list(builder.add_all(ticks)) + list(builder.flush())
    assert len(flows) == 3


def test_flow_table_is_bounded() -> None:
    builder = FlowBuilder(max_flows=3)
    packets = [
        Packet(ts=i, src=C, dst=S, proto=17, ip_len=40, ttl=64, sport=i, dport=53)
        for i in range(1, 6)
    ]
    ended = list(builder.add_all(packets))
    assert len(builder.active) == 3 and builder.evicted == 2 and len(ended) == 2


def test_connection_window_counts_include_the_current_flow() -> None:
    window = ConnectionWindow(size=3)
    builder = FlowBuilder()
    flows = [
        f
        for port in (22, 80, 443, 8080)
        for f in builder.add(pkt(port, C, S, 40000 + port, port, 0x02))
    ]
    flows += list(builder.flush())
    assert len(flows) == 4
    counts = [flow_record(f, window)["features"] for f in flows]
    assert counts[0]["ct_src_ltm"] == 1
    assert counts[2]["ct_src_ltm"] == 3 and counts[2]["ct_dst_src_ltm"] == 3
    assert counts[3]["ct_src_ltm"] == 3  # window of 3: the oldest flow dropped out
    assert counts[3]["ct_src_dport_ltm"] == 1


def test_mapping_covers_every_feature_and_marks_ttl_state_unavailable() -> None:
    assert set(TSHARK_FEATURE_MAP) == set(ALL_FEATURES)
    assert TSHARK_FEATURE_MAP["ct_state_ttl"].availability is Availability.UNAVAILABLE


def test_compatibility_of_the_profiles() -> None:
    no_ttl = check_compatibility(PROFILES["full_no_ttl"].features)
    assert no_ttl.compatible and not no_ttl.unavailable
    assert "swin" in no_ttl.approximate and "not validated" in no_ttl.reason
    full = check_compatibility(PROFILES["full"].features)
    assert not full.compatible and full.unavailable == ["ct_state_ttl"]
    assert "ct_state_ttl" in full.reason
    assert not check_compatibility(["dur", "made_up"]).compatible


def test_every_feature_except_ct_state_ttl_is_computed() -> None:
    builder = FlowBuilder()
    list(builder.add_all(http_session()))
    (flow,) = builder.flush()
    record = flow_record(flow, ConnectionWindow())
    assert set(record["features"]) == set(ALL_FEATURES) - {"ct_state_ttl"}
    assert record["src_ip"] == C and record["dst_port"] == 80


@pytest.mark.skipif(shutil.which("tshark") is None, reason="tshark is not installed")
def test_real_tshark_reads_a_synthetic_capture(tmp_path: Path) -> None:
    frames = [
        (1000.000, synthetic_tcp(C, 40000, S, 80, "S", seq=100)),
        (1000.010, synthetic_tcp(S, 80, C, 40000, "SA", seq=500, ack=101, ttl=63)),
        (1000.012, synthetic_tcp(C, 40000, S, 80, "A", seq=101, ack=501)),
        (
            1000.020,
            synthetic_tcp(
                C, 40000, S, 80, "PA", b"GET / HTTP/1.1\r\nHost: lab\r\n\r\n", seq=101, ack=501
            ),
        ),
        (
            1000.040,
            synthetic_tcp(
                S,
                80,
                C,
                40000,
                "PA",
                b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhello",
                seq=501,
                ack=130,
            ),
        ),
        (1000.050, synthetic_tcp(C, 40000, S, 80, "FA", seq=130, ack=545)),
        (1000.060, synthetic_tcp(S, 80, C, 40000, "FA", seq=545, ack=131)),
        (
            1001.000,
            synthetic_udp(
                C,
                5353,
                S,
                53,
                b"\x12\x34\x01\x00\x00\x01" + b"\x00" * 6 + b"\x03lab\x00\x00\x01\x00\x01",
            ),
        ),
    ]
    capture = write_synthetic_pcap(tmp_path / "synthetic.pcap", frames)
    records, stats = pcap_to_records(capture)
    assert stats.packets == 8 and stats.malformed == 0
    by_port = {r["dst_port"]: r["features"] for r in records}
    http = by_port[80]
    assert (http["service"], http["state"], http["spkts"], http["dpkts"]) == ("http", "FIN", 4, 3)
    assert http["synack"] == pytest.approx(0.010, abs=1e-6)
    assert (http["trans_depth"], http["response_body_len"], http["dttl"]) == (1, 5, 63)
    assert by_port[53]["service"] == "dns" and by_port[53]["state"] == "INT"
