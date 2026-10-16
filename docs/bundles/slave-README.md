# Slave bundle: NVIDIA Orin

Start here. This bundle receives the two Wi-Fi streams from the Pi and commands
the corresponding slave Piper-X arms through the official piper_sdk backend.
Running with --confirm MOVE enables robot motion.

- Device: NVIDIA Orin, Ubuntu 22.04.5 LTS ARM64.
- SSH: `ssh dase-orin@192.168.1.144`.
- Install directory: `~/iliyas/piper-teleop-slave`.
- Master Pi: `192.168.1.145`.
- Confirmed slave routing: LEFT can2; RIGHT can3.

## Where to find things

| File | Purpose |
| --- | --- |
| README.md | This slave-side guide |
| configs/dual_arm.yaml | Left/right CAN and UDP routing |
| configs/default.yaml | Timeouts, motion mode and speed defaults |
| scripts/install_runtime.sh | Creates .venv and installs slave dependencies |
| scripts/setup_can.sh | Configures one SocketCAN interface at 1 Mbps |
| scripts/slave_receiver.py | One receiver: startup alignment and joint/gripper commands |
| piper_wireless_teleop/dual_arm.py | Starts and supervises both labeled receivers |
| piper_wireless_teleop/slave_can_writer.py | C_PiperInterface_V2, JointCtrl and GripperCtrl calls |
| piper_wireless_teleop/receiver_state.py | Packet validation, sequences and timeout tracking |
| piper_wireless_teleop/safety.py | Piper-X joint clamps, unit conversion and optional slew limiting |
| piper_wireless_teleop/can_utils.py | Resets CAN interfaces on receiver exit |
| piper_wireless_teleop/packet.py | Decodes incoming target packets |
| piper_wireless_teleop/udp_transport.py | UDP socket wrappers |
| piper_wireless_teleop/config.py | Loads runtime configuration |
| piper_wireless_teleop/logging_utils.py | Rate-limits status output |
| piper_wireless_teleop/__init__.py | Python package declaration |
| requirements-slave.txt | piper_sdk and PyYAML; SDK brings python-can |
| docs/dual-arm.md | Combined installation and operating guide |
| AGENTS.md | Source contribution and commit rules |

The installer adds .venv locally; it is not shipped in the ZIP. The observed Orin
SDK version was 0.6.2. Requirements are unpinned, so a fresh install may differ.
No ROS packages, Conda, Arduino firmware or development tools are installed.

## Install and check (on the Orin)

```bash
sudo apt update
sudo apt install --no-install-recommends python3-venv iproute2 unzip
cd ~/iliyas
unzip -o piper-teleop-slave.zip
cd piper-teleop-slave
bash scripts/install_runtime.sh slave
bash scripts/setup_can.sh can3
bash scripts/setup_can.sh can2
.venv/bin/python -m piper_wireless_teleop.dual_arm slave --dry-run
```

If ensurepip is missing on Ubuntu 22.04, install `python3.10-venv` and retry.

## Start receiving and commanding

Verify physical arm routing and SDK/firmware settings first. Place each
master/slave pair in similar poses and keep a slave power cutoff accessible.
From this directory, start Orin before the Pi master launcher:

```bash
.venv/bin/python -m piper_wireless_teleop.dual_arm slave --confirm MOVE
```

LEFT listens on UDP 5005 and commands can2; RIGHT listens on UDP 5006 and commands
can3. Startup waits for joint targets within 15 degrees of slave feedback, then
slowly aligns the slave. Gripper commands begin after initialization. No collision
avoidance or synchronized two-arm execution is provided.

Local joint clamps (degrees): J1 +/-150; J2 0..180; J3 -170..0; J4/J5 +/-89;
J6 +/-170. They do not change firmware settings or the SDK's own limits.
SDK source: https://github.com/agilexrobotics/pyAgxArm/blob/master/pyAgxArm/api/constants.py

## Troubleshooting

- Accepted packets: confirms software receipt/command calls, not physical movement.
- Targets change but motors do not: inspect slave enable state, mode, CAN errors,
  firmware compatibility and SDK limits. Do not assume increasing Wi-Fi rate fixes it.
- Initialization waits: check corresponding poses and live slave joint feedback.
- Timeout after stopping Pi: expected; no new commands are issued. Motors are not
  automatically disabled, and the last commanded target may still be active.
- LEFT moves the wrong slave: stop, trace adapters and correct dual_arm.yaml.
- CAN reset on exit uses sudo: run `sudo -v` in this terminal before motion to
  cache credentials; interrupted/failed cleanup can require manual CAN setup.

## System mapping

| Side | Pi master | Orin slave | UDP port |
| --- | --- | --- | --- |
| Left | can2 | can2 | 5005 |
| Right | can1 | can3 | 5006 |

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

## Remember USB adapters (recommended)

Stop teleop and physically trace left/right cables once. List the current adapters:

```bash
.venv/bin/python -m piper_wireless_teleop.can_identity list
```

Register using the CURRENT interface names (the example assumes the table above):

```bash
.venv/bin/python -m piper_wireless_teleop.can_identity register --role slave --left can2 --right can3

```

After reboot, resolve the adapters and configure their current CAN names:

```bash
.venv/bin/python -m piper_wireless_teleop.can_identity check --role slave
.venv/bin/python -m piper_wireless_teleop.can_identity setup --role slave

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

Registration lives in configs/can-identities-slave.json on THIS computer.
It survives ZIP extraction with unzip -o but is lost if you delete the deployment
folder. Back it up locally; do not copy it to the other host. No extra packages
or udev rules are required. Re-register after replacing an adapter, changing USB
topology for a port-bound device, or changing which arm its CAN cable connects to.
