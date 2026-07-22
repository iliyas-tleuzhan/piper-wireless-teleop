# Architecture

## Direct Same-Bus Teleoperation

The original direct Piper teleoperation method places both arms on the same CAN
bus. The master emits Piper command frames and the slave can receive matching
targets directly.

That wiring is not used here. In wireless mode, the two Piper arms must be on
separate CAN buses.

## Wireless Bridge Replacement

This repository replaces the shared CAN bus with a software bridge:

```text
Master PiPER-X -> Computer 1 CAN -> decoded targets -> UDP -> Computer 2 -> pyAgxArm -> Slave PiPER-X
```

Computer 1 reads PiPER-X leader joint feedback through pyAgxArm. For the legacy
standard PiPER profile, it can still decode the relevant Piper command IDs:

- `0x151`: mode/control frame.
- `0x155`: joint 1 and joint 2 targets.
- `0x156`: joint 3 and joint 4 targets.
- `0x157`: joint 5 and joint 6 targets.
- `0x159`: gripper command.

Computer 2 receives UDP packets, validates them, applies deadman and sequence
ordering checks, tracks receiver-side monotonic timeout state, and immediately
calls the configured arm adapter. The PiPER-X adapter uses pyAgxArm
`move_js()` for continuous joint target streaming and AGX gripper
`move_gripper_m()` for received gripper width/force commands.

## Why Send Decoded Joint Targets

The bridge sends decoded joint targets instead of trying to make CAN physically
wireless. This keeps the CAN buses local and deterministic, makes UDP packets
readable during bring-up, and lets the slave side add robot-specific safety
logic before commanding motion.
