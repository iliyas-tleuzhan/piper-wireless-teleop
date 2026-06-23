#!/usr/bin/env python3
"""Receive master UDP targets and command the slave Piper arm without gripper motion.

Run this on Computer 2, connected only to the slave Piper CAN bus. Movement is
refused unless ``--confirm MOVE`` is passed. Incoming targets are checked for
deadman, sequence ordering, and shape, then commanded immediately through
``piper_sdk``. Optional slew limiting is disabled by default because the normal
wireless bridge should follow the latest master target like wired teleoperation.

This variant intentionally ignores any gripper targets, for setups where the
slave gripper is not connected.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from piper_wireless_teleop.config import SafetyConfig, load_config
from piper_wireless_teleop.logging_utils import RateLimitedPrinter
from piper_wireless_teleop.packet import decode_packet
from piper_wireless_teleop.receiver_state import SlavePacketTracker
from piper_wireless_teleop.safety import (
    clamp_joints_raw,
    deg_to_raw,
    limit_step_raw,
    raw_to_deg,
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


def warn_if_receiver_timeout(
    tracker: SlavePacketTracker,
    status: RateLimitedPrinter,
    receiver_timeout_s: float,
) -> None:
    """Print a rate-limited hold warning when valid packets stop arriving."""

    now = time.monotonic()
    if not tracker.timeout_expired(now, receiver_timeout_s):
        return
    idle_s = tracker.seconds_since_valid_packet(now)
    idle_text = receiver_timeout_s if idle_s is None else idle_s
    status.print(f"[SLAVE] No valid packets for {idle_text:.2f}s; holding last command")


def choose_command_joints(
    *,
    last_commanded_joints: list[int] | None,
    target_joints: list[int],
    safety_config: SafetyConfig,
) -> list[int]:
    """Choose the slave command for a target packet.

    Default behavior is direct passthrough of the latest valid target. Slew
    limiting is retained only as an explicit hidden safety fallback because
    limiting every packet makes wireless teleop feel much slower than wired
    Piper master-slave operation.
    """

    if not safety_config.enable_slew_limit or last_commanded_joints is None:
        return clamp_joints_raw(target_joints)

    max_step_raw = deg_to_raw(safety_config.max_step_deg)
    return clamp_joints_raw(limit_step_raw(last_commanded_joints, target_joints, max_step_raw))


def main() -> None:
    """Run the UDP-to-Piper slave bridge without gripper commands."""

    args = parse_args()
    if args.confirm != "MOVE":
        raise SystemExit("Refusing to move robot. Re-run with --confirm MOVE.")

    config = load_config(Path(args.config))
    can_interface = args.can or config.can.interface
    udp_port = args.udp_port or config.network.udp_port

    receiver = UdpReceiver(args.bind_ip, udp_port, config.network.socket_timeout_s)
    writer = PiperSlaveWriter(can_interface, config.piper)
    status = RateLimitedPrinter(config.network.status_rate_hz)
    tracker = SlavePacketTracker()

    print(f"[SLAVE] Listening on {args.bind_ip}:{udp_port}", flush=True)
    print(f"[SLAVE] Connecting to slave Piper on {can_interface}", flush=True)
    writer.connect()
    writer.enable()
    writer.set_motion_mode()
    print("[SLAVE] Arm enabled and motion mode configured", flush=True)

    last_commanded_joints: list[int] | None = None

    try:
        while True:
            received = receiver.recv()
            if received is None:
                warn_if_receiver_timeout(tracker, status, config.network.receiver_timeout_s)
                continue

            data, address = received
            # Receive time is measured on Computer 2 with a monotonic clock.
            # Sender timestamps are not trusted for safety because the two
            # computers may not have synchronized wall clocks.
            receiver_time_s = time.monotonic()
            try:
                packet = decode_packet(data)
            except (ValueError, TypeError) as exc:
                status.print(f"[SLAVE] Ignoring malformed packet from {address[0]}: {exc}")
                warn_if_receiver_timeout(tracker, status, config.network.receiver_timeout_s)
                continue

            decision = tracker.process_packet(packet, receiver_time_s)
            if decision.warning:
                status.print(f"[SLAVE] {decision.warning}")
            if not decision.accepted:
                if decision.reason and decision.reason.startswith("duplicate/out-of-order"):
                    status.print(f"[SLAVE] {decision.reason}")
                else:
                    status.print(f"[SLAVE] Ignoring packet from {address[0]}: {decision.reason}")
                warn_if_receiver_timeout(tracker, status, config.network.receiver_timeout_s)
                continue

            target_joints = decision.target_joints
            if target_joints is None:
                status.print(f"[SLAVE] Ignoring packet from {address[0]}: missing joints")
                continue

            next_joints = choose_command_joints(
                last_commanded_joints=last_commanded_joints,
                target_joints=target_joints,
                safety_config=config.safety,
            )
            writer.send_joints(next_joints)

            last_commanded_joints = next_joints
            command_rate_hz = tracker.command_rate_hz(time.monotonic())
            command_rate_text = "unknown" if command_rate_hz is None else f"{command_rate_hz:.1f}Hz"

            sender_offset_s = None
            if config.logging.verbose_packets and decision.sender_timestamp is not None:
                # Debug hint only. It is never used to accept or reject packets
                # because Computer 1 and Computer 2 clocks may differ.
                sender_offset_s = time.time() - decision.sender_timestamp
            sender_debug_text = (
                "" if sender_offset_s is None else f" sender_offset_debug={sender_offset_s:+.3f}s"
            )

            status.print(
                f"[SLAVE] accepted packet from={address[0]} seq={decision.sequence} "
                f"dropped={decision.dropped} total_dropped={decision.total_dropped} "
                f"cmd_rate={command_rate_text}{sender_debug_text} "
                f"target_deg={[round(raw_to_deg(value), 3) for value in target_joints]} "
                f"cmd_deg={[round(raw_to_deg(value), 3) for value in next_joints]}"
            )
    except KeyboardInterrupt:
        print("\n[SLAVE] stopped", flush=True)
    finally:
        receiver.close()


if __name__ == "__main__":
    main()
