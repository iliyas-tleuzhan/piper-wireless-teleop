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
