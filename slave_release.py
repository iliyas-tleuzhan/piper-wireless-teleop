#!/usr/bin/env python3
"""Release/disable the configured slave arm without commanding motion."""

import sys

from piper_wireless_teleop.config import load_config
from piper_wireless_teleop.slave_can_writer import PiperSlaveWriter


def main() -> int:
    """Connect to the configured CAN interface and send a release command."""

    config = load_config("configs/default.yaml")
    can_name = config.can.interface

    print(f"[RELEASE] Connecting to {config.arm_profile.name} on {can_name}")
    try:
        writer = PiperSlaveWriter(
            can_name,
            config.piper,
            config.arm_profile,
            bitrate=config.can.bitrate,
            sdk_interface=config.can.sdk_interface,
        )
        writer.connect()
        writer.disable()
        writer.close()
    except Exception as exc:
        print(f"[RELEASE] failed: {exc}")
        return 1

    print("[RELEASE] disable command sent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
