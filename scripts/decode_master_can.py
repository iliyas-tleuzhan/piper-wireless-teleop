#!/usr/bin/env python3
"""Decode and print master Piper CAN command frames without moving anything."""

from __future__ import annotations

import argparse
from pathlib import Path

import can

from piper_wireless_teleop.config import load_config
from piper_wireless_teleop.master_can_reader import (
    MASTER_CAN_IDS,
    MasterCommandState,
    decode_master_frame,
)
from piper_wireless_teleop.safety import raw_to_deg


def main() -> None:
    """Run a Computer 1 CAN decode debug loop."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--can", default=None)
    parser.add_argument("--config", default="configs/default.yaml")
    args = parser.parse_args()

    config = load_config(Path(args.config))
    can_interface = args.can or config.can.interface
    bus = can.interface.Bus(channel=can_interface, interface="socketcan")
    state = MasterCommandState()

    print(f"[DECODE] Reading {can_interface}; no UDP is sent and no robot is moved", flush=True)
    try:
        while True:
            message = bus.recv(timeout=config.network.socket_timeout_s)
            if message is None or message.arbitration_id not in MASTER_CAN_IDS:
                continue
            if decode_master_frame(message, state):
                joints = state.joints_raw() if state.has_full_joint_target() else None
                print(
                    f"[DECODE] id=0x{message.arbitration_id:X} "
                    f"joints_deg={None if joints is None else [round(raw_to_deg(v), 3) for v in joints]} "
                    f"gripper={state.gripper}",
                    flush=True,
                )
    except KeyboardInterrupt:
        print("\n[DECODE] stopped", flush=True)
    finally:
        shutdown = getattr(bus, "shutdown", None)
        if callable(shutdown):
            shutdown()


if __name__ == "__main__":
    main()
