"""SocketCAN maintenance helpers."""

from __future__ import annotations

import subprocess


def reset_can_interface(interface: str, bitrate: int) -> bool:
    """Reset a SocketCAN interface using the repo's standard Piper settings."""

    print(f"[CAN] Resetting {interface}. sudo may ask for password.", flush=True)
    print(f"[CAN] Resetting {interface} at {bitrate} bitrate", flush=True)
    commands = (
        ["sudo", "ip", "link", "set", interface, "down"],
        [
            "sudo",
            "ip",
            "link",
            "set",
            interface,
            "type",
            "can",
            "bitrate",
            str(bitrate),
        ],
        ["sudo", "ip", "link", "set", interface, "up"],
        ["ip", "-details", "link", "show", interface],
    )
    try:
        for command in commands:
            subprocess.run(command, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"[CAN] WARNING: failed to reset {interface}: {exc}", flush=True)
        return False

    print(f"[CAN] {interface} reset complete", flush=True)
    return True
