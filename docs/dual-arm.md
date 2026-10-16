# Dual Piper-X Wi-Fi teleoperation

Linus (Jetson master computer): two master CAN buses. Orin: two slave CAN buses.
Left uses UDP 5005; right uses UDP 5006. Slave defaults: left can2, right can3.
Master defaults: left can2, right can1. Edit configs/dual_arm.yaml
on each device to match the physical adapters. Each arm needs a separate CAN bus.
Do not connect two arms with overlapping CAN IDs to the same bus. Verify adapter
mapping after reboot/replug; numbering alone does not establish physical identity.

## Build and transfer only the necessary files
On the laptop, from the repository checkout:

```bash
python scripts/build_runtime_bundle.py
ssh <LINUS_USER>@<LINUS_IP> "mkdir -p ~/iliyas"
scp bundles/piper-teleop-master.zip <LINUS_USER>@<LINUS_IP>:~/iliyas/
ssh dase-orin@192.168.1.144 "mkdir -p ~/iliyas"
scp bundles/piper-teleop-slave.zip dase-orin@192.168.1.144:~/iliyas/
```

Orin uses the current address above; fill in Linus SSH details and adjust if the network changes. Bundles exclude Git history, tests, Arduino/LoRa,
chassis code, and development utilities. They contain only the selected worker,
its runtime modules, configuration, setup scripts and this guide.

On each device install the OS prerequisites once (skip those already installed):

```bash
sudo apt update
sudo apt install --no-install-recommends python3-venv iproute2 unzip
```

On Linus:

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
bash scripts/setup_can.sh can2
bash scripts/setup_can.sh can3
.venv/bin/python -m piper_wireless_teleop.dual_arm slave --dry-run
```

These use the native python3 on each machine, avoiding Conda and a forced Python
3.11 installation. Linus installs python-can and PyYAML; Orin installs piper_sdk
and PyYAML. pip installs any dependencies those packages require. Compatibility
of the selected SDK with each device's Python and Piper-X firmware must be
verified on hardware. Optional CAN diagnostics: install can-utils if needed.

## Start both pairs
First physically align each master with its corresponding slave and verify
Piper-X joint limits and firmware mode settings against the existing config/code.
Keep the slave power cutoff accessible. Start on Orin:

```bash
.venv/bin/python -m piper_wireless_teleop.dual_arm slave --confirm MOVE
```

Then on Linus:

```bash
.venv/bin/python -m piper_wireless_teleop.dual_arm master --target-ip 192.168.1.144 --deadman
```

The slave workers retain existing alignment startup. Logs are labeled LEFT/RIGHT.
Ctrl+C or SIGTERM stops both workers and invokes their existing cleanup. A worker
exit stops its sibling on the same computer. No automatic restart is performed.
The existing deadman flag is a constant packet flag, not a physical hold-to-run
switch. On UDP loss each receiver independently stops issuing new commands and
reports holding the last command. This is not a paired hardware E-stop, nor a
cross-computer shutdown system. The launcher does not coordinate startup of both
arms, detect collisions, control Bunker Mini, or synchronize joint execution.
Both UDP ports must be reachable through any enabled firewall.

## Validate before full operation
Test each pair alone using the existing single-arm scripts, then both streams.
Verify left motion/gripper affects only left and right affects only right.
Disconnect one CAN source and one network stream; check actual arm behavior.
The existing master sender republishes its last decoded complete target, so
fresh UDP alone does not prove fresh master CAN input. Verify this limitation
before relying on network timeout as a source-loss safeguard.
Hardware tests must verify Piper-X command-frame output and SDK compatibility.

Development on the laptop: pip install -r requirements-dev.txt; python -m pytest.
Make changes on dual-piper-teleop. Never commit/merge main without instruction.
Rebuild and transfer bundles after updating. Current dependencies are not pinned;
record tested versions on the devices before a reproducible deployment release.

## Piper-X joint profile
Local receiver clamps now use AgileX's Piper-X presets: J1 +/-150, J2 0..180,
J3 -170..0, J4/J5 +/-89, J6 +/-170 degrees. These do not write firmware limits.
The existing piper_sdk backend is retained; SDK/firmware compatibility remains
subject to device checks. No MIT/CPV joint sign correction is applied to this
JointCtrl position-command path. See the official model presets:
https://github.com/agilexrobotics/pyAgxArm/blob/master/pyAgxArm/api/constants.py

## Update an existing deployment
Stop teleop on both machines before transferring and extracting updated ZIPs.
Extract with `unzip -o` into ~/iliyas to preserve the existing .venv. Review
configs/dual_arm.yaml afterwards: extracting overwrites configuration edits.
Rerun install_runtime.sh only when dependencies change. Numbered CAN names can
swap after reboot; always verify physical left/right assignment before motion.

## Stable adapter registration

Each bundle README describes `python -m piper_wireless_teleop.can_identity`.
Use `list`, then `register --role master|slave --left <current interface>
--right <current interface>` after physically identifying cables. After reboot,
use `check --role ...` and `setup --role ...`; the launcher resolves registered
serials/USB paths automatically. Registration is local and is excluded from ZIPs
and Git. Without registration the existing YAML CAN defaults still apply.
Registration prevents interface-number swaps; it cannot detect swapped CAN cables
or identify an arm's handedness. Preserve the registration JSON when updating.

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
