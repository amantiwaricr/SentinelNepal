from sentinel_ml.schema import (
    ALL_FEATURES,
    CATEGORICAL_FEATURES,
    EXCLUDED_COLUMNS,
    FULL_RECORD_COLUMNS,
    LIVE_FEATURE_MAP,
    METADATA_COLUMNS,
    PARTITIONED_COLUMNS,
    PROFILES,
    TTL_FEATURES,
    Availability,
    get_profile,
    normalize_column_name,
)


def test_every_feature_has_a_live_mapping() -> None:
    assert set(LIVE_FEATURE_MAP) == set(ALL_FEATURES)


def test_no_profile_uses_targets_identifiers_or_excluded_columns() -> None:
    # Leakage guard: labels, row ids, IPs, ports, and timestamps are never model inputs.
    forbidden = set(EXCLUDED_COLUMNS) | set(METADATA_COLUMNS)
    for profile in PROFILES.values():
        assert not forbidden & set(profile.features), profile.name


def test_every_file_column_is_either_a_feature_or_explicitly_excluded() -> None:
    for column in (*PARTITIONED_COLUMNS, *FULL_RECORD_COLUMNS):
        assert column in ALL_FEATURES or column in EXCLUDED_COLUMNS, column


def test_live_compatible_profile_excludes_unavailable_features() -> None:
    live = get_profile("live_compatible")
    for name in live.features:
        assert LIVE_FEATURE_MAP[name].availability is not Availability.UNAVAILABLE
    unavailable = [
        n for n, m in LIVE_FEATURE_MAP.items() if m.availability is Availability.UNAVAILABLE
    ]
    assert unavailable and not set(unavailable) & set(live.features)


def test_ablation_profile_drops_only_ttl_features() -> None:
    assert set(get_profile("full").features) - set(get_profile("full_no_ttl").features) == set(
        TTL_FEATURES
    )


def test_profiles_keep_canonical_feature_order() -> None:
    for profile in PROFILES.values():
        order = [ALL_FEATURES.index(f) for f in profile.numeric]
        assert order == sorted(order)
        assert set(profile.categorical) <= set(CATEGORICAL_FEATURES)


def test_column_name_aliases_between_file_families() -> None:
    assert normalize_column_name(" Smeansz ") == "smean"
    assert normalize_column_name("res_bdy_len") == "response_body_len"
    assert normalize_column_name("Sintpkt") == "sinpkt"
    assert normalize_column_name("ct_src_ ltm") == "ct_src_ltm"
    assert normalize_column_name("Label") == "label"
    assert normalize_column_name("srcip") == "src_ip"


def test_unknown_profile_rejected() -> None:
    import pytest

    with pytest.raises(ValueError, match="Unknown feature profile"):
        get_profile("everything")
