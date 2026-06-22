"""Tests for slave receiver command selection without Piper hardware."""

from piper_wireless_teleop.config import SafetyConfig
from scripts.slave_receiver import choose_command_joints


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
