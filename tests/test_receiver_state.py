"""Tests for receiver-side packet freshness and sequence handling."""

from piper_wireless_teleop.packet import make_packet
from piper_wireless_teleop.receiver_state import SlavePacketTracker


def packet(seq: object, timestamp: float = 0.0) -> dict[str, object]:
    """Build a valid packet with configurable ordering fields."""

    data = make_packet(
        sequence=0,
        timestamp=timestamp,
        deadman=True,
        joints_raw=[0, 1000, -1000, 0, 0, 0],
        gripper=None,
    )
    data["seq"] = seq
    return data


def test_old_sender_timestamp_is_not_rejected() -> None:
    """A fresh arrival is accepted even when the sender clock looks old."""

    tracker = SlavePacketTracker()

    decision = tracker.process_packet(packet(seq=1, timestamp=1.0), receiver_time_s=5000.0)

    assert decision.accepted
    assert decision.target_joints == [0, 1000, -1000, 0, 0, 0]


def test_duplicate_and_out_of_order_sequences_are_ignored() -> None:
    """Sequence numbers protect against replayed or reordered UDP packets."""

    tracker = SlavePacketTracker()

    assert tracker.process_packet(packet(seq=10), receiver_time_s=1.0).accepted
    duplicate = tracker.process_packet(packet(seq=10), receiver_time_s=1.1)
    out_of_order = tracker.process_packet(packet(seq=9), receiver_time_s=1.2)

    assert not duplicate.accepted
    assert "duplicate/out-of-order" in str(duplicate.reason)
    assert not out_of_order.accepted
    assert tracker.last_seq == 10


def test_dropped_packets_are_counted() -> None:
    """Gaps in sequence numbers are counted without estimating elapsed time."""

    tracker = SlavePacketTracker()

    assert tracker.process_packet(packet(seq=4), receiver_time_s=1.0).accepted
    decision = tracker.process_packet(packet(seq=7), receiver_time_s=1.1)

    assert decision.accepted
    assert decision.dropped == 2
    assert decision.total_dropped == 2


def test_timeout_uses_receiver_monotonic_time() -> None:
    """Timeout decisions depend on arrival time, not sender wall-clock timestamp."""

    tracker = SlavePacketTracker()

    assert tracker.process_packet(packet(seq=1, timestamp=-999999.0), receiver_time_s=100.0).accepted
    assert not tracker.timeout_expired(now_s=100.4, receiver_timeout_s=0.5)
    assert tracker.timeout_expired(now_s=100.6, receiver_timeout_s=0.5)


def test_missing_sequence_is_allowed_with_one_warning() -> None:
    """Old or malformed senders can still command motion with unknown ordering."""

    tracker = SlavePacketTracker()

    first = tracker.process_packet(packet(seq="bad"), receiver_time_s=1.0)
    second = tracker.process_packet(packet(seq=None), receiver_time_s=1.1)

    assert first.accepted
    assert first.warning == "packet seq missing or invalid; ordering unknown"
    assert second.accepted
    assert second.warning is None
