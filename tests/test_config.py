"""Tests for default configuration semantics."""

from piper_wireless_teleop.config import load_config


def test_default_config_commands_directly() -> None:
    """The checked-in default config does not slow normal teleop with slew limiting."""

    config = load_config("configs/default.yaml")

    assert config.network.receiver_timeout_s == 0.5
    assert config.network.status_rate_hz == 2
    assert not config.safety.enable_slew_limit
    assert not config.safety.startup_sync_required
    assert config.piper.speed_percent == 100
    assert config.piper.follow_mode == 0xAD
    assert config.piper.joint_limits_deg == (
        (-154.0, 154.0),
        (0.0, 195.0),
        (-175.0, 0.0),
        (-106.0, 106.0),
        (-75.0, 75.0),
        (-120.0, 120.0),
    )
    assert config.piper.gripper_limits_mm == (0.0, 100.0)
