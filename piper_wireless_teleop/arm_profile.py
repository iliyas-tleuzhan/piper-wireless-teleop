"""Arm-specific joint and SDK profile data."""

from __future__ import annotations

import math
from dataclasses import dataclass
from collections.abc import Sequence

RAW_UNITS_PER_DEGREE = 1000


@dataclass(frozen=True)
class JointProfile:
    """Mapping and limits for one arm joint."""

    name: str
    min_deg: float
    max_deg: float
    sign: int = 1
    offset_deg: float = 0.0

    @property
    def min_raw(self) -> int:
        return deg_to_raw(self.min_deg)

    @property
    def max_raw(self) -> int:
        return deg_to_raw(self.max_deg)


@dataclass(frozen=True)
class ArmProfile:
    """Runtime profile for one supported arm model."""

    name: str
    sdk: str
    sdk_robot: str
    sdk_firmware: str
    joint_profiles: tuple[JointProfile, ...]
    gripper_min_raw: int
    gripper_max_raw: int
    gripper_force_min: int
    gripper_force_max: int
    notes: str

    @property
    def joint_limits_raw(self) -> tuple[tuple[int, int], ...]:
        return tuple((joint.min_raw, joint.max_raw) for joint in self.joint_profiles)

    @property
    def joint_limits_deg(self) -> tuple[tuple[float, float], ...]:
        return tuple((joint.min_deg, joint.max_deg) for joint in self.joint_profiles)

    @property
    def joint_signs(self) -> tuple[int, ...]:
        return tuple(joint.sign for joint in self.joint_profiles)

    @property
    def joint_offsets_deg(self) -> tuple[float, ...]:
        return tuple(joint.offset_deg for joint in self.joint_profiles)


def raw_to_deg(value: int | float) -> float:
    """Convert Piper raw joint units to degrees."""

    return float(value) / RAW_UNITS_PER_DEGREE


def deg_to_raw(value: int | float) -> int:
    """Convert degrees to Piper raw joint units."""

    return int(round(float(value) * RAW_UNITS_PER_DEGREE))


def raw_to_rad(value: int | float) -> float:
    """Convert Piper raw joint units to radians."""

    return math.radians(raw_to_deg(value))


def rad_to_raw(value: int | float) -> int:
    """Convert radians to Piper raw joint units."""

    return deg_to_raw(math.degrees(float(value)))


def apply_profile_to_raw(joints_raw: Sequence[int], profile: ArmProfile) -> list[int]:
    """Convert transport raw joints into arm SDK raw joint order/sign/offset."""

    if len(joints_raw) != len(profile.joint_profiles):
        raise ValueError("joint count does not match arm profile")
    result: list[int] = []
    for value, joint in zip(joints_raw, profile.joint_profiles, strict=True):
        signed_deg = raw_to_deg(int(value)) * joint.sign + joint.offset_deg
        result.append(deg_to_raw(signed_deg))
    return result


def remove_profile_from_raw(joints_raw: Sequence[int], profile: ArmProfile) -> list[int]:
    """Convert arm SDK raw feedback into transport raw joint order/sign/offset."""

    if len(joints_raw) != len(profile.joint_profiles):
        raise ValueError("joint count does not match arm profile")
    result: list[int] = []
    for value, joint in zip(joints_raw, profile.joint_profiles, strict=True):
        transport_deg = (raw_to_deg(int(value)) - joint.offset_deg) * joint.sign
        result.append(deg_to_raw(transport_deg))
    return result


PIPER_PROFILE = ArmProfile(
    name="piper",
    sdk="piper_sdk",
    sdk_robot="piper",
    sdk_firmware="default",
    joint_profiles=(
        JointProfile("joint1", -150.0, 150.0),
        JointProfile("joint2", 0.0, 180.0),
        JointProfile("joint3", -170.0, 0.0),
        JointProfile("joint4", -100.0, 100.0),
        JointProfile("joint5", -70.0, 70.0),
        JointProfile("joint6", -120.0, 120.0),
    ),
    gripper_min_raw=0,
    gripper_max_raw=100000,
    gripper_force_min=0,
    gripper_force_max=5000,
    notes="Standard PiPER V2 profile from piper_sdk limits and URDF.",
)


PIPER_X_PROFILE = ArmProfile(
    name="piper_x",
    sdk="pyAgxArm",
    sdk_robot="piper_x",
    sdk_firmware="v189",
    joint_profiles=(
        JointProfile("joint1", -150.0, 150.0),
        JointProfile("joint2", 0.0, 180.0),
        JointProfile("joint3", -170.0, 0.0),
        JointProfile("joint4", -89.0, 89.0),
        JointProfile("joint5", -89.0, 89.0),
        JointProfile("joint6", -120.0, 120.0),
    ),
    gripper_min_raw=0,
    gripper_max_raw=100000,
    gripper_force_min=0,
    gripper_force_max=5000,
    notes=(
        "PiPER-X profile from official pyAgxArm ArmModel.PIPER_X and "
        "agx_arm_urdf piper_x_description.urdf limits."
    ),
)


ARM_PROFILES: dict[str, ArmProfile] = {
    PIPER_PROFILE.name: PIPER_PROFILE,
    PIPER_X_PROFILE.name: PIPER_X_PROFILE,
}


def get_arm_profile(name: str) -> ArmProfile:
    """Return a supported arm profile by name."""

    try:
        return ARM_PROFILES[name]
    except KeyError as exc:
        supported = ", ".join(sorted(ARM_PROFILES))
        raise ValueError(f"unsupported arm profile {name!r}; expected one of: {supported}") from exc
