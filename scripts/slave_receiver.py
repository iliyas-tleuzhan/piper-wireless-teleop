#!/usr/bin/env python3
"""Receive master UDP targets and command the slave Piper arm.

Run this on Computer 2, connected only to the slave Piper CAN bus. Movement is
refused unless ``--confirm MOVE`` is passed. Incoming targets are checked for
deadman, sequence ordering, and shape, then commanded immediately through
``piper_sdk``. Optional slew limiting is disabled by default because the normal
wireless bridge should follow the latest master target like wired teleoperation.
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
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

ALIGN_THRESHOLD_DEG = 15.0
ALIGN_STEP_DEG = 0.3
ALIGN_TICK_S = 0.02
ALIGN_TIMEOUT_S = 10.0
SLAVE_FEEDBACK_SAMPLE_S = 0.5


@dataclass(frozen=True)
class StartupInit:
    """Teleop initialization state selected before normal packet forwarding."""

    mode: str
    master_start: list[int] | None = None
    slave_start: list[int] | None = None


def parse_args() -> argparse.Namespace:
    """Parse Computer 2 command-line options."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--can", default=None, help="SocketCAN interface, for example can0")
    parser.add_argument("--config", default="configs/default.yaml", help="YAML config path")
    parser.add_argument("--bind-ip", default="0.0.0.0", help="UDP bind address")
    parser.add_argument("--udp-port", type=int, default=None, help="UDP listen port")
    parser.add_argument("--confirm", default="", help="Must be MOVE to allow robot motion")
    parser.add_argument(
        "--init-mode",
        choices=("align", "offset", "none"),
        default="align",
        help=(
            "Startup safety mode. align prompts and slowly corrects the slave before teleop; "
            "offset keeps slave_start + master_delta; none uses old direct behavior."
        ),
    )
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


def format_joint_degrees(joints_raw: Sequence[int]) -> list[float]:
    """Return rounded degree values for status output."""

    return [round(raw_to_deg(value), 3) for value in joints_raw]


def apply_offset_command(
    *,
    master_current: Sequence[int],
    master_start: Sequence[int],
    slave_start: Sequence[int],
) -> list[int]:
    """Map master motion deltas onto the slave's startup feedback pose."""

    return clamp_joints_raw(
        [
            int(slave_value) + int(current_value) - int(start_value)
            for current_value, start_value, slave_value in zip(
                master_current, master_start, slave_start, strict=True
            )
        ]
    )


def extract_feedback_joints_raw(feedback: Any) -> list[int] | None:
    """Extract six 0.001-degree joint values from common Piper feedback shapes."""

    visited: set[int] = set()
    return _extract_feedback_joints_raw(feedback, visited)


def _extract_feedback_joints_raw(feedback: Any, visited: set[int]) -> list[int] | None:
    if feedback is None:
        return None
    feedback_id = id(feedback)
    if feedback_id in visited:
        return None
    visited.add(feedback_id)

    if isinstance(feedback, dict):
        direct = _extract_named_joint_values(feedback.get)
        if direct is not None:
            return direct
        for value in feedback.values():
            nested = _extract_feedback_joints_raw(value, visited)
            if nested is not None:
                return nested
        return None

    if isinstance(feedback, Sequence) and not isinstance(feedback, (str, bytes, bytearray)):
        if len(feedback) == 6 and all(_is_int_like(value) for value in feedback):
            return [int(value) for value in feedback]
        for value in feedback:
            nested = _extract_feedback_joints_raw(value, visited)
            if nested is not None:
                return nested
        return None

    direct = _extract_named_joint_values(lambda name: getattr(feedback, name, None))
    if direct is not None:
        return direct
    for attr_name in (
        "joint_state",
        "joint_feedback",
        "arm_joint",
        "arm_joint_msgs",
        "joint_msgs",
        "joint",
    ):
        if hasattr(feedback, attr_name):
            nested = _extract_feedback_joints_raw(getattr(feedback, attr_name), visited)
            if nested is not None:
                return nested
    return None


def _extract_named_joint_values(get_value: Any) -> list[int] | None:
    name_sets = (
        tuple(f"joint_{index}" for index in range(1, 7)),
        tuple(f"joint{index}" for index in range(1, 7)),
        tuple(f"j{index}" for index in range(1, 7)),
    )
    for names in name_sets:
        values = [get_value(name) for name in names]
        if all(_is_int_like(value) for value in values):
            return [int(value) for value in values]
    return None


