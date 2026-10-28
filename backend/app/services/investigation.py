"""IP and subnet investigation over stored alerts. Only observed data is reported: no
geolocation, ownership, or threat-intelligence lookups."""

import ipaddress
from typing import Any

from sqlalchemy import ColumnElement, Select, cast, func, or_, select
from sqlalchemy.dialects.postgresql import CIDR, INET
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.alert import Alert

RECENT_LIMIT = 20
# Bounds how much of the address space one subnet query may scan.
MIN_PREFIX = {4: 16, 6: 48}


def parse_ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    try:
        return ipaddress.ip_address(value.strip())
    except ValueError:
        raise AppError("invalid_ip", "Not a valid IPv4 or IPv6 address", 422) from None


def parse_network(value: str) -> ipaddress.IPv4Network | ipaddress.IPv6Network:
    try:
        network = ipaddress.ip_network(value.strip(), strict=False)
    except ValueError:
        raise AppError("invalid_cidr", "Not a valid IPv4 or IPv6 network", 422) from None
    if network.prefixlen < MIN_PREFIX[network.version]:
        raise AppError(
            "cidr_too_broad",
            f"Prefix must be /{MIN_PREFIX[network.version]} or narrower for IPv{network.version}",
            422,
        )
    return network


def containing_subnet(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> ipaddress.IPv4Network | ipaddress.IPv6Network:
    prefix = 24 if ip.version == 4 else 64
    return ipaddress.ip_network(f"{ip}/{prefix}", strict=False)


def in_network(network: ipaddress.IPv4Network | ipaddress.IPv6Network) -> ColumnElement[bool]:
    target = cast(str(network), CIDR)
    return or_(Alert.src_ip.op("<<=")(target), Alert.dst_ip.op("<<=")(target))


def _counts(
    db: Session, query: Select[Any], column: Any, limit: int | None = None
) -> dict[str, int]:
    sub = query.subquery()
    col = sub.c[column.key]
    stmt = (
        select(col, func.count())
        .where(col.is_not(None))
        .group_by(col)
        .order_by(func.count().desc())
    )
    if limit:
        stmt = stmt.limit(limit)
    return {str(key): int(n) for key, n in db.execute(stmt).all()}


def _time_range(db: Session, condition: ColumnElement[bool]) -> dict[str, Any]:
    seen = func.coalesce(Alert.observed_at, Alert.created_at)
    first, last = db.execute(select(func.min(seen), func.max(seen)).where(condition)).one()
    return {"first_seen": first, "last_seen": last}


def ip_summary(db: Session, value: str) -> dict[str, Any]:
    ip = parse_ip(value)
    address = cast(str(ip), INET)
    as_source = Alert.src_ip == address
    as_destination = Alert.dst_ip == address
    either = or_(as_source, as_destination)
    query = select(Alert).where(either)
    subnet = containing_subnet(ip)
    return {
        "ip": str(ip),
        "version": ip.version,
        "alerts_total": db.scalar(select(func.count()).select_from(Alert).where(either)) or 0,
        "alerts_as_source": db.scalar(select(func.count()).select_from(Alert).where(as_source))
        or 0,
        "alerts_as_destination": db.scalar(
            select(func.count()).select_from(Alert).where(as_destination)
        )
        or 0,
        **_time_range(db, either),
        "by_category": _counts(db, query, Alert.predicted_category),
        "by_severity": _counts(db, query, Alert.severity),
        "destination_ports": _counts(db, query, Alert.dst_port, limit=20),
        "protocols": _counts(db, query, Alert.protocol, limit=20),
        "containing_subnet": str(subnet),
        "alerts_in_subnet": db.scalar(
            select(func.count()).select_from(Alert).where(in_network(subnet))
        )
        or 0,
        "recent_alerts": db.scalars(
            query.order_by(Alert.created_at.desc(), Alert.id.desc()).limit(RECENT_LIMIT)
        ).all(),
        "note": "Only alerts stored by SentinelNepal are shown. No geolocation or "
        "threat-intelligence data is used.",
    }


def subnet_summary(db: Session, value: str) -> dict[str, Any]:
    network = parse_network(value)
    condition = in_network(network)
    query = select(Alert).where(condition)
    return {
        "cidr": str(network),
        "alerts_total": db.scalar(select(func.count()).select_from(Alert).where(condition)) or 0,
        **_time_range(db, condition),
        "by_category": _counts(db, query, Alert.predicted_category),
        "top_source_ips": _counts(
            db,
            select(Alert).where(Alert.src_ip.op("<<=")(cast(str(network), CIDR))),
            Alert.src_ip,
            20,
        ),
        "top_destination_ips": _counts(
            db,
            select(Alert).where(Alert.dst_ip.op("<<=")(cast(str(network), CIDR))),
            Alert.dst_ip,
            20,
        ),
    }
