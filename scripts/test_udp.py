#!/usr/bin/env python3
"""Network-only UDP test that does not require Piper hardware."""

from __future__ import annotations

import argparse
import time

from piper_wireless_teleop.packet import decode_packet, encode_packet, make_packet
from piper_wireless_teleop.udp_transport import UdpReceiver, UdpSender


def main() -> None:
    """Run as either a UDP sender or receiver."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("sender", "receiver"))
    parser.add_argument("--target-ip", default="127.0.0.1")
    parser.add_argument("--bind-ip", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5005)
    parser.add_argument("--rate", type=float, default=2.0)
    args = parser.parse_args()

    if args.mode == "receiver":
        receiver = UdpReceiver(args.bind_ip, args.port, timeout_s=0.5)
        print(f"[UDP] receiving on {args.bind_ip}:{args.port}", flush=True)
        try:
            while True:
                received = receiver.recv()
                if received is None:
                    continue
                data, address = received
                print(f"[UDP] from={address} packet={decode_packet(data)}", flush=True)
        except KeyboardInterrupt:
            print("\n[UDP] receiver stopped", flush=True)
        finally:
            receiver.close()
        return

    sender = UdpSender(args.target_ip, args.port)
    interval_s = 1.0 / args.rate
    sequence = 0
    print(f"[UDP] sending to {args.target_ip}:{args.port}", flush=True)
    try:
        while True:
            packet = make_packet(
                sequence=sequence,
                timestamp=time.time(),
                deadman=True,
                joints_raw=[0, 1000, -1000, 0, 0, 0],
                gripper=None,
            )
            sender.send(encode_packet(packet))
            print(f"[UDP] sent seq={sequence}", flush=True)
            sequence += 1
            time.sleep(interval_s)
    except KeyboardInterrupt:
        print("\n[UDP] sender stopped", flush=True)
    finally:
        sender.close()


if __name__ == "__main__":
    main()
