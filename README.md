# piper-wireless-teleop

Wireless teleoperation bridge for two AgileX Piper robotic arms using the
official `piper_sdk`.

Architecture:

```text
Master Piper arm -> Computer 1 SocketCAN -> UDP/Wi-Fi -> Computer 2 -> SocketCAN -> Slave Piper arm
```

In wireless mode the master and slave arms must not be connected to the same CAN
bus. Computer 1 connects only to the master Piper. Computer 2 connects only to
the slave Piper.

## Hardware Requirements

- Two AgileX Piper arms.
- Two Linux computers with CAN adapters.
- A Wi-Fi or Ethernet network between the two computers.
- Accessible E-stop or power cutoff for the slave arm.

## Software Requirements

- Linux with SocketCAN.
- Conda.
- Python 3.11.
- `piper_sdk`, `python-can`, `PyYAML`.
- System packages: `can-utils`, `iproute2`, `net-tools`, `netcat-openbsd`.

## Conda Setup

```bash
conda env create -f environment.yml
conda activate piper-wireless-teleop
pip install -r requirements.txt
```

## CAN Setup

```bash
sudo apt update
sudo apt install -y can-utils iproute2 net-tools netcat-openbsd
chmod +x scripts/setup_can.sh
./scripts/setup_can.sh can0 1000000
```

Equivalent manual commands:

```bash
sudo ip link set can0 down
sudo ip link set can0 type can bitrate 1000000 restart-ms 100
sudo ip link set can0 up
ip -details link show can0
```

## Quick Start

Start Computer 2 first. This side moves the slave arm and requires explicit
confirmation:

```bash
PYTHONPATH=. python scripts/slave_receiver.py --can can0 --bind-ip 0.0.0.0 --confirm MOVE
```

Then start Computer 1:

```bash
PYTHONPATH=. python scripts/master_sender.py --can can0 --target-ip <COMPUTER_2_IP> --deadman
```

UDP-only test without Piper hardware:

```bash
# Computer 2
PYTHONPATH=. python scripts/test_udp.py receiver --bind-ip 0.0.0.0 --port 5005

# Computer 1
PYTHONPATH=. python scripts/test_udp.py sender --target-ip <COMPUTER_2_IP> --port 5005
```

## Safety Checklist

- Keep the slave arm power cutoff or E-stop within reach.
- Power-cycle the slave Piper fresh before important tests.
- Start with both arms in similar poses.
- Confirm the master and slave are not on the same CAN bus.
- Test UDP before enabling robot movement.
- Check `can0` with `ip -details link show can0` and `candump can0`.
- Run `PYTHONPATH=. python scripts/test_slave_small_move.py --can can0 --confirm MOVE`.
- Start `PYTHONPATH=. python scripts/slave_receiver.py --can can0 --bind-ip 0.0.0.0 --confirm MOVE`.
- Start `PYTHONPATH=. python scripts/master_sender.py --can can0 --target-ip <COMPUTER_2_IP> --deadman`.
- Move slowly first.
- Use `--deadman` on the master sender; packets with `deadman=false` are ignored.

## Configuration

Defaults live in `configs/default.yaml`. Normal commands do not include `--speed`
or `--max-jump-deg`; Piper mode, speed, receiver timeout, and status rate are
config values. Sender packet timestamps are for debugging only. The slave uses
receiver-side `time.monotonic()` and sequence numbers, so Computer 1 and
Computer 2 wall clocks do not need to be synchronized for timeout safety.

Wireless teleop commands the latest valid master target directly by default.
Slew limiting is disabled by default because limiting every packet makes the
slave feel much slower than wired Piper master-slave teleoperation. It remains
available only as an explicit config fallback with `safety.enable_slew_limit`.

Important defaults:

- CAN bitrate: `1000000`
- UDP port: `5005`
- Master send rate: `50 Hz`
- Receiver timeout: `0.5 s`
- Status output: `2 Hz`
- Piper speed percent: `100`
- Follow/high-follow mode: `0xAD`
- Joint hard bounds: J1 `-154..154`, J2 `0..195`, J3 `-175..0`,
  J4 `-106..106`, J5 `-75..75`, J6 `-120..120` degrees
- Slew limiting: disabled by default

## Troubleshooting Summary

- `can0` missing: check adapter drivers and run `ip link`.
- `candump can0` shows nothing: check wiring, bitrate, termination, and power.
- UDP packets not arriving: verify IP address, firewall, subnet, and port `5005`.
- Slave not moving: confirm `--confirm MOVE`, `--deadman`, Piper enable state, and
  that valid packets are arriving before the receiver timeout.
- Gripper moves but joints do not: the slave Piper controller may be stuck in a
  stale hold/control/motion-mode state. Stop `slave_receiver.py`, run
  `slave_release.py`, restart `slave_receiver.py`, then power-cycle the slave arm
  if joints still ignore commands.
- Negative packet age: no longer a safety error; sender timestamps are debug-only.
- Delayed movement: reduce Wi-Fi congestion, avoid verbose packet logging, and
  keep the control machines close to the access point.

More detail is in `docs/`.
