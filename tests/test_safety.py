"""Tests for joint safety helpers."""

from piper_wireless_teleop.safety import (
    clamp_joints_raw,
    deg_to_raw,
    limit_step_raw,
    raw_to_deg,
    validate_joint_packet,
)
from piper_wireless_teleop.arm_profile import PIPER_PROFILE, PIPER_X_PROFILE
import pytest


def test_joint_clamping() -> None:
    """Joint values are clamped to Piper raw limits."""

    assert clamp_joints_raw([200000, -1, -200000, 200000, -80000, 130000]) == [
        150000,
        0,
        -170000,
        89000,
        -80000,
        120000,
    ]


def test_standard_piper_profile_clamping() -> None:
    """The legacy PiPER profile keeps its own wrist limits."""

    assert clamp_joints_raw(
        [200000, -1, -200000, 200000, -80000, 130000],
        PIPER_PROFILE,
    ) == [150000, 0, -170000, 100000, -70000, 120000]


def test_piper_x_limits_reject_out_of_range_packets() -> None:
    """Receiver validation rejects values beyond configured PiPER-X limits."""

    packet = {
        "type": "piper_joint_targets",
        "timestamp": 1.0,
        "deadman": True,
        "joints": [0, 0, 0, 90000, 0, 0],
    }

    with pytest.raises(ValueError, match="joint4"):
        validate_joint_packet(packet, PIPER_X_PROFILE)

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
