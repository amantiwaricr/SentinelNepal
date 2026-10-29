"""Turns rotating capture files into flow records.

dumpcap writes a ring buffer of files (``lab_00001_<time>.pcapng`` ...) and moves to a new
file every 30 s. A file is read only once a newer file exists, so a half-written file is
never parsed. Flows that span files stay open in one FlowBuilder.

Files are ordered by the start time in their name, not by the whole name: dumpcap restarts
its sequence number at 00001 when it restarts, so name order would interleave two runs and
feed the FlowBuilder packets out of time order (which splits every flow).
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sentinel_ml.live.features import ConnectionWindow, flow_record
from sentinel_ml.live.flows import Flow, FlowBuilder
from sentinel_ml.live.pcap import ReadStats, TsharkError, read_packets

logger = logging.getLogger(__name__)

CAPTURE_SUFFIXES = (".pcap", ".pcapng")
# dumpcap ring-buffer names end in _<sequence>_<YYYYmmddHHMMSS>.
_STARTED = re.compile(r"_(\d{14})$")
# Flows may continue in the file dumpcap is still writing (up to one 30 s rotation, plus the
# poll interval), so idle flows are ended against a clock this far behind real time.
EXPIRY_LAG_SECONDS = 60.0


@dataclass
class CaptureStats:
    files_processed: int = 0
    files_failed: int = 0
    packets: int = 0
    malformed_lines: int = 0
    flows: int = 0
    last_error: str | None = None


def _capture_order(path: Path) -> tuple[str, float, str]:
    started = _STARTED.search(path.stem)
    return (started.group(1) if started else "", path.stat().st_mtime, path.name)


def completed_files(capture_dir: Path) -> list[Path]:
    """Capture files that dumpcap has finished, oldest first (every file except the newest)."""
    files = sorted(
        (p for p in capture_dir.iterdir() if p.is_file() and p.suffix in CAPTURE_SUFFIXES),
        key=_capture_order,
    )
    return files[:-1]


class CapturePipeline:
    def __init__(
        self,
        capture_dir: Path,
        state_file: Path,
        *,
        idle_timeout: float = 30.0,
        expiry_lag: float = EXPIRY_LAG_SECONDS,
        tshark: str = "tshark",
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.capture_dir = capture_dir
        self.state_file = state_file
        self.tshark = tshark
        self.builder = FlowBuilder(idle_timeout=idle_timeout)
        self.expiry_lag = expiry_lag
        self.window = ConnectionWindow()
        self.stats = CaptureStats()
        self._clock = clock
        self._done: set[str] = self._load_state()

    def _load_state(self) -> set[str]:
        try:
            return set(self.state_file.read_text(encoding="utf-8").split())
        except FileNotFoundError:
            return set()

    def _save_state(self) -> None:
        # Only names that still exist matter; dumpcap deletes the oldest files itself.
        existing = {p.name for p in self.capture_dir.iterdir()}
        self._done &= existing
        self.state_file.write_text("\n".join(sorted(self._done)), encoding="utf-8")

    def _records(self, flows: list[Flow]) -> list[dict[str, Any]]:
        flows.sort(key=lambda f: f.last)
        self.stats.flows += len(flows)
        return [flow_record(flow, self.window) for flow in flows]

    def poll(self) -> list[dict[str, Any]]:
        """Read any newly completed capture files; return the flows that ended."""
        ended: list[Flow] = []
        for path in completed_files(self.capture_dir):
            if path.name in self._done:
                continue
            read = ReadStats()
            try:
                for packet in read_packets(path, read, tshark=self.tshark):
                    ended.extend(self.builder.add(packet))
                self.stats.files_processed += 1
            except TsharkError as exc:
                self.stats.files_failed += 1
                self.stats.last_error = f"{path.name}: {exc}"
                logger.error("Could not read %s: %s", path.name, exc)
            self.stats.packets += read.packets
            self.stats.malformed_lines += read.malformed
            self._done.add(path.name)
        if ended:
            self._save_state()
        # Flows idle for long enough end even when no new packets arrive. Open flows are
        # judged against a lagging clock (they may continue in the file being written);
        # TCP flows already closed by FIN/RST cannot, so they end without the lag.
        now = self._clock()
        ended.extend(self.builder.expire(now - self.expiry_lag, closed_now=now))
        return self._records(ended)

    def flush(self) -> list[dict[str, Any]]:
        return self._records(list(self.builder.flush()))
