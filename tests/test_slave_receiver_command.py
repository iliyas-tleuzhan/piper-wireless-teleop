"""Tests for slave receiver command selection without Piper hardware."""

from piper_wireless_teleop.config import SafetyConfig
from scripts.slave_receiver import (
    apply_offset_command,
    choose_command_joints,
    extract_feedback_joints_raw,
)


def safety_config(enable_slew_limit: bool) -> SafetyConfig:
    """Build safety config for command-selection tests."""

    return SafetyConfig(
        enable_slew_limit=enable_slew_limit,
        max_step_deg=3.0,
        startup_sync_required=False,
        startup_sync_tolerance_deg=10.0,
    )


def test_default_command_path_passes_latest_target_directly() -> None:
    """Large normal target changes are not artificially slowed by default."""

    target = [150000, 180000, -170000, 100000, 70000, -100000]

    assert choose_command_joints(
        last_commanded_joints=[0, 0, 0, 0, 0, 0],
        target_joints=target,
        safety_config=safety_config(enable_slew_limit=False),
    ) == target


def test_optional_slew_limit_only_when_enabled() -> None:
    """The hidden fallback still limits steps only when explicitly enabled."""

    assert choose_command_joints(
        last_commanded_joints=[0, 0, 0, 0, 0, 0],
        target_joints=[10000, 0, 0, 0, 0, 0],
        safety_config=safety_config(enable_slew_limit=True),
    ) == [3000, 0, 0, 0, 0, 0]


def test_offset_command_maps_current_master_motion_onto_sampled_slave_current() -> None:
    """Offset mode preserves the sampled slave current pose and applies master deltas."""

    assert apply_offset_command(
        master_current=[11000, 20000, -30000, 40000, 50000, -60000],
        master_init_current=[10000, 20000, -25000, 40000, 45000, -65000],
        slave_init_current=[9000, 21000, -26000, 39000, 46000, -64000],
    ) == [10000, 21000, -31000, 39000, 51000, -59000]


def test_feedback_extraction_handles_nested_joint_state_attrs() -> None:
    """Piper SDK feedback objects can wrap joint values in a joint_state object."""

    class JointState:
        joint_1 = 1000
        joint_2 = 2000
        joint_3 = -3000
        joint_4 = 4000
        joint_5 = 5000
        joint_6 = -6000

    class Feedback:
        joint_state = JointState()

    assert extract_feedback_joints_raw(Feedback()) == [1000, 2000, -3000, 4000, 5000, -6000]
