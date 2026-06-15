"""Safety helpers for raw Piper joint targets.

Piper joint targets are represented in raw units of 0.001 degrees. The helpers
here clamp decoded targets to documented joint ranges, validate packet shape,
check packet freshness, and slew-limit motion commands sent to the slave arm.
"""

from __future__ import annotations

import time
from collections.abc import Sequence

RAW_UNITS_PER_DEGREE = 1000

JOINT_LIMITS_RAW: tuple[tuple[int, int], ...] = (
    (-150000, 150000),
    (0, 180000),
    (-170000, 0),
    (-100000, 100000),
    (-70000, 70000),
    (-120000, 120000),
)


def raw_to_deg(value: int | float) -> float:
    """Convert Piper raw joint units to degrees."""

    return float(value) / RAW_UNITS_PER_DEGREE


def deg_to_raw(value: int | float) -> int:
    """Convert degrees to Piper raw joint units."""

    return int(round(float(value) * RAW_UNITS_PER_DEGREE))


def clamp_joints_raw(joints: Sequence[int]) -> list[int]:
    """Clamp six raw joint targets to Piper joint limits."""

    validate_joints_raw(joints)
    clamped: list[int] = []
    for value, (low, high) in zip(joints, JOINT_LIMITS_RAW, strict=True):
        clamped.append(max(low, min(high, int(value))))
    return clamped


def limit_step_raw(current: Sequence[int], target: Sequence[int], max_step_raw: int) -> list[int]:
    """Move from ``current`` toward ``target`` by at most ``max_step_raw`` per joint."""

    validate_joints_raw(current)
    validate_joints_raw(target)
    if max_step_raw < 0:
        raise ValueError("max_step_raw must be non-negative")

    next_joints: list[int] = []
    for current_value, target_value in zip(current, target, strict=True):
        delta = int(target_value) - int(current_value)
        if abs(delta) <= max_step_raw:
            next_joints.append(int(target_value))
        else:
            step = max_step_raw if delta > 0 else -max_step_raw
            next_joints.append(int(current_value) + step)
    return next_joints


def packet_is_fresh(timestamp: float, max_age_s: float, now: float | None = None) -> bool:
    """Return true when a packet timestamp is recent enough to command motion."""

    current_time = time.time() if now is None else now
    return 0.0 <= current_time - float(timestamp) <= max_age_s


def validate_joints_raw(joints: Sequence[object]) -> None:
    """Validate that a joint list contains exactly six integer-like values."""

    if not isinstance(joints, Sequence) or isinstance(joints, (str, bytes)):
        raise ValueError("joints must be a sequence")
    if len(joints) != 6:
        raise ValueError("joints must contain exactly 6 values")
    for value in joints:
        if not isinstance(value, int):
            raise ValueError("joint values must be integers in Piper raw units")


def validate_joint_packet(packet: dict[str, object]) -> list[int]:
    """Validate a decoded teleop packet and return its raw joint list."""

    if packet.get("type") != "piper_joint_targets":
        raise ValueError("unexpected packet type")
    timestamp = packet.get("timestamp")
    if not isinstance(timestamp, (int, float)):
        raise ValueError("packet timestamp is missing or invalid")
    deadman = packet.get("deadman")
    if not isinstance(deadman, bool):
        raise ValueError("packet deadman field is missing or invalid")
    joints = packet.get("joints")
    if not isinstance(joints, list):
        raise ValueError("packet joints field is missing or invalid")
    validate_joints_raw(joints)
    return [int(value) for value in joints]
