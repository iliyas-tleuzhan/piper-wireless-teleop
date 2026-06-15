"""UDP packet encoding for Piper wireless teleoperation.

JSON is used intentionally for readability while bringing up the system and
debugging packets with common tools. The module boundary keeps serialization in
one place so the wire format can later be replaced with msgpack without changing
the CAN reader, UDP transport, or Piper writer logic.

Packets include a sender ``timestamp`` for log correlation only. The receiver
must not use that wall-clock value for safety decisions because the two
computers may not have synchronized clocks.
"""

from __future__ import annotations

import json
from typing import Any

from .safety import raw_to_deg


PACKET_TYPE = "piper_joint_targets"


def make_packet(
    *,
    sequence: int,
    timestamp: float,
    deadman: bool,
    joints_raw: list[int],
    gripper: dict[str, int] | None = None,
    mode_frame: list[int] | None = None,
) -> dict[str, Any]:
    """Build a teleoperation packet from decoded Piper command targets.

    ``timestamp`` is the sender wall-clock time and is useful for optional
    debugging. Freshness and timeout checks belong on receiver-side monotonic
    time, not this field.
    """

    return {
        "type": PACKET_TYPE,
        "seq": int(sequence),
        "timestamp": float(timestamp),
        "deadman": bool(deadman),
        "joints": [int(value) for value in joints_raw],
        "joints_deg": [raw_to_deg(value) for value in joints_raw],
        "gripper": gripper,
        "mode_frame": None if mode_frame is None else [int(value) for value in mode_frame],
    }


def encode_packet(packet: dict[str, Any]) -> bytes:
    """Encode a packet as compact UTF-8 JSON bytes."""

    return json.dumps(packet, separators=(",", ":"), sort_keys=True).encode("utf-8")


def decode_packet(data: bytes) -> dict[str, Any]:
    """Decode UTF-8 JSON packet bytes into a dictionary."""

    decoded = json.loads(data.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("packet must decode to a JSON object")
    return decoded
