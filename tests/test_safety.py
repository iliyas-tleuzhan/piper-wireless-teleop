"""Tests for joint safety helpers."""

from piper_wireless_teleop.safety import (
    clamp_joints_raw,
    deg_to_raw,
    limit_step_raw,
    packet_is_fresh,
    raw_to_deg,
)


def test_joint_clamping() -> None:
    """Joint values are clamped to Piper raw limits."""

    assert clamp_joints_raw([200000, -1, -200000, 200000, -80000, 130000]) == [
        150000,
        0,
        -170000,
        100000,
        -70000,
        120000,
    ]


def test_slew_limiting() -> None:
    """Slew limiting steps each joint toward the target."""

    assert limit_step_raw([0, 0, 0, 0, 0, 0], [5000, -2000, 100, 0, -50, 50], 1000) == [
        1000,
        -1000,
        100,
        0,
        -50,
        50,
    ]


def test_units_and_freshness() -> None:
    """Unit conversion and freshness checks are deterministic with injected time."""

    assert raw_to_deg(1250) == 1.25
    assert deg_to_raw(1.25) == 1250
    assert packet_is_fresh(10.0, max_age_s=0.25, now=10.2)
    assert not packet_is_fresh(10.0, max_age_s=0.25, now=10.3)
