#!/usr/bin/env python3
"""Build minimal master/slave ZIPs using only the Python standard library."""
from pathlib import Path
import argparse
import zipfile
ROOT = Path(__file__).resolve().parents[1]
COMMON = ["__init__.py", "config.py", "logging_utils.py", "packet.py", "safety.py", "udp_transport.py", "dual_arm.py"]
MODULES = {"master": ["master_can_reader.py"], "slave": ["can_utils.py", "receiver_state.py", "slave_can_writer.py"]}

def build_bundle(role, output):
    if role not in MODULES:
        raise ValueError("unknown role")
    files = [f"piper_wireless_teleop/{name}" for name in COMMON + MODULES[role]]
    files += ["configs/default.yaml", "configs/dual_arm.yaml", "scripts/setup_can.sh", "scripts/install_runtime.sh",
              f"requirements-{role}.txt", "docs/dual-arm.md", "AGENTS.md"]
    files += ["scripts/master_sender.py" if role == "master" else "scripts/slave_receiver.py"]
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    target = output / f"piper-teleop-{role}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in files:
            # Normalize text even when built from a Windows checkout.
            data = (ROOT / name).read_bytes().replace(b"\r\n", b"\n")
            archive.writestr(f"piper-teleop-{role}/{name}", data)
    return target

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", choices=("master", "slave", "both"), default="both")
    parser.add_argument("--output", default=str(ROOT / "dist"))
    args = parser.parse_args()
    for role in (("master", "slave") if args.role == "both" else (args.role,)):
        print(build_bundle(role, args.output))
if __name__ == "__main__":
    main()
