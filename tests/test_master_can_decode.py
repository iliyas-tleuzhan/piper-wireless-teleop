"""Tests for master Piper CAN command decoding."""

from dataclasses import dataclass

from piper_wireless_teleop.master_can_reader import MasterCommandState, decode_master_frame


@dataclass
class FakeCanMessage:
    """Small python-can stand-in for decoder tests."""

    arbitration_id: int
    data: bytes


def frame(*values: int) -> bytes:
    """Pack signed int32 values into a CAN payload."""

    return b"".join(value.to_bytes(4, "big", signed=True) for value in values)


def test_decode_joint_frames() -> None:
    """0x155, 0x156, and 0x157 fill all six joint targets."""

    state = MasterCommandState()
    decode_master_frame(FakeCanMessage(0x155, frame(1000, -2000)), state)
    decode_master_frame(FakeCanMessage(0x156, frame(3000, -4000)), state)
    decode_master_frame(FakeCanMessage(0x157, frame(5000, -6000)), state)

    assert state.has_full_joint_target()
    assert state.joints_raw() == [1000, -2000, 3000, -4000, 5000, -6000]


def test_decode_gripper_frame() -> None:
    """0x159 decodes angle, unsigned effort, and command code."""

    state = MasterCommandState()
    data = (1234).to_bytes(4, "big", signed=True) + (1000).to_bytes(2, "big") + bytes([1, 0])

    assert decode_master_frame(FakeCanMessage(0x159, data), state)
    assert state.gripper == {"angle": 1234, "effort": 1000, "code": 1}
