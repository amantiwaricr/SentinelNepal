"""Canonical UNSW-NB15 schema, class labels, feature profiles, and live-feature availability.

Column names follow the partitioned UNSW-NB15 CSVs. The full-record CSVs use some different
names (e.g. ``smeansz``); :data:`COLUMN_ALIASES` maps them onto the canonical names.

Facts about the dataset in this module come from its published description and are checked
against the real files by ``sentinel-ml profile``; a mismatch makes loading fail loudly.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

# Bump when feature names, order, or meaning change. Artifacts record the version they were
# trained with and the predictor refuses to load a mismatching artifact.
FEATURE_SCHEMA_VERSION = 1

# --- Files -----------------------------------------------------------------------------------

TRAIN_FILE = "UNSW_NB15_training-set.csv"
TEST_FILE = "UNSW_NB15_testing-set.csv"
FULL_RECORD_FILES = ("UNSW-NB15_1.csv", "UNSW-NB15_2.csv", "UNSW-NB15_3.csv", "UNSW-NB15_4.csv")
FEATURES_DESCRIPTION_FILE = "NUSW-NB15_features.csv"
# A data directory containing this file holds generated test data, not UNSW-NB15. Reports
# produced from it are labelled synthetic and must never be quoted as model performance.
SYNTHETIC_MARKER_FILE = "SYNTHETIC_DATA_NOT_UNSW_NB15"

# --- Labels ----------------------------------------------------------------------------------

LABEL_COLUMN = "label"
CATEGORY_COLUMN = "attack_cat"
NORMAL = "Normal"
ATTACK_CATEGORIES = (
    "Analysis",
    "Backdoor",
    "DoS",
    "Exploits",
    "Fuzzers",
    "Generic",
    "Reconnaissance",
    "Shellcode",
    "Worms",
)
CLASS_LABELS = (NORMAL, *ATTACK_CATEGORIES)

# Spelling variants seen in the published files, keyed by lower-cased, stripped value.
CATEGORY_ALIASES = {
    **{label.lower(): label for label in CLASS_LABELS},
    "backdoors": "Backdoor",
}

# --- Columns ---------------------------------------------------------------------------------

CATEGORICAL_FEATURES = ("proto", "service", "state")

NUMERIC_FEATURES = (
    "dur",
    "spkts",
    "dpkts",
    "sbytes",
    "dbytes",
    "sttl",
    "dttl",
    "sload",
    "dload",
    "sloss",
    "dloss",
    "sinpkt",
    "dinpkt",
    "sjit",
    "djit",
    "swin",
    "dwin",
    "tcprtt",
    "synack",
    "ackdat",
    "smean",
    "dmean",
    "trans_depth",
    "response_body_len",
    "ct_srv_src",
    "ct_state_ttl",
    "ct_dst_ltm",
    "ct_src_dport_ltm",
    "ct_dst_sport_ltm",
    "ct_dst_src_ltm",
    "is_ftp_login",
    "ct_ftp_cmd",
    "ct_flw_http_mthd",
    "ct_src_ltm",
    "ct_srv_dst",
    "is_sm_ips_ports",
)

ALL_FEATURES = (*NUMERIC_FEATURES, *CATEGORICAL_FEATURES)

# Blank in some published full-record rows (HTTP/FTP-specific counters). These alone may be
# imputed; any other missing value rejects the record rather than inventing a value.
NULLABLE_FEATURES = frozenset({"ct_flw_http_mthd", "is_ftp_login", "ct_ftp_cmd"})

# Investigation metadata: kept with alerts, never used as model input.
METADATA_COLUMNS = ("src_ip", "src_port", "dst_ip", "dst_port", "start_time", "last_time")

# Columns present in the files that are deliberately not model features, and why.
EXCLUDED_COLUMNS = {
    "id": "Row number of the partitioned files: says nothing about the traffic, but can "
    "correlate with the label through the order of rows in the file.",
    "rate": "Only in the partitioned files and its formula is undocumented; excluding it keeps one "
    "feature set valid for both file families and for live data.",
    "stcpb": "TCP initial sequence number: a random value with no behavioural meaning; any pattern "
    "would reflect the 2015 testbed's tools, not attacks in general.",
    "dtcpb": "TCP initial sequence number (destination); excluded for the same reason as stcpb.",
    "label": "Target variable.",
    "attack_cat": "Target variable.",
    "src_ip": "Identifier. In this testbed attacker hosts sit in a small fixed address range, so "
    "IPs would let the model memorise hosts instead of behaviour.",
    "dst_ip": "Identifier (see src_ip).",
    "src_port": "Identifier; ephemeral source ports carry no reliable meaning.",
    "dst_port": "Identifier; the service is represented by the 'service' feature instead.",
    "start_time": "Timestamp; would tie predictions to when the capture happened.",
    "last_time": "Timestamp (see start_time).",
}

# Raw column names that differ between file families, after lower-casing and removing spaces.
COLUMN_ALIASES = {
    "smeansz": "smean",
    "dmeansz": "dmean",
    "res_bdy_len": "response_body_len",
    "sintpkt": "sinpkt",
    "dintpkt": "dinpkt",
    "srcip": "src_ip",
    "dstip": "dst_ip",
    "sport": "src_port",
    "dsport": "dst_port",
    "stime": "start_time",
    "ltime": "last_time",
}

# Header of the partitioned CSVs (UNSW_NB15_training-set.csv / _testing-set.csv).
PARTITIONED_COLUMNS = (
    "id",
    "dur",
    "proto",
    "service",
    "state",
    "spkts",
    "dpkts",
    "sbytes",
    "dbytes",
    "rate",
    "sttl",
    "dttl",
    "sload",
    "dload",
    "sloss",
    "dloss",
    "sinpkt",
    "dinpkt",
    "sjit",
    "djit",
    "swin",
    "stcpb",
    "dtcpb",
    "dwin",
    "tcprtt",
    "synack",
    "ackdat",
    "smean",
    "dmean",
    "trans_depth",
    "response_body_len",
    "ct_srv_src",
    "ct_state_ttl",
    "ct_dst_ltm",
    "ct_src_dport_ltm",
    "ct_dst_sport_ltm",
    "ct_dst_src_ltm",
    "is_ftp_login",
    "ct_ftp_cmd",
    "ct_flw_http_mthd",
    "ct_src_ltm",
    "ct_srv_dst",
    "is_sm_ips_ports",
    "attack_cat",
    "label",
)

# Column order of the header-less full-record files, as listed in NUSW-NB15_features.csv.
# Used only when that description file is not available; normalised names.
FULL_RECORD_COLUMNS = (
    "src_ip",
    "src_port",
    "dst_ip",
    "dst_port",
    "proto",
    "state",
    "dur",
    "sbytes",
    "dbytes",
    "sttl",
    "dttl",
    "sloss",
    "dloss",
    "service",
    "sload",
    "dload",
    "spkts",
    "dpkts",
    "swin",
    "dwin",
    "stcpb",
    "dtcpb",
    "smean",
    "dmean",
    "trans_depth",
    "response_body_len",
    "sjit",
    "djit",
    "start_time",
    "last_time",
    "sinpkt",
    "dinpkt",
    "tcprtt",
    "synack",
    "ackdat",
    "is_sm_ips_ports",
    "ct_state_ttl",
    "ct_flw_http_mthd",
    "is_ftp_login",
    "ct_ftp_cmd",
    "ct_srv_src",
    "ct_srv_dst",
    "ct_dst_ltm",
    "ct_src_ltm",
    "ct_src_dport_ltm",
    "ct_dst_sport_ltm",
    "ct_dst_src_ltm",
    "attack_cat",
    "label",
)


def normalize_column_name(name: str) -> str:
    """Map a raw column name from either file family onto the canonical name."""
    key = name.strip().lower().replace(" ", "")
    return COLUMN_ALIASES.get(key, key)


# --- Live (Zeek) availability ----------------------------------------------------------------


class Availability(StrEnum):
    EXACT = "exact"  # same quantity, directly available
    DERIVED = "derived"  # computed from available fields with a documented formula
    APPROXIMATE = "approximate"  # related quantity; must be validated before live use
    UNAVAILABLE = "unavailable"  # cannot be obtained from default Zeek logs


@dataclass(frozen=True)
class LiveMapping:
    source: str
    transformation: str
    availability: Availability
    limitation: str


_A = Availability

# Preliminary mapping of each model feature to Zeek output. Phase 6 verifies it against real
# Zeek logs; until then live inference stays behind the compatibility gate.
LIVE_FEATURE_MAP: dict[str, LiveMapping] = {
    "dur": LiveMapping(
        "conn.duration", "seconds", _A.EXACT, "Argus and Zeek may split flows differently."
    ),
    "proto": LiveMapping(
        "conn.proto",
        "lower-case",
        _A.APPROXIMATE,
        "Zeek reports tcp/udp/icmp only; the dataset has many more IP protocols.",
    ),
    "service": LiveMapping(
        "conn.service",
        "map Zeek names to dataset names; none -> '-'",
        _A.APPROXIMATE,
        "Vocabularies differ (e.g. Zeek 'ssl' is absent from the dataset).",
    ),
    "state": LiveMapping(
        "conn.conn_state + history",
        "lossy map Zeek states -> Argus states",
        _A.APPROXIMATE,
        "No one-to-one mapping; must be validated.",
    ),
    "spkts": LiveMapping(
        "conn.orig_pkts", "direct", _A.EXACT, "Counting may differ slightly between tools."
    ),
    "dpkts": LiveMapping(
        "conn.resp_pkts", "direct", _A.EXACT, "Counting may differ slightly between tools."
    ),
    "sbytes": LiveMapping(
        "conn.orig_ip_bytes", "direct", _A.APPROXIMATE, "Header accounting may differ from Argus."
    ),
    "dbytes": LiveMapping(
        "conn.resp_ip_bytes", "direct", _A.APPROXIMATE, "Header accounting may differ from Argus."
    ),
    "sttl": LiveMapping("-", "-", _A.UNAVAILABLE, "TTL is not in conn.log."),
    "dttl": LiveMapping("-", "-", _A.UNAVAILABLE, "TTL is not in conn.log."),
    "sload": LiveMapping(
        "derived", "sbytes * 8 / dur (0 if dur = 0)", _A.DERIVED, "Inherits sbytes approximation."
    ),
    "dload": LiveMapping(
        "derived", "dbytes * 8 / dur (0 if dur = 0)", _A.DERIVED, "Inherits dbytes approximation."
    ),
    "sloss": LiveMapping("-", "-", _A.UNAVAILABLE, "conn.missed_bytes is a different concept."),
    "dloss": LiveMapping("-", "-", _A.UNAVAILABLE, "conn.missed_bytes is a different concept."),
    "sinpkt": LiveMapping(
        "derived",
        "dur / (spkts - 1) mean inter-arrival",
        _A.APPROXIMATE,
        "Mean only; per-packet timing is not in conn.log.",
    ),
    "dinpkt": LiveMapping(
        "derived",
        "dur / (dpkts - 1) mean inter-arrival",
        _A.APPROXIMATE,
        "Mean only; per-packet timing is not in conn.log.",
    ),
    "sjit": LiveMapping("-", "-", _A.UNAVAILABLE, "Needs per-packet timing."),
    "djit": LiveMapping("-", "-", _A.UNAVAILABLE, "Needs per-packet timing."),
    "swin": LiveMapping("-", "-", _A.UNAVAILABLE, "TCP window is not in conn.log."),
    "dwin": LiveMapping("-", "-", _A.UNAVAILABLE, "TCP window is not in conn.log."),
    "tcprtt": LiveMapping("-", "-", _A.UNAVAILABLE, "Handshake timing needs a custom Zeek script."),
    "synack": LiveMapping("-", "-", _A.UNAVAILABLE, "Handshake timing needs a custom Zeek script."),
    "ackdat": LiveMapping("-", "-", _A.UNAVAILABLE, "Handshake timing needs a custom Zeek script."),
    "smean": LiveMapping("derived", "sbytes / spkts", _A.DERIVED, "Inherits sbytes approximation."),
    "dmean": LiveMapping("derived", "dbytes / dpkts", _A.DERIVED, "Inherits dbytes approximation."),
    "trans_depth": LiveMapping("http.trans_depth", "join on uid", _A.DERIVED, "HTTP flows only."),
    "response_body_len": LiveMapping(
        "http.response_body_len", "join on uid", _A.DERIVED, "HTTP flows only."
    ),
    "ct_srv_src": LiveMapping(
        "collector window",
        "count over last 100 connections",
        _A.DERIVED,
        "Window semantics approximated.",
    ),
    "ct_state_ttl": LiveMapping("-", "-", _A.UNAVAILABLE, "Depends on TTL values."),
    "ct_dst_ltm": LiveMapping(
        "collector window",
        "count over last 100 connections",
        _A.DERIVED,
        "Window semantics approximated.",
    ),
    "ct_src_dport_ltm": LiveMapping(
        "collector window",
        "count over last 100 connections",
        _A.DERIVED,
        "Window semantics approximated.",
    ),
    "ct_dst_sport_ltm": LiveMapping(
        "collector window",
        "count over last 100 connections",
        _A.DERIVED,
        "Window semantics approximated.",
    ),
    "ct_dst_src_ltm": LiveMapping(
        "collector window",
        "count over last 100 connections",
        _A.DERIVED,
        "Window semantics approximated.",
    ),
    "is_ftp_login": LiveMapping("ftp.log", "join on uid", _A.DERIVED, "FTP flows only."),
    "ct_ftp_cmd": LiveMapping("ftp.log", "join on uid", _A.DERIVED, "FTP flows only."),
    "ct_flw_http_mthd": LiveMapping("http.log", "join on uid", _A.DERIVED, "HTTP flows only."),
    "ct_src_ltm": LiveMapping(
        "collector window",
        "count over last 100 connections",
        _A.DERIVED,
        "Window semantics approximated.",
    ),
    "ct_srv_dst": LiveMapping(
        "collector window",
        "count over last 100 connections",
        _A.DERIVED,
        "Window semantics approximated.",
    ),
    "is_sm_ips_ports": LiveMapping(
        "derived", "src_ip == dst_ip and src_port == dst_port", _A.DERIVED, "-"
    ),
}

# --- Feature profiles ------------------------------------------------------------------------

TTL_FEATURES = ("sttl", "dttl", "ct_state_ttl")


@dataclass(frozen=True)
class FeatureProfile:
    name: str
    numeric: tuple[str, ...]
    categorical: tuple[str, ...]
    description: str

    @property
    def features(self) -> tuple[str, ...]:
        return (*self.numeric, *self.categorical)


def _live_available(name: str) -> bool:
    return LIVE_FEATURE_MAP[name].availability is not Availability.UNAVAILABLE


PROFILES: dict[str, FeatureProfile] = {
    "full": FeatureProfile(
        name="full",
        numeric=NUMERIC_FEATURES,
        categorical=CATEGORICAL_FEATURES,
        description="All usable UNSW-NB15 flow features. For dataset analysis only.",
    ),
    "full_no_ttl": FeatureProfile(
        name="full_no_ttl",
        numeric=tuple(f for f in NUMERIC_FEATURES if f not in TTL_FEATURES),
        categorical=CATEGORICAL_FEATURES,
        description="Ablation: 'full' without TTL-based features, which are tied to the testbed.",
    ),
    "live_compatible": FeatureProfile(
        name="live_compatible",
        numeric=tuple(f for f in NUMERIC_FEATURES if _live_available(f)),
        categorical=tuple(f for f in CATEGORICAL_FEATURES if _live_available(f)),
        description="Only features obtainable from Zeek logs (exact, derived, or approximate). "
        "Live use still requires the Phase 6 compatibility gate.",
    ),
}


def get_profile(name: str) -> FeatureProfile:
    try:
        return PROFILES[name]
    except KeyError:
        raise ValueError(
            f"Unknown feature profile {name!r}; choose from {sorted(PROFILES)}"
        ) from None
