"""Wrapper around the official ``piper_sdk`` interface for the slave arm."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .arm_profile import ArmProfile, raw_to_rad, rad_to_raw
from .config import PiperConfig


class PiperSlaveWriter:
    """Thin adapter for Piper SDK versions used in the field."""

    def __init__(
        self,
        can_interface: str,
        piper_config: PiperConfig,
        arm_profile: ArmProfile,
        *,
        bitrate: int = 1000000,
        sdk_interface: str = "socketcan",
    ) -> None:
        self.can_interface = can_interface
        self.piper_config = piper_config
        self.arm_profile = arm_profile
        self.bitrate = bitrate
        self.sdk_interface = sdk_interface
        self._piper: Any | None = None
        self._effector: Any | None = None

    def connect(self) -> None:
        """Create the SDK interface and connect to the configured CAN device."""

        if self.arm_profile.sdk == "pyAgxArm":
            from pyAgxArm import AgxArmFactory, ArmModel, PiperFW, create_agx_arm_config

            firmware = getattr(PiperFW, str(self.arm_profile.sdk_firmware).upper(), PiperFW.DEFAULT)
            robot = getattr(ArmModel, "PIPER_X")
            cfg = create_agx_arm_config(
                robot=robot,
                firmeware_version=firmware,
                interface=self.sdk_interface,
                channel=self.can_interface,
                bitrate=self.bitrate,
            )
            self._piper = AgxArmFactory.create_arm(cfg)
            self._piper.connect()
            init_effector = getattr(self._piper, "init_effector", None)
            options = getattr(self._piper, "OPTIONS", None)
            if callable(init_effector) and options is not None:
                effectors = getattr(options, "EFFECTOR", None)
                gripper_option = getattr(effectors, "AGX_GRIPPER", None)
                if gripper_option is not None:
                    try:
                        self._effector = init_effector(gripper_option)
                    except Exception:
                        self._effector = None
            return

        from piper_sdk import C_PiperInterface_V2

        self._piper = C_PiperInterface_V2(self.can_interface)
        connect = getattr(self._piper, "ConnectPort", None)
        if callable(connect):
            connect()

    @property
    def piper(self) -> Any:
        """Return the connected Piper SDK object."""

        if self._piper is None:
            raise RuntimeError("Piper SDK is not connected")
        return self._piper

    def enable(self) -> None:
        """Enable the slave arm using whichever SDK method is available."""

        if self.arm_profile.sdk == "pyAgxArm":
            enable = getattr(self.piper, "enable", None)
            if callable(enable):
                enable()
                return
            raise AttributeError("pyAgxArm object does not expose enable()")

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
        if self.arm_profile.sdk == "pyAgxArm":
            set_limits = getattr(self.piper, "set_joint_limits_enabled", None)
            if callable(set_limits):
                set_limits(True)
            set_speed = getattr(self.piper, "set_speed_percent", None)
            if callable(set_speed):
                set_speed(cfg.speed_percent)
            set_motion_mode = getattr(self.piper, "set_motion_mode", None)
            options = getattr(self.piper, "OPTIONS", None)
            motion_options = getattr(options, "MOTION_MODE", None) if options is not None else None
            joint_mode = getattr(motion_options, "J", None)
            if callable(set_motion_mode) and joint_mode is not None:
                set_motion_mode(joint_mode)
            return

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
        if self.arm_profile.sdk == "pyAgxArm":
            self.piper.move_j([raw_to_rad(value) for value in joints_raw])
            return
        self.piper.JointCtrl(*[int(value) for value in joints_raw])

    def send_gripper(self, gripper: dict[str, int]) -> None:
        """Send a gripper command when the master packet includes one."""

        angle = int(gripper.get("angle", 0))
        effort = int(gripper.get("effort", self.piper_config.gripper_default_effort))
        code = int(gripper.get("code", 1))
        if self.arm_profile.sdk == "pyAgxArm":
            if self._effector is None:
                return
            move_gripper_m = getattr(self._effector, "move_gripper_m", None)
            if callable(move_gripper_m):
                move_gripper_m(angle / 1000000.0, effort / 1000.0)
            return
        self.piper.GripperCtrl(angle, effort, code, 0)

    def read_joint_feedback(self) -> Any:
        """Read joint feedback using the first SDK feedback method available."""

        for method_name in (
            "get_joint_angles",
            "GetArmJointMsgs",
            "GetArmJointCtrl",
            "GetArmStatus",
        ):
            method = getattr(self.piper, method_name, None)
            if callable(method):
                return method()
        raise AttributeError("Piper SDK does not expose a known joint feedback method")

    def disable(self) -> None:
        """Disable or release the arm through the selected SDK."""

        for method_name in (
            "disable",
            "DisablePiper",
            "DisableArm",
            "EnableArmStandbyMode",
        ):
            method = getattr(self.piper, method_name, None)
            if callable(method):
                try:
                    if method_name in {"DisableArm", "EnableArmStandbyMode"}:
                        method(7)
                    else:
                        method()
                    return
                except TypeError:
                    method(7)
                    return

    def close(self) -> None:
        """Disconnect the SDK object when supported."""

        disconnect = getattr(self._piper, "disconnect", None)
        if callable(disconnect):
            disconnect()


def extract_pyagxarm_feedback_raw(feedback: Any) -> list[int] | None:
    """Extract raw 0.001-degree joints from pyAgxArm radians feedback."""

    payload = getattr(feedback, "msg", feedback)
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        return None
    if len(payload) != 6:
        return None
    if not all(isinstance(value, (int, float)) for value in payload):
        return None
    return [rad_to_raw(float(value)) for value in payload]
