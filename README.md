# Dual Piper-X wireless teleoperation

Two master Piper-X arms on Linus (a Jetson master computer) send joint/gripper targets over
UDP/Wi-Fi to two slave arms on an NVIDIA Orin. One worker per arm keeps routing,
packet tracking and startup alignment separate. Bunker Mini chassis control and
LoRa transport are outside this repository's dual-arm runtime.

## Current setup

| Side | Linus master CAN | Orin slave CAN | UDP port |
| --- | --- | --- | --- |
| Left | can2 | can2 | 5005 |
| Right | can1 | can3 | 5006 |

- Linus: Jetson master computer; SSH `<LINUS_USER>@<LINUS_IP>`.
- Orin: Ubuntu 22.04 ARM64; SSH `dase-orin@192.168.1.144`.
- Each arm has a separate CAN bus at 1 Mbps.
- Mapping is in [configs/dual_arm.yaml](configs/dual_arm.yaml). Numbered adapter
  names can change after reboot: confirm the physical mapping before motion.

## Minimal downloads

Download the ZIP for each machine; no full repository clone is required:

- [Linus master bundle](bundles/piper-teleop-master.zip): python-can and PyYAML.
- [Orin slave bundle](bundles/piper-teleop-slave.zip): piper_sdk and PyYAML.

Their dependencies are installed as needed. Bundles exclude tests, Git history,
Arduino/LoRa firmware and development tools. Each contains its worker, required
Python modules, configuration, setup scripts and operating guide.
See [deployment instructions](docs/dual-arm.md) for SCP and update commands.

On each machine install the OS prerequisites once:

```bash
sudo apt update
sudo apt install --no-install-recommends python3-venv iproute2 unzip
```

On Linus, after transferring its ZIP to ~/iliyas:

```bash
cd ~/iliyas
unzip -o piper-teleop-master.zip
cd piper-teleop-master
bash scripts/install_runtime.sh master
bash scripts/setup_can.sh can2
bash scripts/setup_can.sh can1
.venv/bin/python -m piper_wireless_teleop.dual_arm master --target-ip 192.168.1.144 --deadman --dry-run
```

On the Orin:

```bash
cd ~/iliyas
unzip -o piper-teleop-slave.zip
cd piper-teleop-slave
bash scripts/install_runtime.sh slave
bash scripts/setup_can.sh can3
bash scripts/setup_can.sh can2
.venv/bin/python -m piper_wireless_teleop.dual_arm slave --dry-run
```

Use the system Python in a private .venv; Conda is optional and is not required.
On Ubuntu 22.04, install python3.10-venv if ensurepip is missing.

## Run

Physically align each master/slave pair and keep the slave power cutoff nearby.
Start the Orin receiver first (from its extracted bundle directory):

```bash
.venv/bin/python -m piper_wireless_teleop.dual_arm slave --confirm MOVE
```

Then start on Linus:

```bash
.venv/bin/python -m piper_wireless_teleop.dual_arm master --target-ip 192.168.1.144 --deadman
```

These commands enable motion. Logs carry LEFT/RIGHT labels. Each receiver waits
for targets within 15 degrees of the slave feedback pose, then slowly aligns.
Gripper forwarding begins after initialization. Ctrl+C stops both local workers;
a local worker exit also stops its sibling. Linux workers receive a single
supervisor interrupt so cleanup is not interrupted by duplicate terminal signals.

## Behavior and validation status

The sender reads command IDs 0x155/0x156/0x157 and sends at 250 Hz, including while
the master is stationary. The receiver tracks sequences and uses a local 0.5 s
UDP timeout; sender/receiver clocks need not match. Network loss stops new commands,
but does not physically disable motors. The sender keeps its last complete target
if CAN input disappears. --deadman is a packet flag, not a physical hold-to-run switch.

Local joint clamps use official Piper-X presets in degrees: J1 +/-150, J2 0..180,
J3 -170..0, J4/J5 +/-89, J6 +/-170. They do not change firmware or SDK limits.
The backend remains piper_sdk.C_PiperInterface_V2; firmware/SDK compatibility and
actual slave following are still under investigation. Field logs confirmed two
accepted UDP streams around 48 Hz at the former 50 Hz setting and changing left-master CAN targets, but do
not establish successful physical teleoperation. No collision avoidance or
synchronized dual-arm execution is implemented.

## Repository structure

| Directory | Purpose |
| --- | --- |
| piper_wireless_teleop/ | Runtime modules and dual-arm launcher |
| configs/ | Runtime settings and left/right mapping |
| scripts/ | Workers, installer, bundle builder and diagnostics |
| bundles/ | Ready-to-transfer master/slave ZIPs |
| docs/ | Deployment, control behavior and troubleshooting |
| tests/ | Development tests; excluded from deployments |
| arduino/ | Optional existing Wi-Fi access-point firmware |

Single-pair scripts remain available; see [script reference](docs/scripts.md).
The older tmux/SSH launcher uses its own single-pair settings; it is not the
recommended dual-arm launcher. See [safety behavior](docs/safety.md) for details.

## Development and rebuild

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python scripts/build_runtime_bundle.py
```

The builder writes bundles/ by default and normalizes Linux text line endings.
Rebuild both ZIPs whenever packaged code/configuration/docs change; use --output
for a different destination. Tests cover routing, worker imports from extracted
bundles, Windows line-ending normalization and process supervision. Linux signal
cleanup also needs testing on the target devices. Dependencies are unpinned;
record deployed versions for a reproducible installation.

Work on a development branch and commit as Iliyas. Commit/merge main only when
explicitly instructed. See [AGENTS.md](AGENTS.md).

## Automatic CAN selection

The [master](docs/bundles/master-README.md) and [slave](docs/bundles/slave-README.md)
guides explain one-time USB adapter registration. The launcher then resolves
left/right by unique serial number or fixed USB port instead of trusting canN.
Missing or ambiguous registered adapters prevent startup. Run the identity tool's
setup command after reboot to configure the resolved buses. It identifies CAN
adapters, not the attached arms; confirm the initial physical cable mapping.

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
