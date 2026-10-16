# Master bundle: Linus (Jetson master computer)

Start here. This bundle reads both master Piper-X arms and sends their latest
joint/gripper targets to the Orin over UDP/Wi-Fi. It does not control slave motors.

- Device: Linus; Jetson model and OS version to be confirmed.
- SSH: `ssh <LINUS_USER>@<LINUS_IP>`.
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
| scripts/verify_250.py | Hardware-free simulated CAN to loopback UDP timing check |
| scripts/master_sender.py | Reads one master CAN bus and sends UDP targets |
| piper_wireless_teleop/dual_arm.py | Starts and supervises both labeled senders |
| piper_wireless_teleop/master_can_reader.py | Decodes command IDs 0x155/156/157, gripper 0x159 |
| piper_wireless_teleop/packet.py | Builds and serializes target packets |
| piper_wireless_teleop/udp_transport.py | UDP send/receive wrappers |
| piper_wireless_teleop/safety.py | Shared units, validation and Piper-X joint presets |
| piper_wireless_teleop/config.py | Loads runtime configuration |
| piper_wireless_teleop/logging_utils.py | Rate-limits status output |
| piper_wireless_teleop/__init__.py | Python package declaration |
| requirements-master.txt | python-can and PyYAML; no Piper SDK needed on Linus |
| docs/dual-arm.md | Combined installation and operating guide |
| AGENTS.md | Source contribution and commit rules |

The installer adds .venv locally; it is not included in the ZIP. No tests, Conda,
ROS packages, Arduino firmware or development tools are installed by this bundle.

## Install and check (on Linus)

```bash
sudo apt update
sudo apt install --no-install-recommends python3-venv iproute2 unzip
cd ~/iliyas
unzip -o piper-teleop-master.zip
cd piper-teleop-master
bash scripts/install_runtime.sh master
bash scripts/setup_can.sh can2
bash scripts/setup_can.sh can1
.venv/bin/python -m piper_wireless_teleop.dual_arm master --target-ip 192.168.1.144 --deadman --dry-run
```

## Start sending

First start the slave receiver on Orin. Then, from this directory:

```bash
.venv/bin/python -m piper_wireless_teleop.dual_arm master --target-ip 192.168.1.144 --deadman
```

LEFT reads can2 and sends to port 5005; RIGHT reads can1 and sends to port 5006.
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

| Side | Linus master | Orin slave | UDP port |
| --- | --- | --- | --- |
| Left | can2 | can2 | 5005 |
| Right | can1 | can3 | 5006 |

Each arm uses a separate CAN bus at 1 Mbps. Numbered CAN interfaces can swap
after reboot or USB reconnect; verify the physical mapping before motion.
The Bunker Mini chassis and LoRa are not controlled by these bundles.

## Settings and timing

`configs/dual_arm.yaml` maps left/right labels to CAN interfaces and UDP ports.
`configs/default.yaml` holds transport timing and Piper motion settings.
Current defaults: 250 Hz per arm, 0.5 s receiver timeout, 2 Hz status logs,
100 percent speed setting and follow mode 0xAD. The sender targets 250 Hz (4 ms); actual rates depend on host/network/CAN timing.
Wi-Fi field logs showed approximately 48 Hz accepted packets per arm at the former 50 Hz setting.

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

## Remember USB adapters (recommended)

Stop teleop and physically trace left/right cables once. List the current adapters:

```bash
.venv/bin/python -m piper_wireless_teleop.can_identity list
```

Register using the CURRENT interface names (the example assumes the table above):

```bash
.venv/bin/python -m piper_wireless_teleop.can_identity register --role master --left can2 --right can1

```

After reboot, resolve the adapters and configure their current CAN names:

```bash
.venv/bin/python -m piper_wireless_teleop.can_identity check --role master
.venv/bin/python -m piper_wireless_teleop.can_identity setup --role master

```

The usual dual_arm launcher automatically loads this registration, including in
--dry-run. It prefers a unique adapter serial; without one it binds to the USB
port path. Keep ports/hubs unchanged for path-based registration. It remembers
adapters, not physical arms: swapping CAN cables between adapters changes which
arm is controlled. Duplicate serials discovered later or missing adapters prevent
startup; no fallback to numbered CAN names occurs after registration. Check output
and physically verify mapping before motion. Unsupported non-USB adapters cannot
be registered by this tool. setup brings CAN down/up and must run only with teleop
stopped; it does not send motor commands.

Registration lives in configs/can-identities-master.json on THIS computer.
It survives ZIP extraction with unzip -o but is lost if you delete the deployment
folder. Back it up locally; do not copy it to the other host. No extra packages
or udev rules are required. Re-register after replacing an adapter, changing USB
topology for a port-bound device, or changing which arm its CAN cable connects to.

## 250 Hz timing

The default sender targets 250 packets/s per arm (4 ms). CAN receive waits are
capped by the next deadline and 1 ms socket timeout. Deadlines advance on a fixed
schedule and missed slots are skipped rather than replayed in a burst. This uses
the supplied piper-250-edit timing implementation. Fresh master CAN data can be
slower than UDP transmission; repeated latest targets are intentional. Linux
scheduling, Wi-Fi jitter, CAN traffic and SDK overhead determine achieved rates.
The older 48 Hz field observations were made with the previous 50 Hz setting.

On Linus, run the optional hardware-free timing check from its bundle directory:

```bash
.venv/bin/python scripts/verify_250.py
```

This uses a simulated CAN source and real loopback UDP, not robot hardware or
Wi-Fi. Check the printed achieved rate; it is not proof of 250 Hz physical arm
control. The Orin logs report accepted command rate during real teleoperation.

Linux/WSL verification of this version: 49 tests passed and the simulated-CAN
loopback benchmark measured 250.06 Hz. That measurement is host-local, not an
end-to-end Wi-Fi or physical arm measurement. Existing adapter registrations are
machine-specific: re-register on Linus instead of copying the old master's JSON.
