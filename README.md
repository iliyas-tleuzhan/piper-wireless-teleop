# piper-wireless-teleop

Wireless master-slave teleoperation bridge for AgileX PiPER-X arms.

```text
Master PiPER-X -> Computer 1 CAN -> UDP/Wi-Fi -> Computer 2 -> CAN -> Slave PiPER-X
```

The network transport is still the original UDP bridge. Arm-specific behavior is isolated in profiles and SDK adapters. This branch defaults to `piper_x`; the older standard `piper` profile remains available in code for compatibility.

## PiPER-X SDK Decision

Use official AgileX `pyAgxArm` for PiPER-X. The inspected upstream HEAD was:

- `pyAgxArm`: `cc498c00af0bcb9e297943e94f4792c0e3ee5b2c`
- `agx_arm_urdf`: `f6642ce0d7872c686f29c99e9e10cd23d1d49313`
- `piper_sdk`: `c05c5454b1cf61c05ad26385e0c0a3aa6d3c7bad`
- `agx_arm_ros`: `91e6b2e5eb2d9880e85230d0add9945e27387d87`

`pyAgxArm` explicitly exports `ArmModel.PIPER_X`, PiPER-series firmware selectors, PiPER-X drivers, PiPER-X demos, and PiPER-X joint/MDH presets. `piper_sdk` documents the original PiPER V2 master-slave CAN frames and remains useful for standard PiPER, but it does not expose a PiPER-X model selector in the inspected source.

## Verified Configuration

Defaults live in `configs/default.yaml`.

- Arm profile: `piper_x`
- CAN bitrate: `1000000`
- CAN channel: `can0`
- SDK CAN interface: `socketcan`
- UDP port: `5005`
- Master send rate: `50 Hz`
- Receiver timeout: `0.5 s`
- Status output: `2 Hz`
- PiPER-X command units on the wire: six joints in raw `0.001 degree` units plus optional gripper
- PiPER-X SDK command stream: `pyAgxArm.move_js()` radians after startup sync
- PiPER-X master feedback API: `pyAgxArm.get_leader_joint_angles()` radians
- PiPER-X gripper command API: `AGX_GRIPPER.move_gripper_m()` meters/Newtons
- PiPER-X firmware selector: `PiperFW.V189` by default

PiPER-X runtime limits are stored in `piper_wireless_teleop/arm_profile.py` from official PiPER-X URDF limits:

```text
J1 -150..150 deg
J2    0..180 deg
J3 -170..0 deg
J4  -89..89 deg
J5  -89..89 deg
J6 -120..120 deg
Gripper 0..100000 raw um-style command units
```

Note: the inspected `pyAgxArm` constants list PiPER-X J6 as `[-180, 180]`, while official `agx_arm_urdf/piper_x_description.urdf` lists J6 as approximately `[-120, 120]`. This bridge uses the narrower URDF limit until hardware/firmware feedback confirms otherwise.

## Install

```bash
sudo apt update
sudo apt install -y can-utils iproute2 net-tools netcat-openbsd
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` pins `pyAgxArm` to the inspected official commit.

## CAN Setup

Run on both computers:

```bash
sudo ip link set can0 down || true
sudo ip link set can0 type can bitrate 1000000
sudo ip link set can0 up
ip -details link show can0
```

Expected CAN status includes `state UP` and `bitrate 1000000`. Use `candump can0` to confirm frames before commanding motion. Do not let this bridge automatically change persistent leader/follower arm modes during bring-up; configure those modes deliberately with official tools only if your hardware/firmware procedure requires it.

## Computer 2: Slave

Start the receiver first:

```bash
PYTHONPATH=. python scripts/slave_receiver.py --can can0 --bind-ip 0.0.0.0
```

Expected output:

```text
[SLAVE] Listening on 0.0.0.0:5005
[SLAVE] Connecting to slave Piper on can0
[SLAVE] Arm enabled and motion mode configured
```

The default startup mode samples current master packets and current slave feedback, waits until poses are within the startup threshold, then slowly aligns the slave before normal teleop. Valid packets keep sequence/deadman/stale-packet safety. Malformed, NaN, infinity, wrong-length, out-of-range, duplicate, stale, and `deadman=false` packets are rejected.

Shutdown/release:

```bash
Ctrl+C
python slave_release.py
```

`slave_release.py` takes no arguments, loads `configs/default.yaml`, connects to `can0`, and calls the configured SDK disable path.

## Computer 1: Master

After Computer 2 is listening:

```bash
PYTHONPATH=. python scripts/master_sender.py --can can0 --target-ip <COMPUTER_2_IP> --deadman
```

Expected output:

```text
[MASTER] profile=piper_x can=can0 bitrate=1000000
[MASTER] Sending UDP to <COMPUTER_2_IP>:5005
[MASTER] Reading PiPER-X master feedback through pyAgxArm
```

The master reads all six PiPER-X leader joints from `pyAgxArm.get_leader_joint_angles()`, validates complete fresh feedback, reads gripper feedback when available, and transmits the latest complete state at the configured fixed rate. The inspected pyAgxArm parser maps those leader joint frames to the physical leader command CAN IDs `0x155`, `0x156`, and `0x157`.

## UDP-Only Test

```bash
# Computer 2
PYTHONPATH=. python scripts/test_udp.py receiver --bind-ip 0.0.0.0 --port 5005

# Computer 1
PYTHONPATH=. python scripts/test_udp.py sender --target-ip <COMPUTER_2_IP> --port 5005
```

## Safe First Hardware Test

Do not start full teleoperation first. Proceed in this exact order:

1. Secure both arms and clear the workspace.
2. Confirm CAN and joint feedback without commanding motion.
3. Compare physical joint movement against reported joint order and signs.
4. Test the gripper separately.
5. Test one joint at a time using very small movement.
6. Verify every joint limit.
7. Test packet timeout and disconnect handling.
8. Only then allow complete master-slave teleoperation.

No real PiPER-X hardware validation has been performed by this repository change. Treat the joint signs, gripper scaling, actual firmware version, whether the master is already publishing leader joint frames, and the J6 limit mismatch as first-hardware-test verification items.

## Troubleshooting

- `can0` missing: check adapter driver, USB path, and `ip link`.
- `candump can0` is silent: check arm power, CAN wiring, termination, and bitrate.
- Master says feedback is stale or missing: confirm `pyAgxArm` can read `get_leader_joint_angles()` from the master PiPER-X on the same CAN channel and that the master is configured to publish leader joint frames.
- Slave refuses packets: inspect the reason printed by `[SLAVE]`; common causes are missing `--deadman`, wrong joint count, out-of-range PiPER-X wrist values, or stale/duplicate sequence numbers.
- Slave connects but does not move: verify arm enable state, CAN traffic on Computer 2, and that the master and slave are not connected to the same CAN bus.
- Gripper errors: gripper validation is isolated, so joint updates continue even if gripper feedback/commands are unavailable.
- After an exception or Ctrl+C: run `python slave_release.py`, power-cycle if necessary, then bring CAN up again.

## Automated Validation

Run:

```bash
pytest -q
python -m compileall piper_wireless_teleop scripts slave_release.py
```

The tests cover PiPER-X joint order/sign conversion, units and scaling, joint-limit validation, master feedback conversion, slave command generation with mocked SDK behavior, six-joint-plus-gripper packets, malformed packet rejection, sequence/stale-packet behavior, deadman rejection, startup synchronization helpers, and clean shutdown adapter behavior.
