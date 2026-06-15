#!/usr/bin/env python3
"""Release/disable the slave Piper arm without commanding motion."""

import sys

from piper_sdk import C_PiperInterface_V2


def main() -> int:
    """Connect to the Piper on can0 and send a release/disable command."""

    can_name = "can0"

    print(f"[INFO] Connecting to Piper on {can_name}")
    try:
        try:
            arm = C_PiperInterface_V2(can_name, False)
        except TypeError:
            arm = C_PiperInterface_V2(can_name)
        arm.ConnectPort()
    except Exception as exc:
        print(f"[ERROR] Failed to connect to Piper: {exc}")
        return 1

    print("[INFO] Trying to release/disable the arm...")
    try:
        if hasattr(arm, "DisableArm"):
            try:
                arm.DisableArm(7)
            except TypeError:
                arm.DisableArm()
            print("[OK] Called DisableArm")
            print("[OK] Arm release/disable command sent.")
            return 0

        for method_name in ("StopArm", "EmergencyStop", "ReleaseArm"):
            method = getattr(arm, method_name, None)
            if callable(method):
                method()
                print(f"[OK] Called {method_name}")
                print("[OK] Arm release/disable command sent.")
                return 0
    except Exception as exc:
        print(f"[ERROR] Release/disable command failed: {exc}")

    candidates = [
        name
        for name in dir(arm)
        if "Disable" in name or "Enable" in name or "Stop" in name or "Release" in name
    ]
    print(f"[ERROR] Candidate methods: {candidates}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
