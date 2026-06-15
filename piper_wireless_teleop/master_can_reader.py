"""Decode master Piper CAN command frames into joint and gripper targets."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

MASTER_CAN_IDS = {0x151, 0x155, 0x156, 0x157, 0x159}


class CanMessage(Protocol):
    """Subset of ``python-can`` message fields used by the decoder."""

    arbitration_id: int
    data: bytes


def decode_i32_be(data: bytes | bytearray | memoryview) -> int:
    """Decode a signed 32-bit big-endian integer from four CAN payload bytes."""

    if len(data) != 4:
        raise ValueError("expected exactly 4 bytes for int32")
    return int.from_bytes(bytes(data), byteorder="big", signed=True)


@dataclass
class MasterCommandState:
    """Latest decoded Piper command state from the master CAN bus."""

    joints: list[int | None] = field(default_factory=lambda: [None] * 6)
    gripper: dict[str, int] | None = None
    mode_frame: list[int] | None = None

    def has_full_joint_target(self) -> bool:
        """Return true after all three joint target frames have been observed."""

        return all(value is not None for value in self.joints)

    def joints_raw(self) -> list[int]:
        """Return the latest complete raw joint target list."""

        if not self.has_full_joint_target():
            raise ValueError("full joint target is not available yet")
        return [int(value) for value in self.joints]


def decode_master_frame(message: CanMessage, state: MasterCommandState) -> bool:
    """Decode one master command CAN frame into ``state``.

    Piper joint command frames use an 8-byte payload containing two signed
    big-endian int32 values:

    * ``0x155`` bytes 0..3 = J1, bytes 4..7 = J2
    * ``0x156`` bytes 0..3 = J3, bytes 4..7 = J4
    * ``0x157`` bytes 0..3 = J5, bytes 4..7 = J6

    The gripper frame ``0x159`` uses bytes 0..3 for angle, bytes 4..5 for
    unsigned effort, and byte 6 for the gripper command code. Byte 7 is not used
    by this bridge but is kept on the bus by the original command stream.
    """

    arbitration_id = int(message.arbitration_id)
    data = bytes(message.data)
    if arbitration_id not in MASTER_CAN_IDS:
        return False

    if arbitration_id == 0x151 and len(data) == 8:
        state.mode_frame = list(data)
        return True

    if arbitration_id == 0x155 and len(data) == 8:
        state.joints[0] = decode_i32_be(data[0:4])
        state.joints[1] = decode_i32_be(data[4:8])
        return True

    if arbitration_id == 0x156 and len(data) == 8:
        state.joints[2] = decode_i32_be(data[0:4])
        state.joints[3] = decode_i32_be(data[4:8])
        return True

    if arbitration_id == 0x157 and len(data) == 8:
        state.joints[4] = decode_i32_be(data[0:4])
        state.joints[5] = decode_i32_be(data[4:8])
        return True

    if arbitration_id == 0x159 and len(data) == 8:
        state.gripper = {
            "angle": decode_i32_be(data[0:4]),
            "effort": int.from_bytes(data[4:6], byteorder="big", signed=False),
            "code": data[6],
        }
        return True

    return False
