"""Configuration loading for Piper wireless teleoperation.

The scripts use a YAML file for operational defaults so normal commands stay
short and safety-related values are not hidden in long CLI invocations.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .safety import GRIPPER_LIMITS_RAW, JOINT_LIMITS_RAW, raw_to_deg, raw_to_mm


@dataclass(frozen=True)
class NetworkConfig:
    """UDP timing and receiver-side timeout settings."""

    udp_port: int
    send_rate_hz: float
    receiver_timeout_s: float
    status_rate_hz: float
    socket_timeout_s: float

    @property
    def max_packet_age_s(self) -> float:
        """Backward-compatible alias for older config users.

        New code should use ``receiver_timeout_s`` because the timeout is based
        on receiver-side monotonic time, not sender wall-clock packet age.
        """

        return self.receiver_timeout_s


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
    joint_limits_deg: tuple[tuple[float, float], ...]
    gripper_limits_mm: tuple[float, float]


@dataclass(frozen=True)
class SafetyConfig:
    """Runtime safety checks and optional slew limiting settings."""

    enable_slew_limit: bool
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


def _parse_joint_limits_deg(value: Any | None) -> tuple[tuple[float, float], ...]:
    """Parse six joint limit pairs from config or fall back to safety defaults."""

    if value is None:
        return tuple((raw_to_deg(low), raw_to_deg(high)) for low, high in JOINT_LIMITS_RAW)
    if not isinstance(value, list) or len(value) != 6:
        raise ValueError("piper.joint_limits_deg must contain six [min, max] pairs")

    parsed: list[tuple[float, float]] = []
    for pair in value:
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError("each piper.joint_limits_deg item must be [min, max]")
        low, high = float(pair[0]), float(pair[1])
        if low > high:
            raise ValueError("piper.joint_limits_deg min must be <= max")
        parsed.append((low, high))
    return tuple(parsed)


def _parse_gripper_limits_mm(value: Any | None) -> tuple[float, float]:
    """Parse gripper range from config or fall back to safety defaults."""

    if value is None:
        low, high = GRIPPER_LIMITS_RAW
        return raw_to_mm(low), raw_to_mm(high)
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("piper.gripper_limits_mm must be [min, max]")
    low, high = float(value[0]), float(value[1])
    if low > high:
        raise ValueError("piper.gripper_limits_mm min must be <= max")
    return low, high


def load_config(path: str | Path) -> AppConfig:
    """Load an ``AppConfig`` from a YAML file."""

    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    network_raw = raw["network"]
    logging_raw = raw.get("logging", {})
    safety_raw = raw.get("safety", {})
    receiver_timeout_s = network_raw.get(
        "receiver_timeout_s",
        network_raw.get("max_packet_age_s", 0.5),
    )
    status_rate_hz = network_raw.get(
        "status_rate_hz",
        logging_raw.get("status_hz", 2),
    )

    return AppConfig(
        network=NetworkConfig(
            udp_port=int(network_raw["udp_port"]),
            send_rate_hz=float(network_raw["send_rate_hz"]),
            receiver_timeout_s=float(receiver_timeout_s),
            status_rate_hz=float(status_rate_hz),
            socket_timeout_s=float(network_raw["socket_timeout_s"]),
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
            joint_limits_deg=_parse_joint_limits_deg(raw["piper"].get("joint_limits_deg")),
            gripper_limits_mm=_parse_gripper_limits_mm(raw["piper"].get("gripper_limits_mm")),
        ),
        safety=SafetyConfig(
            enable_slew_limit=bool(safety_raw.get("enable_slew_limit", False)),
            max_step_deg=float(safety_raw.get("max_step_deg", 3.0)),
            startup_sync_required=bool(safety_raw.get("startup_sync_required", False)),
            startup_sync_tolerance_deg=float(safety_raw.get("startup_sync_tolerance_deg", 10.0)),
        ),
        logging=LoggingConfig(
            status_hz=float(status_rate_hz),
            verbose_packets=bool(logging_raw.get("verbose_packets", False)),
        ),
    )
