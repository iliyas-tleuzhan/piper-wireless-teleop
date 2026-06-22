"""Tests for joint safety helpers."""

from piper_wireless_teleop.safety import (
    clamp_gripper_command,
    clamp_joints_raw,
    deg_to_raw,
    limit_step_raw,
    mm_to_raw,
    raw_to_deg,
    raw_to_mm,
)


def test_joint_clamping() -> None:
    """Joint values are clamped to Piper raw limits."""

    assert clamp_joints_raw([200000, -1, -200000, 200000, -80000, 130000]) == [
        154000,
        0,
        -175000,
        106000,
        -75000,
        120000,
    ]


def test_gripper_clamping() -> None:
    """Gripper values are clamped without shrinking the normal 0-100 mm range."""

    assert clamp_gripper_command({"angle": 120000, "effort": 7000, "code": 9}, 1000) == {
        "angle": 100000,
        "effort": 5000,
        "code": 1,
    }


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
    assert raw_to_mm(1250) == 1.25
    assert mm_to_raw(1.25) == 1250
