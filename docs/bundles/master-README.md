# Master bundle: Raspberry Pi 5

Start here. This bundle reads both master Piper-X arms and sends their latest
joint/gripper targets to the Orin over UDP/Wi-Fi. It does not control slave motors.

- Device: Raspberry Pi 5, Ubuntu Server 24.04 LTS ARM64.
- SSH: `ssh dase-raspberrypi@192.168.1.145`.
- Install directory: `~/iliyas/piper-teleop-master`.
- Destination: Orin at `192.168.1.144`.

## Where to find things

| File | Purpose |
| --- | --- |
| README.md | This master-side guide |
| configs/dual_arm.yaml | Left/right CAN and UDP routing |
| configs/default.yaml | Send rate, timeouts and control defaults |
| scripts/install_runtime.sh | Creates .venv and installs master dependencies |
| scripts/setup_can.sh | Configures one SocketCAN interface at 1 Mbps |
| scripts/master_sender.py | Reads one master CAN bus and sends UDP targets |
| piper_wireless_teleop/dual_arm.py | Starts and supervises both labeled senders |
| piper_wireless_teleop/master_can_reader.py | Decodes command IDs 0x155/156/157, gripper 0x159 |
| piper_wireless_teleop/packet.py | Builds and serializes target packets |
| piper_wireless_teleop/udp_transport.py | UDP send/receive wrappers |
| piper_wireless_teleop/safety.py | Shared units, validation and Piper-X joint presets |
| piper_wireless_teleop/config.py | Loads runtime configuration |
| piper_wireless_teleop/logging_utils.py | Rate-limits status output |
| piper_wireless_teleop/__init__.py | Python package declaration |
| requirements-master.txt | python-can and PyYAML; no Piper SDK needed on Pi |
| docs/dual-arm.md | Combined installation and operating guide |
| AGENTS.md | Source contribution and commit rules |

The installer adds .venv locally; it is not included in the ZIP. No tests, Conda,
ROS packages, Arduino firmware or development tools are installed by this bundle.

## Install and check (on the Pi)

```bash
sudo apt update
sudo apt install --no-install-recommends python3-venv iproute2 unzip
cd ~/iliyas
unzip -o piper-teleop-master.zip
cd piper-teleop-master
bash scripts/install_runtime.sh master
bash scripts/setup_can.sh can0
bash scripts/setup_can.sh can1
.venv/bin/python -m piper_wireless_teleop.dual_arm master --target-ip 192.168.1.144 --deadman --dry-run
```

## Start sending

First start the slave receiver on Orin. Then, from this directory:

```bash
.venv/bin/python -m piper_wireless_teleop.dual_arm master --target-ip 192.168.1.144 --deadman
```

LEFT reads can0 and sends to port 5005; RIGHT reads can1 and sends to port 5006.
The process keeps transmitting while the master is stationary. It also retains
its last complete target if master CAN input disappears. --deadman sets a packet
flag; it is not a physical hold-to-run switch. Changing the target IP is a launcher
argument; it is not stored in dual_arm.yaml.

## Troubleshooting

- `Waiting for complete ... target`: verify power, CAN wiring and command frames.
- Fixed logged angles while moving: inspect the master CAN command stream.
- `No module named ...`: use the latest complete bundle and the .venv interpreter.
- Nothing reaches Orin: check its address, Wi-Fi and UDP ports 5005/5006.
- After reboot: configure CAN again and verify which arm each interface represents.

## System mapping

| Side | Pi master | Orin slave | UDP port |
| --- | --- | --- | --- |
| Left | can0 | can3 | 5005 |
| Right | can1 | can2 | 5006 |

Each arm uses a separate CAN bus at 1 Mbps. Numbered CAN interfaces can swap
after reboot or USB reconnect; verify the physical mapping before motion.
The Bunker Mini chassis and LoRa are not controlled by these bundles.

## Settings and timing

`configs/dual_arm.yaml` maps left/right labels to CAN interfaces and UDP ports.
`configs/default.yaml` holds transport timing and Piper motion settings.
Current defaults: 50 Hz per arm, 0.5 s receiver timeout, 2 Hz status logs,
100 percent speed setting and follow mode 0xAD. 250 Hz has not been implemented.
Wi-Fi field logs showed approximately 48 Hz accepted packets per arm.

## Validation status

Automated tests cover routing, packet handling, bundle imports and supervision.
Field tests confirmed changing master CAN command targets and two accepted UDP
streams. Successful physical slave following has not yet been demonstrated.
Piper-X firmware and installed SDK compatibility still need verification.
A dry run only prints the worker commands; it does not test CAN, Wi-Fi or motors.

## Updating and stopping

Stop teleop before replacing files. Extract the updated ZIP with `unzip -o` in
~/iliyas. This preserves .venv but overwrites the bundled configuration files;
back up any local configuration edits first. Rerun the installer if dependencies
change. Ctrl+C stops both workers on this computer. A worker exit stops its local
sibling; this does not remotely stop the other computer or disable motor power.

## Further reading

`docs/dual-arm.md` contains the full two-computer deployment guide.
Source repository: https://github.com/iliyas-tleuzhan/piper-wireless-teleop
These are minimal deployment archives, not Git checkouts. Modify source and run
`python scripts/build_runtime_bundle.py` to regenerate them.
