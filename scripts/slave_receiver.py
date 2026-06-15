#!/usr/bin/env python3
"""Receive master UDP targets and command the slave Piper arm.

Run this on Computer 2, connected only to the slave Piper CAN bus. Movement is
refused unless ``--confirm MOVE`` is passed. Incoming targets are checked for
deadman, freshness, and shape, then commanded through ``piper_sdk`` with
per-cycle slew limiting instead of freezing on large jumps.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from piper_wireless_teleop.config import load_config
from piper_wireless_teleop.logging_utils import RateLimitedPrinter
from piper_wireless_teleop.packet import decode_packet
from piper_wireless_teleop.safety import (
    clamp_joints_raw,
    deg_to_raw,
    limit_step_raw,
    packet_is_fresh,
    raw_to_deg,
    validate_joint_packet,
)
from piper_wireless_teleop.slave_can_writer import PiperSlaveWriter
from piper_wireless_teleop.udp_transport import UdpReceiver


def parse_args() -> argparse.Namespace:
    """Parse Computer 2 command-line options."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--can", default=None, help="SocketCAN interface, for example can0")
    parser.add_argument("--config", default="configs/default.yaml", help="YAML config path")
    parser.add_argument("--bind-ip", default="0.0.0.0", help="UDP bind address")
    parser.add_argument("--udp-port", type=int, default=None, help="UDP listen port")
    parser.add_argument("--confirm", default="", help="Must be MOVE to allow robot motion")
    return parser.parse_args()


def main() -> None:
    """Run the UDP-to-Piper slave bridge."""

    args = parse_args()
    if args.confirm != "MOVE":
        raise SystemExit("Refusing to move robot. Re-run with --confirm MOVE.")

    config = load_config(Path(args.config))
    can_interface = args.can or config.can.interface
    udp_port = args.udp_port or config.network.udp_port
    max_step_raw = deg_to_raw(config.safety.max_step_deg)

    receiver = UdpReceiver(args.bind_ip, udp_port, config.network.socket_timeout_s)
    writer = PiperSlaveWriter(can_interface, config.piper)
    status = RateLimitedPrinter(config.logging.status_hz)

    print(f"[SLAVE] Listening on {args.bind_ip}:{udp_port}", flush=True)
    print(f"[SLAVE] Connecting to slave Piper on {can_interface}", flush=True)
    writer.connect()
    writer.enable()
    writer.set_motion_mode()
    print("[SLAVE] Arm enabled and motion mode configured", flush=True)

    last_commanded_joints: list[int] | None = None
    last_sequence: int | None = None

    try:
        while True:
            received = receiver.recv()
            if received is None:
                continue

            data, address = received
            try:
                packet = decode_packet(data)
                target_joints = clamp_joints_raw(validate_joint_packet(packet))
            except (ValueError, TypeError) as exc:
                status.print(f"[SLAVE] Ignoring malformed packet from {address[0]}: {exc}")
                continue

            if not packet["deadman"]:
                status.print("[SLAVE] Ignoring packet because deadman=false")
                continue

            timestamp = float(packet["timestamp"])
            if not packet_is_fresh(timestamp, config.network.max_packet_age_s):
                age_ms = (time.time() - timestamp) * 1000.0
                status.print(f"[SLAVE] Ignoring stale packet age={age_ms:.1f}ms")
                continue

            if last_commanded_joints is None:
                # Initialize the slew limiter at the first safe target. Operators
                # should still start with both arms in similar poses; this avoids
                # an artificial jump from zeros on the first packet.
                last_commanded_joints = target_joints

            next_joints = clamp_joints_raw(
                limit_step_raw(last_commanded_joints, target_joints, max_step_raw)
            )
            writer.send_joints(next_joints)

            gripper = packet.get("gripper")
            if isinstance(gripper, dict):
                writer.send_gripper(
                    {
                        "angle": int(gripper.get("angle", 0)),
                        "effort": int(gripper.get("effort", config.piper.gripper_default_effort)),
                        "code": int(gripper.get("code", 1)),
                    }
                )

            sequence = packet.get("seq")
            dropped = 0
            if last_sequence is not None and isinstance(sequence, int):
                dropped = max(0, sequence - last_sequence - 1)
            if isinstance(sequence, int):
                last_sequence = sequence
            last_commanded_joints = next_joints

            status.print(
                f"[SLAVE] from={address[0]} seq={sequence} dropped={dropped} "
                f"target_deg={[round(raw_to_deg(value), 3) for value in target_joints]} "
                f"cmd_deg={[round(raw_to_deg(value), 3) for value in next_joints]}"
            )
    except KeyboardInterrupt:
        print("\n[SLAVE] stopped", flush=True)
    finally:
        receiver.close()


if __name__ == "__main__":
    main()
