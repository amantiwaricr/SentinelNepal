"""Collector: config, API client, buffered sender, capture pipeline, CSV replay.

Packets and CSV rows are SYNTHETIC (sentinel_ml.testing; RFC 5737 documentation addresses).
"""

import json
import shutil
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, ClassVar

import pytest
from sentinel_ml.testing import (
    make_partitioned_frame,
    synthetic_tcp,
    synthetic_udp,
    write_synthetic_pcap,
)

from sentinel_collector.api import ApiClient, ApiError
from sentinel_collector.capture import CapturePipeline, completed_files
from sentinel_collector.config import Config, ConfigError
from sentinel_collector.replay import replay_csv
from sentinel_collector.sender import Sender

C, S = "192.0.2.10", "192.0.2.20"
needs_tshark = pytest.mark.skipif(shutil.which("tshark") is None, reason="tshark not installed")


class FakeClient:
    """Records posted batches; can be told to fail."""

    def __init__(self) -> None:
        self.posts: list[tuple[str, dict[str, Any]]] = []
        self.fail: ApiError | None = None

    def post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        if self.fail:
            raise self.fail
        self.posts.append((path, body))
        return {"accepted": len(body["records"]), "rejected": 0, "dropped": 0}


def test_config_requires_a_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COLLECTOR_TOKEN", raising=False)
    with pytest.raises(ConfigError, match="create-collector"):
        Config.from_env()
    monkeypatch.setenv("COLLECTOR_TOKEN", "t" * 43)
    monkeypatch.setenv("SENTINEL_API_URL", "file:///etc/passwd")
    with pytest.raises(ConfigError, match="http"):
        Config.from_env()
    monkeypatch.setenv("SENTINEL_API_URL", "http://backend:8000/api/v1/")
    monkeypatch.setenv("BATCH_SIZE", "50")
    config = Config.from_env()
    assert config.api_url == "http://backend:8000/api/v1" and config.batch_size == 50


def test_sender_batches_and_clears_the_buffer() -> None:
    client = FakeClient()
    sender = Sender(client, batch_size=2)  # type: ignore[arg-type]
    sender.enqueue([{"flow_id": str(i)} for i in range(5)])
    assert sender.flush() is True
    assert [len(b["records"]) for _, b in client.posts] == [2, 2, 1]
    assert client.posts[0] == (
        "/ingest/flows",
        {"source": "live", "records": [{"flow_id": "0"}, {"flow_id": "1"}]},
    )
    assert not sender.buffer and sender.stats.sent == 5


def test_sender_keeps_records_and_backs_off_while_the_api_is_down() -> None:
    now = [100.0]
    client = FakeClient()
    client.fail = ApiError("down", retryable=True)
    sender = Sender(client, clock=lambda: now[0])  # type: ignore[arg-type]
    sender.enqueue([{"flow_id": "a"}])
    assert sender.flush() is False and len(sender.buffer) == 1
    assert sender.flush() is False and sender.stats.send_failures == 1  # still backing off
    now[0] += 1.5
    client.fail = None
    assert sender.flush() is True and not sender.buffer


def test_sender_discards_a_batch_the_api_refuses() -> None:
    client = FakeClient()
    client.fail = ApiError("HTTP 422", retryable=False)
    sender = Sender(client)  # type: ignore[arg-type]
    sender.enqueue([{"flow_id": "a"}])
    assert sender.flush() is True and not sender.buffer


def test_sender_buffer_is_bounded() -> None:
    sender = Sender(FakeClient(), buffer_limit=100)  # type: ignore[arg-type]
    sender.enqueue([{"flow_id": str(i)} for i in range(150)])
    assert len(sender.buffer) == 100 and sender.stats.dropped_locally == 50
    assert sender.buffer[0]["flow_id"] == "50"  # the oldest were dropped


