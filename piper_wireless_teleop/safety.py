"""Safety helpers for raw Piper joint targets.

Piper joint targets are represented in raw units of 0.001 degrees. The helpers
here clamp decoded targets to documented joint ranges, validate packet shape,
and provide optional step-limiting primitives for explicit fallback use.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from .arm_profile import PIPER_X_PROFILE, ArmProfile, deg_to_raw, raw_to_deg

JOINT_LIMITS_RAW = PIPER_X_PROFILE.joint_limits_raw


def clamp_joints_raw(
    joints: Sequence[int], profile: ArmProfile = PIPER_X_PROFILE
) -> list[int]:
    """Clamp six raw joint targets to Piper joint limits."""

    validate_joints_raw(joints)
    clamped: list[int] = []
    for value, (low, high) in zip(joints, profile.joint_limits_raw, strict=True):
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


def validate_joints_raw(joints: Sequence[object]) -> None:
    """Validate that a joint list contains exactly six integer-like values."""

    if not isinstance(joints, Sequence) or isinstance(joints, (str, bytes)):
        raise ValueError("joints must be a sequence")
    if len(joints) != 6:
        raise ValueError("joints must contain exactly 6 values")
    for value in joints:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("joint values must be integers in Piper raw units")


def validate_joints_in_limits(
    joints: Sequence[int], profile: ArmProfile = PIPER_X_PROFILE
) -> None:
    """Validate that raw joints are finite integers inside profile limits."""

    validate_joints_raw(joints)
    for index, (value, (low, high)) in enumerate(
        zip(joints, profile.joint_limits_raw, strict=True), start=1
    ):
        if not math.isfinite(float(value)):
            raise ValueError(f"joint{index} is not finite")
        if not low <= int(value) <= high:
            raise ValueError(
                f"joint{index}={value} outside {profile.name} limit [{low}, {high}]"
            )


def validate_gripper_packet(
    gripper: object, profile: ArmProfile = PIPER_X_PROFILE
) -> dict[str, int] | None:
    """Validate an optional gripper command without blocking joint updates."""

    if gripper is None:
        return None
    if not isinstance(gripper, dict):
        raise ValueError("gripper must be an object when present")
    angle = gripper.get("angle", 0)
    effort = gripper.get("effort", 0)
    code = gripper.get("code", 1)
    if (
        isinstance(angle, bool)
        or isinstance(effort, bool)
        or isinstance(code, bool)
        or not isinstance(angle, int)
        or not isinstance(effort, int)
        or not isinstance(code, int)
    ):
        raise ValueError("gripper angle, effort and code must be integers")
    if not profile.gripper_min_raw <= angle <= profile.gripper_max_raw:
        raise ValueError("gripper angle outside configured range")
    if not profile.gripper_force_min <= effort <= profile.gripper_force_max:
        raise ValueError("gripper effort outside configured range")
    return {"angle": angle, "effort": effort, "code": code}


def validate_joint_packet(
    packet: dict[str, object], profile: ArmProfile = PIPER_X_PROFILE
) -> list[int]:
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
    validate_joints_in_limits(joints, profile)
    return [int(value) for value in joints]
