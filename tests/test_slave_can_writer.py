"""Tests for the Piper slave writer wrapper."""

from math import radians

from piper_wireless_teleop.config import PiperConfig
from piper_wireless_teleop.slave_can_writer import PiperSlaveWriter


class FakePiper:
    """Small piper_sdk stand-in for writer tests."""

    def __init__(self) -> None:
        self.joint_limits: list[tuple[str, float, float]] = []
        self.gripper_limits: tuple[float, float] | None = None
        self.gripper_command: tuple[int, int, int, int] | None = None

    def SetSDKJointLimitParam(self, name: str, low: float, high: float) -> None:
        self.joint_limits.append((name, low, high))

    def SetSDKGripperRangeParam(self, low: float, high: float) -> None:
        self.gripper_limits = (low, high)

    def GripperCtrl(self, angle: int, effort: int, code: int, set_zero: int) -> None:
        self.gripper_command = (angle, effort, code, set_zero)


def piper_config() -> PiperConfig:
    """Build a config matching the checked-in defaults."""

    return PiperConfig(
        control_mode=0x01,
        move_mode=0x01,
        speed_percent=100,
        follow_mode=0xAD,
        gripper_default_effort=1000,
        joint_limits_deg=(
            (-154.0, 154.0),
            (0.0, 195.0),
            (-175.0, 0.0),
            (-106.0, 106.0),
            (-75.0, 75.0),
            (-120.0, 120.0),
        ),
        gripper_limits_mm=(0.0, 100.0),
    )


def test_configure_sdk_limits_when_supported() -> None:
    """Configured movement ranges are passed to SDK limit hooks when available."""

    writer = PiperSlaveWriter("can0", piper_config())
    fake = FakePiper()
    writer._piper = fake

    writer.configure_sdk_limits()

    assert fake.joint_limits == [
        ("j1", radians(-154.0), radians(154.0)),
        ("j2", radians(0.0), radians(195.0)),
        ("j3", radians(-175.0), radians(0.0)),
        ("j4", radians(-106.0), radians(106.0)),
        ("j5", radians(-75.0), radians(75.0)),
        ("j6", radians(-120.0), radians(120.0)),
    ]
    assert fake.gripper_limits == (0.0, 0.1)


def test_send_gripper_clamps_to_full_safe_range() -> None:
    """Gripper pass-through keeps full 0-100 mm travel but clamps unsafe values."""

    writer = PiperSlaveWriter("can0", piper_config())
    fake = FakePiper()
    writer._piper = fake

    writer.send_gripper({"angle": 120000, "effort": 7000, "code": 9})

    assert fake.gripper_command == (100000, 5000, 1, 0)