class _Handler(BaseHTTPRequestHandler):
    seen: ClassVar[list[dict[str, Any]]] = []
    status: ClassVar[int] = 202

    def do_POST(self) -> None:
        length = int(self.headers["Content-Length"])
        _Handler.seen.append(
            {
                "path": self.path,
                "auth": self.headers["Authorization"],
                "body": json.loads(self.rfile.read(length)),
            }
        )
        self.send_response(_Handler.status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"accepted": 1}')

    def log_message(self, *args: Any) -> None:
        pass


@pytest.fixture
def server() -> Any:
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}/api/v1"
    httpd.shutdown()


def test_api_client_sends_bearer_json_and_maps_errors(server: str) -> None:
    _Handler.seen.clear()
    _Handler.status = 202
    client = ApiClient(server, "secret-token", timeout=5)
    assert client.post("/ingest/flows", {"records": []}) == {"accepted": 1}
    assert _Handler.seen[0]["auth"] == "Bearer secret-token"
    assert _Handler.seen[0]["path"] == "/api/v1/ingest/flows"
    _Handler.status = 401
    with pytest.raises(ApiError) as refused:
        client.post("/ingest/flows", {})
    assert not refused.value.retryable
    _Handler.status = 503
    with pytest.raises(ApiError) as unavailable:
        client.post("/ingest/flows", {})
    assert unavailable.value.retryable
    with pytest.raises(ApiError) as unreachable:
        ApiClient("http://127.0.0.1:9/api/v1", "t", timeout=2).post("/x", {})
    assert unreachable.value.retryable


def test_only_finished_capture_files_are_read(tmp_path: Path) -> None:
    for name in ("lab_00001.pcapng", "lab_00002.pcapng", "lab_00003.pcapng", "notes.txt"):
        (tmp_path / name).write_bytes(b"")
    assert [p.name for p in completed_files(tmp_path)] == ["lab_00001.pcapng", "lab_00002.pcapng"]


def test_capture_files_are_ordered_by_start_time_across_dumpcap_restarts(tmp_path: Path) -> None:
    # dumpcap restarted at 16:07:36 and began numbering from 00001 again.
    names = [
        "lab_00001_20261029160555.pcapng",
        "lab_00002_20261029160625.pcapng",
        "lab_00001_20261029160736.pcapng",
        "lab_00002_20261029160806.pcapng",
    ]
    for name in reversed(names):  # creation order must not matter either
        (tmp_path / name).write_bytes(b"")
    assert [p.name for p in completed_files(tmp_path)] == names[:3]


def _session(start: float, port: int) -> list[tuple[float, bytes]]:
    return [
        (start, synthetic_tcp(C, port, S, 80, "S")),
        (start + 0.01, synthetic_tcp(S, 80, C, port, "SA")),
        (start + 0.02, synthetic_tcp(C, port, S, 80, "A")),
        (start + 0.03, synthetic_tcp(C, port, S, 80, "FA")),
        (start + 0.04, synthetic_tcp(S, 80, C, port, "FA")),
    ]


@needs_tshark
def test_capture_pipeline_reads_each_file_once_and_ends_idle_flows(tmp_path: Path) -> None:
    captures = tmp_path / "captures"
    captures.mkdir()
    write_synthetic_pcap(captures / "lab_00001.pcap", _session(1000, 40000) + _session(1001, 40001))
    write_synthetic_pcap(
        captures / "lab_00002.pcap", [(1010, synthetic_udp(C, 5353, S, 53, b"\x00" * 12))]
    )
    (captures / "lab_00003.pcap").write_bytes(b"")  # still being written by dumpcap
    now = [1005.0]
    pipeline = CapturePipeline(captures, tmp_path / "state", clock=lambda: now[0])
    first = pipeline.poll()
    # The two TCP sessions closed with FIN (ended); the UDP flow is still open.
    assert sorted(r["src_port"] for r in first) == [40000, 40001]
    assert first[0]["features"]["state"] == "FIN"
    assert pipeline.stats.files_processed == 2 and pipeline.stats.packets == 11
    assert pipeline.poll() == []  # nothing is read twice
    now[0] = 1200.0  # well past the idle timeout (and the expiry lag)
    (late,) = pipeline.poll()
    assert late["features"]["service"] == "dns"
    # A restarted collector remembers which files it already read.
    again = CapturePipeline(captures, tmp_path / "state", clock=lambda: now[0])
    assert again.poll() == []


