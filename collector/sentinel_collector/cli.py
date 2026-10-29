"""``sentinel-collector run`` (live lab capture) and ``sentinel-collector replay FILE``."""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from pathlib import Path
from types import FrameType

from sentinel_collector.api import ApiClient, ApiError
from sentinel_collector.capture import CapturePipeline
from sentinel_collector.config import Config, ConfigError
from sentinel_collector.replay import replay_csv
from sentinel_collector.sender import Sender

logger = logging.getLogger("sentinel_collector")


class _Stop:
    requested = False

    def __call__(self, signum: int, frame: FrameType | None) -> None:
        self.requested = True


def heartbeat(
    client: ApiClient, pipeline: CapturePipeline, sender: Sender, status: str
) -> str | None:
    """Report counters; returns the collector's mode, or None if the API is unreachable."""
    stats = pipeline.stats
    errors = [e for e in (stats.last_error, sender.stats.last_error) if e]
    body = {
        "status": status,
        "stats": {
            "capture_files": stats.files_processed,
            "capture_files_failed": stats.files_failed,
            "packets": stats.packets,
            "malformed_lines": stats.malformed_lines,
            "flows_built": stats.flows,
            "open_flows": len(pipeline.builder.active),
            "flows_evicted": pipeline.builder.evicted,
            "flows_sent": sender.stats.sent,
            "send_buffer": len(sender.buffer),
            "dropped_locally": sender.stats.dropped_locally,
            "send_failures": sender.stats.send_failures,
        },
        "last_error": errors[-1] if errors else None,
    }
    try:
        reply = client.post("/ingest/heartbeat", body)
    except ApiError as exc:
        logger.warning("Heartbeat failed: %s", exc)
        return None
    return str(reply.get("mode"))


def run(config: Config) -> int:
    client = ApiClient(config.api_url, config.token, config.request_timeout)
    sender = Sender(client, batch_size=config.batch_size, buffer_limit=config.buffer_limit)
    pipeline = CapturePipeline(
        config.capture_dir, config.state_file, idle_timeout=config.flow_idle_timeout
    )
    stop = _Stop()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    logger.info("Collecting from %s, sending to %s", config.capture_dir, config.api_url)
    next_heartbeat = 0.0
    mode: str | None = None
    while not stop.requested:
        if config.capture_dir.is_dir():
            sender.enqueue(pipeline.poll())
        else:
            pipeline.stats.last_error = f"capture directory {config.capture_dir} not found"
        sender.flush()
        if time.monotonic() >= next_heartbeat:
            new_mode = heartbeat(client, pipeline, sender, "running")
            if new_mode and new_mode != mode:
                logger.info("Collector mode: %s", new_mode)
                mode = new_mode
            next_heartbeat = time.monotonic() + config.heartbeat_seconds
        time.sleep(config.poll_seconds)
    logger.info("Stopping: sending open flows")
    sender.enqueue(pipeline.flush())
    sender.flush()
    heartbeat(client, pipeline, sender, "stopping")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sentinel-collector", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="Read the lab capture directory and send flows (live)")
    p_replay = sub.add_parser("replay", help="Send a CSV of flows through the live pipeline")
    p_replay.add_argument("csv", type=Path)
    p_replay.add_argument("--rate", type=float, default=50.0, help="rows per second (0 = no limit)")
    p_replay.add_argument("--limit", type=int, default=None, help="stop after this many rows")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        config = Config.from_env()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    if args.command == "run":
        return run(config)
    client = ApiClient(config.api_url, config.token, config.request_timeout)
    sender = Sender(client, source="replay", batch_size=config.batch_size)
    result = replay_csv(args.csv, sender, rate=args.rate, limit=args.limit)
    print(", ".join(f"{k}={v}" for k, v in result.items()))
    return 0 if result["unsent"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
