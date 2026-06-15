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
python scripts/slave_receiver.py --can can0 --confirm MOVE
```

Then start Computer 1:

```bash
python scripts/master_sender.py --target-ip <COMPUTER_2_IP> --can can0 --deadman
```

UDP-only test without Piper hardware:

```bash
# Computer 2
python scripts/test_udp.py receiver --bind-ip 0.0.0.0 --port 5005

# Computer 1
python scripts/test_udp.py sender --target-ip <COMPUTER_2_IP> --port 5005
```

## Safety Checklist

- Keep the slave arm power cutoff or E-stop within reach.
- Start with both arms in similar poses.
- Confirm the master and slave are not on the same CAN bus.
- Test UDP before enabling robot movement.
- Test each CAN bus with `candump can0`.
- Run the slave receiver first, then the master sender.
- Use `--deadman` on the master sender; packets with `deadman=false` are ignored.

## Configuration

Defaults live in `configs/default.yaml`. Normal commands do not include `--speed`
or `--max-jump-deg`; speed, follow mode, stale-packet age, status rate, and slew
limit are config values.

Important defaults:

- CAN bitrate: `1000000`
- UDP port: `5005`
- Master send rate: `50 Hz`
- Max packet age: `0.25 s`
- Piper speed percent: `100`
- Follow/high-follow mode: `0xAD`
- Slew limit: `3.0 degrees`
- Status output: `2 Hz`

## Troubleshooting Summary

- `can0` missing: check adapter drivers and run `ip link`.
- `candump can0` shows nothing: check wiring, bitrate, termination, and power.
- UDP packets not arriving: verify IP address, firewall, subnet, and port `5005`.
- Slave not moving: confirm `--confirm MOVE`, `--deadman`, Piper enable state, and
  that packets are not stale.
- Delayed movement: reduce Wi-Fi congestion, avoid verbose packet logging, and
  keep the control machines close to the access point.

More detail is in `docs/`.
