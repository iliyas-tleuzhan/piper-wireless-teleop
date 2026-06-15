"""Tests for joint safety helpers."""

from piper_wireless_teleop.safety import (
    clamp_joints_raw,
    deg_to_raw,
    limit_step_raw,
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


def test_units() -> None:
    """Piper raw unit conversion is deterministic."""

    assert raw_to_deg(1250) == 1.25
    assert deg_to_raw(1.25) == 1250