def _is_int_like(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def is_default_zero_feedback(joints_raw: Sequence[int]) -> bool:
    """Return true for the SDK's initial/default all-zero feedback frames."""

    return all(int(value) == 0 for value in joints_raw)


def read_stable_slave_feedback(writer: PiperSlaveWriter) -> list[int]:
    """Read recent slave feedback, ignoring initial/default all-zero frames."""

    print("[SLAVE] Reading stable slave joint feedback", flush=True)
    latest: list[int] | None = None
    sample_started_s: float | None = None
    status = RateLimitedPrinter(2.0)

    while True:
        feedback = writer.read_joint_feedback()
        joints = extract_feedback_joints_raw(feedback)
        if joints is None:
            status.print(f"[SLAVE] Waiting for parseable slave joint feedback: {feedback}")
            time.sleep(ALIGN_TICK_S)
            continue
        if is_default_zero_feedback(joints):
            status.print("[SLAVE] Discarding initial/default all-zero slave feedback")
            time.sleep(ALIGN_TICK_S)
            continue

        latest = clamp_joints_raw(joints)
        now_s = time.monotonic()
        if sample_started_s is None:
            sample_started_s = now_s
        if now_s - sample_started_s >= SLAVE_FEEDBACK_SAMPLE_S:
            return latest
        time.sleep(ALIGN_TICK_S)


def wait_for_valid_master_packet(
    *,
    receiver: UdpReceiver,
    tracker: SlavePacketTracker,
    status: RateLimitedPrinter,
    receiver_timeout_s: float,
    purpose: str,
) -> list[int]:
    """Wait for the next valid master packet without commanding the slave."""

    status.print(f"[SLAVE] Waiting for valid master packet for {purpose}; slave is not moving")
    while True:
        received = receiver.recv()
        if received is None:
            warn_if_receiver_timeout(tracker, status, receiver_timeout_s)
            status.print(f"[SLAVE] Still waiting for master packet for {purpose}; slave is not moving")
            continue

        data, address = received
        receiver_time_s = time.monotonic()
        try:
            packet = decode_packet(data)
        except (ValueError, TypeError) as exc:
            status.print(f"[SLAVE] Ignoring malformed packet from {address[0]} during init: {exc}")
            continue

        decision = tracker.process_packet(packet, receiver_time_s)
        if decision.warning:
            status.print(f"[SLAVE] {decision.warning}")
        if not decision.accepted:
            status.print(f"[SLAVE] Ignoring packet from {address[0]} during init: {decision.reason}")
            continue
        if decision.target_joints is None:
            status.print(f"[SLAVE] Ignoring packet from {address[0]} during init: missing joints")
            continue
        return decision.target_joints


def print_start_alignment(master_start: Sequence[int], slave_start: Sequence[int]) -> list[float]:
    """Print startup raw/degree poses and return per-joint degree differences."""

    diffs_deg = [
        raw_to_deg(int(master_value) - int(slave_value))
        for master_value, slave_value in zip(master_start, slave_start, strict=True)
    ]
    print(f"[SLAVE] master_start raw={list(master_start)} deg={format_joint_degrees(master_start)}", flush=True)
    print(f"[SLAVE] slave_start  raw={list(slave_start)} deg={format_joint_degrees(slave_start)}", flush=True)
    print(f"[SLAVE] difference deg={[round(value, 3) for value in diffs_deg]}", flush=True)
    return diffs_deg


def report_alignment_errors(diffs_deg: Sequence[float]) -> bool:
    """Print out-of-threshold joints and return whether startup is acceptable."""

    too_far = [
        (index, diff)
        for index, diff in enumerate(diffs_deg, start=1)
        if abs(diff) > ALIGN_THRESHOLD_DEG
    ]
    if not too_far:
        return True
    for index, diff in too_far:
        print(
            f"[SLAVE] J{index} is too far from master: {diff:+.3f} deg "
            f"(limit {ALIGN_THRESHOLD_DEG:.1f} deg)",
            flush=True,
        )
    print("[SLAVE] Adjust both arms to the same safe visual starting pose and try again", flush=True)
    return False


def slowly_align_slave_to_master_start(
    *,
    writer: PiperSlaveWriter,
    slave_start: Sequence[int],
    master_start: Sequence[int],
) -> bool:
    """Slowly move the slave from feedback pose to the confirmed master pose."""

    commanded = clamp_joints_raw(slave_start)
    target = clamp_joints_raw(master_start)
    max_step_raw = deg_to_raw(ALIGN_STEP_DEG)
    close_raw = deg_to_raw(0.5)
    start_s = time.monotonic()
    next_progress_s = start_s

    print(
        f"[SLAVE] Slowly aligning slave: max {ALIGN_STEP_DEG:.1f} deg every "
        f"{ALIGN_TICK_S * 1000:.0f} ms, timeout {ALIGN_TIMEOUT_S:.0f}s",
        flush=True,
    )

    while True:
        now_s = time.monotonic()
        error_raw = [int(target_value) - int(commanded_value) for target_value, commanded_value in zip(target, commanded, strict=True)]
        max_error_deg = max(abs(raw_to_deg(value)) for value in error_raw)
        if max(abs(value) for value in error_raw) <= close_raw:
            writer.send_joints(target)
            print("[SLAVE] Alignment complete; starting normal teleop", flush=True)
            return True
        if now_s - start_s > ALIGN_TIMEOUT_S:
            print(
                f"[SLAVE] Alignment timed out with max remaining error {max_error_deg:.3f} deg; "
                "slave was not switched to teleop",
                flush=True,
            )
            return False

        commanded = clamp_joints_raw(limit_step_raw(commanded, target, max_step_raw))
        writer.send_joints(commanded)
        if now_s >= next_progress_s:
            print(
                f"[SLAVE] alignment progress cmd_deg={format_joint_degrees(commanded)} "
                f"max_error_deg={max_error_deg:.3f}",
                flush=True,
            )
            next_progress_s = now_s + 0.5
        time.sleep(ALIGN_TICK_S)


def initialize_teleop(
    *,
    init_mode: str,
    receiver: UdpReceiver,
    writer: PiperSlaveWriter,
    tracker: SlavePacketTracker,
    status: RateLimitedPrinter,
    receiver_timeout_s: float,
) -> StartupInit:
    """Run the selected startup initialization before normal teleop."""

    if init_mode == "none":
        print(
            "[SLAVE] WARNING: --init-mode none uses old direct startup behavior. "
            "The slave can jump to the master pose when the first command is sent.",
            flush=True,
        )
        return StartupInit(mode="none")

    wait_for_valid_master_packet(
        receiver=receiver,
        tracker=tracker,
        status=status,
        receiver_timeout_s=receiver_timeout_s,
        purpose="startup",
    )
    print("[SLAVE] First valid master packet received. No slave motion has been commanded.", flush=True)

    while True:
        input(
            "Move both master and slave arms to the same safe visual starting pose. "
            "Press Enter when ready."
        )
        master_start = wait_for_valid_master_packet(
            receiver=receiver,
            tracker=tracker,
            status=status,
            receiver_timeout_s=receiver_timeout_s,
            purpose="alignment check",
        )
        slave_start = read_stable_slave_feedback(writer)
        diffs_deg = print_start_alignment(master_start, slave_start)
        if not report_alignment_errors(diffs_deg):
            continue

        if init_mode == "offset":
            print(
                "[SLAVE] Offset init accepted. Teleop will command "
                "slave_start + (master_current - master_start).",
                flush=True,
            )
            return StartupInit(mode="offset", master_start=master_start, slave_start=slave_start)

        input("Press Enter to slowly move the slave to the master_start pose.")
        if slowly_align_slave_to_master_start(
            writer=writer,
            slave_start=slave_start,
            master_start=master_start,
        ):
            return StartupInit(mode="align", master_start=master_start, slave_start=slave_start)
        print("[SLAVE] Rechecking alignment before teleop.", flush=True)


def main() -> None:
    """Run the UDP-to-Piper slave bridge."""

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

    try:
        startup = initialize_teleop(
            init_mode=args.init_mode,
            receiver=receiver,
            writer=writer,
            tracker=tracker,
            status=status,
            receiver_timeout_s=config.network.receiver_timeout_s,
        )
        last_commanded_joints: list[int] | None = None

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

            command_target_joints = target_joints
            if startup.mode == "offset":
                if startup.master_start is None or startup.slave_start is None:
                    raise RuntimeError("offset startup missing master/slave start poses")
                command_target_joints = apply_offset_command(
                    master_current=target_joints,
                    master_start=startup.master_start,
                    slave_start=startup.slave_start,
                )

            next_joints = choose_command_joints(
                last_commanded_joints=last_commanded_joints,
                target_joints=command_target_joints,
                safety_config=config.safety,
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
