"""Configuration loading for Piper wireless teleoperation.

The scripts use a YAML file for operational defaults so normal commands stay
short and safety-related values are not hidden in long CLI invocations.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class NetworkConfig:
    """UDP timing and freshness settings."""

    udp_port: int
    send_rate_hz: float
    max_packet_age_s: float
    socket_timeout_s: float


@dataclass(frozen=True)
class CanConfig:
    """SocketCAN interface settings."""

    bitrate: int
    interface: str


@dataclass(frozen=True)
class PiperConfig:
    """Piper SDK motion-mode defaults."""

    control_mode: int
    move_mode: int
    speed_percent: int
    follow_mode: int
    gripper_default_effort: int


@dataclass(frozen=True)
class SafetyConfig:
    """Runtime safety checks and slew limiting settings."""

    max_step_deg: float
    startup_sync_required: bool
    startup_sync_tolerance_deg: float


@dataclass(frozen=True)
class LoggingConfig:
    """Status-printing settings."""

    status_hz: float
    verbose_packets: bool


@dataclass(frozen=True)
class AppConfig:
    """Complete application configuration."""

    network: NetworkConfig
    can: CanConfig
    piper: PiperConfig
    safety: SafetyConfig
    logging: LoggingConfig


def _parse_int(value: Any) -> int:
    """Parse YAML integers, including hex values if a parser returns strings."""

    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 0)
    raise TypeError(f"expected int-compatible value, got {type(value).__name__}")


def load_config(path: str | Path) -> AppConfig:
    """Load an ``AppConfig`` from a YAML file."""

    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    return AppConfig(
        network=NetworkConfig(
            udp_port=int(raw["network"]["udp_port"]),
            send_rate_hz=float(raw["network"]["send_rate_hz"]),
            max_packet_age_s=float(raw["network"]["max_packet_age_s"]),
            socket_timeout_s=float(raw["network"]["socket_timeout_s"]),
        ),
        can=CanConfig(
            bitrate=int(raw["can"]["bitrate"]),
            interface=str(raw["can"]["interface"]),
        ),
        piper=PiperConfig(
            control_mode=_parse_int(raw["piper"]["control_mode"]),
            move_mode=_parse_int(raw["piper"]["move_mode"]),
            speed_percent=int(raw["piper"]["speed_percent"]),
            follow_mode=_parse_int(raw["piper"]["follow_mode"]),
            gripper_default_effort=int(raw["piper"]["gripper_default_effort"]),
        ),
        safety=SafetyConfig(
            max_step_deg=float(raw["safety"]["max_step_deg"]),
            startup_sync_required=bool(raw["safety"]["startup_sync_required"]),
            startup_sync_tolerance_deg=float(raw["safety"]["startup_sync_tolerance_deg"]),
        ),
        logging=LoggingConfig(
            status_hz=float(raw["logging"]["status_hz"]),
            verbose_packets=bool(raw["logging"]["verbose_packets"]),
        ),
    )
