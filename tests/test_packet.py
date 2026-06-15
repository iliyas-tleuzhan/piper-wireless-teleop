"""Tests for JSON teleoperation packet encoding."""

from piper_wireless_teleop.packet import decode_packet, encode_packet, make_packet


def test_packet_round_trip() -> None:
    """Packets preserve command fields through JSON encoding."""

    packet = make_packet(
        sequence=42,
        timestamp=123.5,
        deadman=True,
        joints_raw=[1000, 2000, -3000, 0, 500, -500],
        gripper={"angle": 1200, "effort": 1000, "code": 1},
        mode_frame=[1, 1, 100, 173, 0, 0, 0, 0],
    )

    decoded = decode_packet(encode_packet(packet))

    assert decoded["type"] == "piper_joint_targets"
    assert decoded["seq"] == 42
    assert decoded["joints"] == [1000, 2000, -3000, 0, 500, -500]
    assert decoded["joints_deg"] == [1.0, 2.0, -3.0, 0.0, 0.5, -0.5]
    assert decoded["gripper"] == {"angle": 1200, "effort": 1000, "code": 1}
    assert decoded["timestamp"] == 123.5
    assert decoded["mode_frame"] == [1, 1, 100, 173, 0, 0, 0, 0]
