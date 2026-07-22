"""Tests for PiPER-X master feedback conversion."""

import math
import pytest

from piper_wireless_teleop.master_arm_reader import radians_payload_to_raw


def test_master_feedback_conversion_six_joints() -> None:
    """pyAgxArm radians feedback converts into six transport raw joints."""

    assert radians_payload_to_raw([0.0, math.pi / 2, -math.pi / 2, 0.1, -0.1, 0.0]) == [
        0,
        90000,
        -90000,
        5730,
        -5730,
        0,
    ]


def test_master_feedback_rejects_nan() -> None:
    """Invalid master feedback is not transmitted."""

    with pytest.raises(ValueError, match="non-finite"):
        radians_payload_to_raw([0.0, 0.0, float("nan"), 0.0, 0.0, 0.0])


def test_master_feedback_rejects_wrong_joint_count() -> None:
    """Incomplete master feedback is rejected before packet creation."""

    with pytest.raises(ValueError, match="exactly 6"):
        radians_payload_to_raw([0.0] * 5)
