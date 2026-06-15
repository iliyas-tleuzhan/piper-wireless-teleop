#!/usr/bin/env python3
"""Send decoded master Piper command targets over UDP.

Run this on Computer 1, connected only to the master Piper CAN bus. The script
listens for Piper command frames, stores the latest complete joint target, and
sends that latest target at a fixed configured rate even when the master arm is
not moving.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import can

from piper_wireless_teleop.config import load_config
from piper_wireless_teleop.logging_utils import RateLimitedPrinter
from piper_wireless_teleop.master_can_reader import (
    MASTER_CAN_IDS,
    MasterCommandState,
    decode_master_frame,
)
from piper_wireless_teleop.packet import encode_packet, make_packet
from piper_wireless_teleop.udp_transport import UdpSender


def parse_args() -> argparse.Namespace:
    """Parse Computer 1 command-line options."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-ip", required=True, help="Computer 2 IP address")
    parser.add_argument("--can", default=None, help="SocketCAN interface, for example can0")
    parser.add_argument("--config", default="configs/default.yaml", help="YAML config path")
    parser.add_argument("--target-port", type=int, default=None, help="UDP target port")
    parser.add_argument("--deadman", action="store_true", help="Set packet deadman=true")
    return parser.parse_args()


def main() -> None:
    """Run the master CAN-to-UDP bridge."""

    args = parse_args()
    config = load_config(Path(args.config))
    can_interface = args.can or config.can.interface
    target_port = args.target_port or config.network.udp_port
    send_interval_s = 1.0 / config.network.send_rate_hz

    bus = can.interface.Bus(channel=can_interface, interface="socketcan")
    sender = UdpSender(args.target_ip, target_port)
    status = RateLimitedPrinter(config.network.status_rate_hz)
    state = MasterCommandState()

    sequence = 0
    next_send = time.monotonic()

    print(f"[MASTER] Reading master Piper CAN frames from {can_interface}", flush=True)
    print(f"[MASTER] Sending UDP to {args.target_ip}:{target_port}", flush=True)
    print("[MASTER] Waiting for complete 0x155/0x156/0x157 joint target set", flush=True)

    try:
        while True:
            # Keep the receive timeout short so fixed-rate UDP sending is not
            # blocked waiting for new CAN traffic.
            message = bus.recv(timeout=config.network.socket_timeout_s)
            if message is not None and message.arbitration_id in MASTER_CAN_IDS:
                decode_master_frame(message, state)

            now = time.monotonic()
            if now < next_send:
                continue

            if not state.has_full_joint_target():
                status.print("[MASTER] Waiting for complete joint target frames")
                next_send = now + send_interval_s
                continue

            # Sender wall-clock timestamp is kept only for log correlation. The
            # slave uses receiver-side monotonic time for safety timeouts.
            timestamp = time.time()
            packet = make_packet(
                sequence=sequence,
                timestamp=timestamp,
                deadman=args.deadman,
                joints_raw=state.joints_raw(),
                gripper=state.gripper,
                mode_frame=state.mode_frame,
            )
            sender.send(encode_packet(packet))

            if config.logging.verbose_packets:
                print(f"[MASTER] packet={packet}", flush=True)
            else:
                status.print(
                    f"[MASTER] seq={sequence} deadman={args.deadman} "
                    f"deg={[round(value, 3) for value in packet['joints_deg']]} "
                    f"gripper={state.gripper}"
                )

            sequence += 1
            next_send = now + send_interval_s
    except KeyboardInterrupt:
        print("\n[MASTER] stopped", flush=True)
    finally:
        sender.close()
        shutdown = getattr(bus, "shutdown", None)
        if callable(shutdown):
            shutdown()


if __name__ == "__main__":
    main()
