"""Wrapper around the official ``piper_sdk`` interface for the slave arm."""

from __future__ import annotations

from math import radians
from collections.abc import Sequence
from typing import Any

from .config import PiperConfig
from .safety import clamp_gripper_command


class PiperSlaveWriter:
    """Thin adapter for Piper SDK versions used in the field."""

    def __init__(self, can_interface: str, piper_config: PiperConfig) -> None:
        self.can_interface = can_interface
        self.piper_config = piper_config
        self._piper: Any | None = None

    def connect(self) -> None:
        """Create the SDK interface and connect to the configured CAN device."""

        from piper_sdk import C_PiperInterface_V2

        try:
            self._piper = C_PiperInterface_V2(
                self.can_interface,
                start_sdk_joint_limit=True,
                start_sdk_gripper_limit=True,
            )
        except TypeError:
            self._piper = C_PiperInterface_V2(self.can_interface)
        connect = getattr(self._piper, "ConnectPort", None)
        if callable(connect):
            connect()
        self.configure_sdk_limits()

    @property
    def piper(self) -> Any:
        """Return the connected Piper SDK object."""

        if self._piper is None:
            raise RuntimeError("Piper SDK is not connected")
        return self._piper

    def configure_sdk_limits(self) -> None:
        """Apply configured SDK-side soft limits when supported by piper_sdk."""

        set_joint_limit = getattr(self.piper, "SetSDKJointLimitParam", None)
        if callable(set_joint_limit):
            for index, (low, high) in enumerate(self.piper_config.joint_limits_deg, start=1):
                set_joint_limit(f"j{index}", radians(float(low)), radians(float(high)))

        set_gripper_range = getattr(self.piper, "SetSDKGripperRangeParam", None)
        if callable(set_gripper_range):
            low, high = self.piper_config.gripper_limits_mm
            set_gripper_range(float(low) / 1000.0, float(high) / 1000.0)

    def enable(self) -> None:
        """Enable the slave arm using whichever SDK method is available."""

        if hasattr(self.piper, "EnableArm"):
            self.piper.EnableArm(7)
        elif hasattr(self.piper, "EnableArmStandbyMode"):
            self.piper.EnableArmStandbyMode(7)
        else:
            raise AttributeError("Piper SDK does not expose an arm enable method")

    def set_motion_mode(self) -> None:
        """Set control, move, speed, and follow/high-follow mode from config.

        Some SDK releases expose ``MotionCtrl_2`` while others expose
        ``ModeCtrl``. The bridge accepts either to avoid pinning the repo to one
        exact SDK build.
        """

        cfg = self.piper_config
        if hasattr(self.piper, "MotionCtrl_2"):
            self.piper.MotionCtrl_2(
                cfg.control_mode,
                cfg.move_mode,
                cfg.speed_percent,
                cfg.follow_mode,
            )
        elif hasattr(self.piper, "ModeCtrl"):
            self.piper.ModeCtrl(
                cfg.control_mode,
                cfg.move_mode,
                cfg.speed_percent,
                cfg.follow_mode,
            )
        else:
            raise AttributeError("Piper SDK exposes neither MotionCtrl_2 nor ModeCtrl")

    def send_joints(self, joints_raw: Sequence[int]) -> None:
        """Send six raw joint targets to the slave Piper."""

        if len(joints_raw) != 6:
            raise ValueError("JointCtrl requires exactly 6 joint values")
        self.piper.JointCtrl(*[int(value) for value in joints_raw])

    def send_gripper(self, gripper: dict[str, int]) -> None:
        """Send a gripper command when the master packet includes one."""

        command = clamp_gripper_command(gripper, self.piper_config.gripper_default_effort)
        angle = command["angle"]
        effort = command["effort"]
        code = command["code"]
        self.piper.GripperCtrl(angle, effort, code, 0)

    def read_joint_feedback(self) -> Any:
        """Read joint feedback using the first SDK feedback method available."""

        for method_name in (
            "GetArmJointMsgs",
            "GetArmJointCtrl",
            "GetArmStatus",
        ):
            method = getattr(self.piper, method_name, None)
            if callable(method):
                return method()
        raise AttributeError("Piper SDK does not expose a known joint feedback method")
