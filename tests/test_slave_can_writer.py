"""Tests for slave SDK adapter command generation."""

import sys
import types

from piper_wireless_teleop.arm_profile import PIPER_X_PROFILE
from piper_wireless_teleop.config import PiperConfig
from piper_wireless_teleop.slave_can_writer import PiperSlaveWriter


class FakeRobot:
    OPTIONS = types.SimpleNamespace(
        EFFECTOR=types.SimpleNamespace(AGX_GRIPPER="gripper"),
        MOTION_MODE=types.SimpleNamespace(JS="js"),
    )

    def __init__(self) -> None:
        self.connected = False
        self.enabled = False
        self.disabled = False
        self.joints = None
        self.speed = None
        self.motion_mode = None
        self.auto_mode = True
        self.effector = FakeEffector()

    def connect(self) -> None:
        self.connected = True

    def init_effector(self, _option: object) -> object:
        return self.effector

    def enable(self) -> None:
        self.enabled = True

    def disable(self) -> None:
        self.disabled = True

    def set_joint_limits_enabled(self, _enabled: bool) -> None:
        pass

    def set_speed_percent(self, speed: int) -> None:
        self.speed = speed

    def set_motion_mode(self, mode: object) -> None:
        self.motion_mode = mode

    def set_auto_set_motion_mode_enabled(self, enabled: bool) -> None:
        self.auto_mode = enabled

    def move_js(self, joints: list[float]) -> None:
        self.joints = joints


class FakeEffector:
    def __init__(self) -> None:
        self.gripper = None

    def move_gripper_m(self, width: float, force: float) -> None:
        self.gripper = (width, force)


def install_fake_pyagxarm(monkeypatch):
    robot = FakeRobot()

    class FakeFactory:
        @staticmethod
        def create_arm(_config):
            return robot

    module = types.SimpleNamespace(
        AgxArmFactory=FakeFactory,
        ArmModel=types.SimpleNamespace(PIPER_X="piper_x"),
        PiperFW=types.SimpleNamespace(DEFAULT="default", V189="v189"),
        create_agx_arm_config=lambda **kwargs: kwargs,
    )
    monkeypatch.setitem(sys.modules, "pyAgxArm", module)
    return robot


def test_piper_x_slave_writer_generates_pyagxarm_commands(monkeypatch) -> None:
    """PiPER-X writer converts raw 0.001-degree commands to radians."""

    robot = install_fake_pyagxarm(monkeypatch)
    writer = PiperSlaveWriter(
        "can0",
        PiperConfig(1, 1, 100, 0xAD, 1000),
        PIPER_X_PROFILE,
    )

    writer.connect()
    writer.enable()
    writer.set_motion_mode()
    writer.send_joints([0, 90000, -90000, 0, 0, 0])
    writer.send_gripper({"angle": 50000, "effort": 1200, "code": 1})
    writer.disable()

    assert robot.connected
    assert robot.enabled
    assert robot.disabled
    assert robot.speed == 100
    assert robot.motion_mode == "js"
    assert not robot.auto_mode
    assert robot.joints == [0.0, 1.5707963267948966, -1.5707963267948966, 0.0, 0.0, 0.0]
    assert robot.effector.gripper == (0.05, 1.2)
