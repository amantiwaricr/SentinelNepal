"""Read a saved capture with TShark and turn it into flow records.

TShark runs as a subprocess with a fixed argument list (no shell, no user-controlled
options); only the capture path varies, and it is passed as a single argument.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sentinel_ml.live.features import ConnectionWindow, flow_record
from sentinel_ml.live.flows import FlowBuilder
from sentinel_ml.live.tshark import Packet, PacketParseError, parse_line, tshark_args

logger = logging.getLogger(__name__)


class TsharkError(RuntimeError):
    pass


@dataclass
class ReadStats:
    packets: int = 0
    malformed: int = 0
    errors: list[str] = field(default_factory=list)


def read_packets(
    path: Path, stats: ReadStats, *, tshark: str = "tshark", timeout: float = 300.0
) -> Iterator[Packet]:
    """Packets of one capture file, in file order. Malformed lines are counted, not raised."""
    args = tshark_args(str(path))
    args[0] = tshark
    try:
        process = subprocess.Popen(  # noqa: S603 - fixed argument list, no shell
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise TsharkError(f"{tshark} is not installed") from exc
    assert process.stdout is not None  # noqa: S101 - set by stdout=PIPE
    try:
        for line in process.stdout:
            try:
                packet = parse_line(line)
            except PacketParseError as exc:
                stats.malformed += 1
                if len(stats.errors) < 5:
                    stats.errors.append(str(exc))
                continue
            stats.packets += 1
            yield packet
    finally:
        process.stdout.close()
        try:
            _, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            raise TsharkError("tshark timed out") from None
    if process.returncode not in (0, None):
        # The message can contain the path; keep it short and never include packet data.
        detail = (stderr or "").strip().splitlines()[-1:] or ["no output"]
        raise TsharkError(f"tshark exited with {process.returncode}: {detail[0][:200]}")


def pcap_to_records(
    path: Path, *, tshark: str = "tshark"
) -> tuple[list[dict[str, Any]], ReadStats]:
    """All flows of one capture file (offline: open flows are ended at the end of the file)."""
    stats = ReadStats()
    builder = FlowBuilder()
    window = ConnectionWindow()
    flows = list(builder.add_all(read_packets(path, stats, tshark=tshark)))
    flows += list(builder.flush())
    flows.sort(key=lambda f: f.last)
    return [flow_record(flow, window) for flow in flows], stats
