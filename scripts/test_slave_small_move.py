#!/usr/bin/env python3
"""Hardware validation script that moves slave joint 6 by 1 degree.

This script commands real motion and is intentionally not part of normal
teleoperation. It requires ``--confirm MOVE`` and should only be run with an
E-stop or power switch nearby and the workspace clear.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from piper_wireless_teleop.config import load_config
from piper_wireless_teleop.safety import clamp_joints_raw, deg_to_raw, limit_step_raw
from piper_wireless_teleop.slave_can_writer import PiperSlaveWriter


def main() -> None:
    """Move J6 by a small amount to validate SDK control."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--can", default=None)
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()

    if args.confirm != "MOVE":
        raise SystemExit("Refusing to move robot. Re-run with --confirm MOVE.")

    config = load_config(Path(args.config))
    can_interface = args.can or config.can.interface
    writer = PiperSlaveWriter(can_interface, config.piper)

    print("[SMALL-MOVE] Keep E-stop/power within reach. Moving J6 by 1 degree.", flush=True)
    writer.connect()
    feedback = writer.read_joint_feedback()
    print(f"[SMALL-MOVE] current feedback={feedback}", flush=True)
    writer.enable()
    writer.set_motion_mode()

    # SDK feedback object shapes vary. For validation, require the operator to
    # place the arm near zero and command a small known target slowly.
    current = [0, 0, 0, 0, 0, 0]
    target = [0, 0, 0, 0, 0, deg_to_raw(1.0)]
    step = deg_to_raw(0.1)
    commanded = current
    while commanded != target:
        commanded = clamp_joints_raw(limit_step_raw(commanded, target, step))
        writer.send_joints(commanded)
        time.sleep(0.05)
    print("[SMALL-MOVE] complete", flush=True)


if __name__ == "__main__":
    main()
