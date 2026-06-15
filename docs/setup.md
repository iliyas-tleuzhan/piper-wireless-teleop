# Setup

## Conda Environment

```bash
conda env create -f environment.yml
conda activate piper-wireless-teleop
pip install -r requirements.txt
```

The target Python version is 3.11.

## Apt Packages

```bash
sudo apt update
sudo apt install -y can-utils iproute2 net-tools netcat-openbsd
```

`can-utils` provides tools such as `candump` and `cansend`. `iproute2` provides
`ip link`, which configures SocketCAN devices.

## Python Packages

- `piper_sdk`: official Piper SDK used on the slave computer.
- `python-can`: reads SocketCAN frames on the master computer.
- `PyYAML`: loads `configs/default.yaml`.
- `pytest`: runs tests that do not require hardware.

## CAN Setup

```bash
chmod +x scripts/setup_can.sh
./scripts/setup_can.sh can0 1000000
```

Check traffic:

```bash
candump can0
```

If no frames appear, check CAN-H/CAN-L wiring, termination, arm power, adapter
driver setup, and bitrate.
