"""Receiver-side packet ordering and timeout state.

The slave must not reject packets by comparing Computer 1 wall-clock timestamps
with Computer 2 wall-clock time. This module tracks valid packet arrival using
``time.monotonic()`` values supplied by the receiver loop and uses sequence
numbers only for ordering and dropped-packet accounting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .safety import clamp_joints_raw, validate_joint_packet


@dataclass(frozen=True)
class PacketDecision:
    """Result of validating one decoded UDP packet."""

    accepted: bool
    reason: str | None = None
    warning: str | None = None
    target_joints: list[int] | None = None
    sequence: int | None = None
    dropped: int = 0
    total_dropped: int = 0
    receiver_time_s: float | None = None
    sender_timestamp: float | None = None


class SlavePacketTracker:
    """Track valid slave packets using receiver monotonic time."""

    def __init__(self) -> None:
        self.last_seq: int | None = None
        self.total_dropped = 0
        self.last_valid_rx_time_s: float | None = None
        self.first_valid_rx_time_s: float | None = None
        self.valid_packet_count = 0
        self._warned_missing_seq = False

    def process_packet(self, packet: dict[str, Any], receiver_time_s: float) -> PacketDecision:
        """Validate one packet and update ordering state if it is usable."""

        try:
            target_joints = clamp_joints_raw(validate_joint_packet(packet))
        except (TypeError, ValueError) as exc:
            return PacketDecision(accepted=False, reason=f"malformed packet: {exc}")

        if not packet["deadman"]:
            return PacketDecision(accepted=False, reason="deadman=false")

        sequence, warning = self._read_sequence(packet.get("seq"))
        if sequence is not None:
            if self.last_seq is not None and sequence <= self.last_seq:
                return PacketDecision(
                    accepted=False,
                    reason=f"duplicate/out-of-order seq={sequence} last_seq={self.last_seq}",
                    sequence=sequence,
                    total_dropped=self.total_dropped,
                )

            dropped = 0
            if self.last_seq is not None and sequence > self.last_seq + 1:
                dropped = sequence - self.last_seq - 1
                self.total_dropped += dropped
            self.last_seq = sequence
        else:
            dropped = 0

        self.last_valid_rx_time_s = receiver_time_s
        if self.first_valid_rx_time_s is None:
            self.first_valid_rx_time_s = receiver_time_s
        self.valid_packet_count += 1

        sender_timestamp = packet.get("timestamp")
        return PacketDecision(
            accepted=True,
            warning=warning,
            target_joints=target_joints,
            sequence=sequence,
            dropped=dropped,
            total_dropped=self.total_dropped,
            receiver_time_s=receiver_time_s,
            sender_timestamp=float(sender_timestamp) if isinstance(sender_timestamp, (int, float)) else None,
        )

    def timeout_expired(self, now_s: float, receiver_timeout_s: float) -> bool:
        """Return true when no valid packet has arrived within the timeout."""

        if self.last_valid_rx_time_s is None:
            return False
        return now_s - self.last_valid_rx_time_s > receiver_timeout_s

    def seconds_since_valid_packet(self, now_s: float) -> float | None:
        """Return seconds since the last valid packet, or ``None`` before any valid packet."""

        if self.last_valid_rx_time_s is None:
            return None
        return max(0.0, now_s - self.last_valid_rx_time_s)

    def command_rate_hz(self, now_s: float) -> float | None:
        """Estimate accepted packet rate from receiver-side monotonic time."""

        if self.first_valid_rx_time_s is None or self.valid_packet_count < 2:
            return None
        elapsed_s = now_s - self.first_valid_rx_time_s
        if elapsed_s <= 0:
            return None
        return (self.valid_packet_count - 1) / elapsed_s

    def _read_sequence(self, value: Any) -> tuple[int | None, str | None]:
        """Parse packet sequence number without crashing on malformed input."""

        if isinstance(value, bool) or not isinstance(value, int):
            if self._warned_missing_seq:
                return None, None
            self._warned_missing_seq = True
            return None, "packet seq missing or invalid; ordering unknown"
        return value, None
