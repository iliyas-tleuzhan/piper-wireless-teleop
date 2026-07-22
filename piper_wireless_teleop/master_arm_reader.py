"""Master arm feedback readers."""

from __future__ import annotations

import math
import time
from collections.abc import Sequence
from typing import Any

from .arm_profile import ArmProfile, rad_to_raw
from .safety import validate_gripper_packet, validate_joints_in_limits


class PiperXMasterReader:
    """Read PiPER-X master feedback with the official pyAgxArm API."""

    def __init__(
        self,
        *,
        can_interface: str,
        can_bitrate: int,
        sdk_interface: str,
        profile: ArmProfile,
        stale_after_s: float = 0.25,
    ) -> None:
        self.can_interface = can_interface
        self.can_bitrate = can_bitrate
        self.sdk_interface = sdk_interface
        self.profile = profile
        self.stale_after_s = stale_after_s
        self._robot: Any | None = None
        self._effector: Any | None = None

    def connect(self) -> None:
        """Create and connect the pyAgxArm PiPER-X driver."""

        from pyAgxArm import AgxArmFactory, ArmModel, PiperFW, create_agx_arm_config

        firmware = getattr(PiperFW, str(self.profile.sdk_firmware).upper(), PiperFW.DEFAULT)
        robot = getattr(ArmModel, "PIPER_X")
        config = create_agx_arm_config(
            robot=robot,
            firmeware_version=firmware,
            interface=self.sdk_interface,
            channel=self.can_interface,
            bitrate=self.can_bitrate,
        )
        self._robot = AgxArmFactory.create_arm(config)
        self._robot.connect()
        init_effector = getattr(self._robot, "init_effector", None)
        options = getattr(self._robot, "OPTIONS", None)
        if callable(init_effector) and options is not None:
            effectors = getattr(options, "EFFECTOR", None)
            gripper_option = getattr(effectors, "AGX_GRIPPER", None)
            if gripper_option is not None:
                try:
                    self._effector = init_effector(gripper_option)
                except Exception:
                    self._effector = None

    @property
    def robot(self) -> Any:
        if self._robot is None:
            raise RuntimeError("master arm is not connected")
        return self._robot

    def read_state(self) -> tuple[list[int], dict[str, int] | None]:
        """Read validated six-joint-plus-gripper feedback."""

        feedback = self._read_master_joint_feedback()
        joints_rad = extract_message_payload(feedback)
        joints_raw = radians_payload_to_raw(joints_rad)
        validate_joints_in_limits(joints_raw, self.profile)

        hz = getattr(feedback, "hz", None)
        if isinstance(hz, (int, float)) and float(hz) <= 0:
            raise TimeoutError("master joint feedback has zero receive rate")

        timestamp = getattr(feedback, "timestamp", None)
        if (
            isinstance(timestamp, (int, float))
            and float(timestamp) > 0
            and time.time() - float(timestamp) > self.stale_after_s
        ):
            raise TimeoutError("master joint feedback is stale")

        gripper = self._read_gripper()
        return joints_raw, gripper

    def _read_master_joint_feedback(self) -> Any:
        """Read leader joint frames from a physical master arm."""

        leader_method = getattr(self.robot, "get_leader_joint_angles", None)
        if callable(leader_method):
            feedback = leader_method()
            if feedback is not None:
                return feedback
        raise ValueError("missing PiPER-X leader joint feedback")

    def _read_gripper(self) -> dict[str, int] | None:
        if self._effector is None:
            return None
        for method_name in (
            "get_gripper_ctrl_states",
            "get_gripper_states",
            "get_gripper_status",
        ):
            method = getattr(self._effector, method_name, None)
            if not callable(method):
                continue
            feedback = method()
            gripper = extract_gripper_feedback(feedback)
            if gripper is not None:
                return validate_gripper_packet(gripper, self.profile)
        return None

    def close(self) -> None:
        """Disconnect the SDK object when supported."""

        disconnect = getattr(self._robot, "disconnect", None)
        if callable(disconnect):
            disconnect()


def extract_message_payload(feedback: Any) -> Any:
    """Return the `.msg` payload used by pyAgxArm, or the object itself."""

    if feedback is None:
        raise ValueError("missing arm feedback")
    return getattr(feedback, "msg", feedback)


def radians_payload_to_raw(payload: Any) -> list[int]:
    """Convert a six-value radians payload into raw 0.001-degree units."""

    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        raise ValueError("joint feedback payload must be a sequence")
    if len(payload) != 6:
        raise ValueError("joint feedback payload must contain exactly 6 values")
    joints: list[int] = []
    for value in payload:
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError("joint feedback contains a non-finite value")
        joints.append(rad_to_raw(float(value)))
    return joints


def extract_gripper_feedback(feedback: Any) -> dict[str, int] | None:
    """Extract a simple gripper command shape from common SDK feedback objects."""

    if feedback is None:
        return None
    payload = getattr(feedback, "msg", feedback)
    if isinstance(payload, dict):
        angle = payload.get("angle", payload.get("width", payload.get("gripper")))
        effort = payload.get("effort", payload.get("force", 0))
        code = payload.get("code", 1)
    else:
        angle = None
        for name in ("angle", "width", "gripper", "pos", "position"):
            if hasattr(payload, name):
                angle = getattr(payload, name)
                break
        effort = getattr(payload, "effort", getattr(payload, "force", 0))
        code = getattr(payload, "code", 1)
    if angle is None:
        return None
    if isinstance(angle, float):
        angle = int(round(angle * 1000000))
    if isinstance(effort, float):
        effort = int(round(effort * 1000))
    return {"angle": int(angle), "effort": int(effort), "code": int(code)}
