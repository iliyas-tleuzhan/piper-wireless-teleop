"""Minimal UDP sender and receiver wrappers for low-latency teleoperation."""

from __future__ import annotations

import socket
from dataclasses import dataclass


@dataclass
class UdpSender:
    """Small UDP sender for fixed-rate packet transmission."""

    target_ip: str
    target_port: int

    def __post_init__(self) -> None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._target = (self.target_ip, int(self.target_port))

    def send(self, data: bytes) -> None:
        """Send raw packet bytes to the configured target."""

        self._socket.sendto(data, self._target)

    def close(self) -> None:
        """Close the UDP socket."""

        self._socket.close()


class UdpReceiver:
    """UDP receiver with a short timeout so control loops can remain responsive."""

    def __init__(self, bind_ip: str, udp_port: int, timeout_s: float) -> None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.bind((bind_ip, int(udp_port)))
        self._socket.settimeout(float(timeout_s))

    def recv(self, max_bytes: int = 65535) -> tuple[bytes, tuple[str, int]] | None:
        """Receive one packet, returning ``None`` on timeout."""

        try:
            return self._socket.recvfrom(max_bytes)
        except socket.timeout:
            return None

    def close(self) -> None:
        """Close the UDP socket."""

        self._socket.close()
