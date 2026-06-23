# Scripts

## `scripts/setup_can.sh`

Runs on either computer. Configures a SocketCAN interface.

Moves robot: no.

```bash
./scripts/setup_can.sh can0 1000000
```

## `scripts/master_sender.py`

Runs on Computer 1. Reads master Piper CAN command frames and sends decoded UDP
packets continuously at the configured rate.

Moves robot: no, but it sends motion targets.

```bash
PYTHONPATH=. python scripts/master_sender.py --can can0 --target-ip <COMPUTER_2_IP> --deadman
```

## `scripts/slave_receiver.py`

Runs on Computer 2. Receives UDP packets, validates them, and commands the latest
valid target through `piper_sdk` after startup initialization.

Moves robot: yes. Requires `--confirm MOVE`.

```bash
PYTHONPATH=. python scripts/slave_receiver.py --can can0 --confirm MOVE
```

Default startup mode is `--init-mode align`. It waits for a valid master packet,
prompts the operator to place both arms in the same safe visual starting pose,
prints master/slave raw and degree starts, rejects any joint more than 8 degrees
apart, and only slowly moves the slave to the master start pose after the
operator types `ALIGN`. The gripper is ignored until teleop starts.

Other modes:

```bash
PYTHONPATH=. python scripts/slave_receiver.py --can can0 --confirm MOVE --init-mode offset
PYTHONPATH=. python scripts/slave_receiver.py --can can0 --confirm MOVE --init-mode none
```

`offset` records the startup poses and commands
`slave_start + (master_current - master_start)`. `none` is the old direct
behavior and can jump at startup.

## `scripts/no_gripper_master.py`

Runs on Computer 1. Reads master Piper joint command frames and sends UDP
packets without gripper targets.

Moves robot: no, but it sends motion targets.

```bash
PYTHONPATH=. python scripts/no_gripper_master.py --can can0 --target-ip <COMPUTER_2_IP> --deadman
```

## `scripts/no_gripper_slave.py`

Runs on Computer 2. Receives UDP packets and commands only the slave arm joints;
incoming or absent gripper targets are ignored.

Moves robot: yes. Requires `--confirm MOVE`.

```bash
PYTHONPATH=. python scripts/no_gripper_slave.py --can can0 --confirm MOVE
```

This script uses the same default `--init-mode align` startup as
`scripts/slave_receiver.py`: it waits for a valid master packet, checks
master/slave startup pose differences against the 8 degree threshold, and only
slowly corrects the slave after the operator types `ALIGN`. `--init-mode offset`
and `--init-mode none` are also available.

## `scripts/decode_master_can.py`

Runs on Computer 1. Prints decoded master joint and gripper command frames.

Moves robot: no.

```bash
PYTHONPATH=. python scripts/decode_master_can.py --can can0
```

## `scripts/read_slave_state.py`

Runs on Computer 2. Connects to the slave Piper and prints SDK feedback.

Moves robot: no.

```bash
PYTHONPATH=. python scripts/read_slave_state.py --can can0
```

## `scripts/test_slave_small_move.py`

Runs on Computer 2. Hardware validation that enables the arm and moves joint 6
by 1 degree slowly.

Moves robot: yes. Requires `--confirm MOVE`.

```bash
PYTHONPATH=. python scripts/test_slave_small_move.py --can can0 --confirm MOVE
```

## `scripts/test_udp.py`

Runs on either computer. Tests UDP transport without Piper hardware.

Moves robot: no.

```bash
PYTHONPATH=. python scripts/test_udp.py receiver --bind-ip 0.0.0.0 --port 5005
PYTHONPATH=. python scripts/test_udp.py sender --target-ip <COMPUTER_2_IP> --port 5005
```
