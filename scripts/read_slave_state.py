#!/usr/bin/env python3
"""Print slave Piper SDK feedback without commanding motion."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from piper_wireless_teleop.config import load_config
from piper_wireless_teleop.logging_utils import RateLimitedPrinter
from piper_wireless_teleop.slave_can_writer import PiperSlaveWriter


def main() -> None:
    """Run a Computer 2 feedback debug loop."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--can", default=None)
    parser.add_argument("--config", default="configs/default.yaml")
    args = parser.parse_args()

    config = load_config(Path(args.config))
    can_interface = args.can or config.can.interface
    writer = PiperSlaveWriter(can_interface, config.piper)
    status = RateLimitedPrinter(config.logging.status_hz)

    print(f"[STATE] Connecting to slave Piper on {can_interface}; no motion is commanded", flush=True)
    writer.connect()

    try:
        while True:
            feedback = writer.read_joint_feedback()
            status.print(f"[STATE] feedback={feedback}")
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\n[STATE] stopped", flush=True)


if __name__ == "__main__":
    main()