@needs_tshark
def test_flow_continuing_in_the_file_being_written_is_not_split(tmp_path: Path) -> None:
    captures = tmp_path / "captures"
    captures.mkdir()
    session = _session(1000, 40000)
    write_synthetic_pcap(captures / "lab_00001_20261029160000.pcap", session[:3])
    (captures / "lab_00002_20261029160030.pcap").write_bytes(b"")  # being written
    now = [1045.0]  # 45 s after the last packet read: past the idle timeout, not the lag
    pipeline = CapturePipeline(captures, tmp_path / "state", clock=lambda: now[0])
    assert pipeline.poll() == []
    write_synthetic_pcap(captures / "lab_00002_20261029160030.pcap", session[3:])
    (captures / "lab_00003_20261029160100.pcap").write_bytes(b"")
    now[0] = 1200.0
    (flow,) = pipeline.poll()
    assert flow["features"]["state"] == "FIN"
    assert (flow["features"]["spkts"], flow["features"]["dpkts"]) == (3, 2)


@needs_tshark
def test_closed_flows_end_promptly_on_a_quiet_network(tmp_path: Path) -> None:
    captures = tmp_path / "captures"
    captures.mkdir()
    write_synthetic_pcap(captures / "lab_00001_20261029160000.pcap", _session(1000, 40000))
    (captures / "lab_00002_20261029160030.pcap").write_bytes(b"")
    # No later packets advance the flow clock; 5 s of real time is enough for a FIN flow.
    pipeline = CapturePipeline(captures, tmp_path / "state", clock=lambda: 1005.0)
    (flow,) = pipeline.poll()
    assert flow["features"]["state"] == "FIN"


@needs_tshark
def test_unreadable_capture_is_reported_not_fatal(tmp_path: Path) -> None:
    captures = tmp_path / "captures"
    captures.mkdir()
    (captures / "lab_00001.pcap").write_bytes(b"this is not a capture")
    (captures / "lab_00002.pcap").write_bytes(b"")
    pipeline = CapturePipeline(captures, tmp_path / "state")
    assert pipeline.poll() == []
    assert pipeline.stats.files_failed == 1 and "lab_00001.pcap" in (
        pipeline.stats.last_error or ""
    )


def test_replay_sends_validated_rows_as_replayed_flows(tmp_path: Path) -> None:
    frame = make_partitioned_frame(60, seed=5).astype(str)
    frame.loc[0, "sbytes"] = "not-a-number"
    path = tmp_path / "synthetic.csv"
    frame.to_csv(path, index=False)
    client = FakeClient()
    sender = Sender(client, source="replay", batch_size=25)  # type: ignore[arg-type]
    result = replay_csv(path, sender, rate=0)
    assert result == {
        "rows_read": 59,
        "rows_rejected_locally": 1,
        "unsent": 0,
        "accepted_by_api": 59,
    }
    records = [r for _, body in client.posts for r in body["records"]]
    assert all(body["source"] == "replay" for _, body in client.posts)
    first = records[0]
    assert first["feature_source"] == "dataset_csv" and first["src_ip"] is None
    assert isinstance(first["features"]["dur"], float) and isinstance(
        first["features"]["proto"], str
    )
    assert "ct_state_ttl" not in first["features"] and "attack_cat" not in first["features"]


def test_replay_limit(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.csv"
    make_partitioned_frame(60, seed=5).to_csv(path, index=False)
    sender = Sender(FakeClient(), source="replay")  # type: ignore[arg-type]
    assert replay_csv(path, sender, rate=0, limit=10)["rows_read"] == 10
