"""Tests for arm-specific profile conversion."""

import math

from piper_wireless_teleop.arm_profile import (
    PIPER_X_PROFILE,
    apply_profile_to_raw,
    raw_to_deg,
    raw_to_rad,
    remove_profile_from_raw,
)


def test_piper_x_joint_order_sign_and_offsets_are_identity() -> None:
    """PiPER-X transport currently preserves official joint order and signs."""

    joints = [1000, 2000, -3000, 4000, -5000, 6000]

    assert PIPER_X_PROFILE.joint_signs == (1, 1, 1, 1, 1, 1)
    assert apply_profile_to_raw(joints, PIPER_X_PROFILE) == joints
    assert remove_profile_from_raw(joints, PIPER_X_PROFILE) == joints


def test_piper_x_units_and_scaling() -> None:
    """Raw units are 0.001 degree and pyAgxArm commands use radians."""

    assert raw_to_deg(1250) == 1.25
    assert raw_to_rad(180000) == math.pi


def test_piper_x_joint_limits_from_profile() -> None:
    """PiPER-X profile stores six independent joint limits."""

    assert PIPER_X_PROFILE.joint_limits_raw == (
        (-150000, 150000),
        (0, 180000),
        (-170000, 0),
        (-89000, 89000),
        (-89000, 89000),
        (-120000, 120000),
    )
