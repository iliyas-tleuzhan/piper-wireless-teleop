"""Hardware-free benchmark adapted from piper-250-edit/verify_250.py.

Runs the real sender with a simulated CAN source and real loopback UDP for 2 s.
Reports achieved host timing; this does not measure Wi-Fi or actual robot control.
"""
import contextlib
import io
import json
import runpy
import socket
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

import can
import yaml

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
routes = yaml.safe_load((root / "configs/dual_arm.yaml").read_text())["arms"]
assert routes["left"]["master_can"] == "can2"
assert routes["right"]["master_can"] == "can1"
assert routes["left"]["udp_port"] == 5005
assert routes["right"]["udp_port"] == 5006
assert routes["left"]["slave_can"] == "can2"
assert routes["right"]["slave_can"] == "can3"

receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
receiver.bind(("127.0.0.1", 0))
receiver.settimeout(0.1)
packets = []
finished = threading.Event()


def collect():
    while not finished.is_set():
        try:
            data, _ = receiver.recvfrom(65535)
        except socket.timeout:
            continue
        packets.append((time.monotonic(), json.loads(data)))


class SimulatedBus:
    def __init__(self):
        self.frames = iter(
            can.Message(arbitration_id=key, data=bytes(8), is_extended_id=False)
            for key in (0x155, 0x156, 0x157)
        )
        self.deadline = time.monotonic() + 2.0
        self.closed = False

    def recv(self, timeout):
        assert 0 <= timeout <= 0.001
        if time.monotonic() >= self.deadline:
            raise KeyboardInterrupt
        frame = next(self.frames, None)
        if frame is None:
            time.sleep(timeout)
        return frame

    def shutdown(self):
        self.closed = True


thread = threading.Thread(target=collect)
thread.start()
bus = SimulatedBus()
args = [
    "master_sender.py", "--target-ip", "127.0.0.1",
    "--target-port", str(receiver.getsockname()[1]),
    "--config", str(root / "configs/default.yaml"),
]
try:
    with patch("can.interface.Bus", return_value=bus), patch.object(sys, "argv", args):
        with contextlib.redirect_stdout(io.StringIO()):
            runpy.run_path(str(root / "scripts/master_sender.py"), run_name="__main__")
finally:
    finished.set()
    thread.join()
    receiver.close()

assert bus.closed
assert len(packets) >= 2, "Not enough packets received"
assert [p["seq"] for _, p in packets] == list(range(len(packets)))
assert all(p["deadman"] is False for _, p in packets)
hz = (len(packets) - 1) / (packets[-1][0] - packets[0][0])

print(f"MEASURED: dual-arm routes; simulated CAN -> loopback UDP: {len(packets)} packets, {hz:.2f} Hz; no hardware CAN access")
