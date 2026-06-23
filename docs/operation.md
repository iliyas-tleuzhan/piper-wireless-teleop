# Operation

## Startup Order

1. Wire Computer 1 only to the master Piper.
2. Wire Computer 2 only to the slave Piper.
3. Power-cycle the slave Piper fresh before important tests.
4. Configure CAN on both computers and check `can0`.
5. Run a slave small-move test.
6. Start the slave receiver on Computer 2.
7. Start the master sender on Computer 1.
8. Move slowly first.

## Computer 2: Slave Receiver

```bash
PYTHONPATH=. python scripts/slave_receiver.py --can can0 --bind-ip 0.0.0.0 --confirm MOVE
```

`--init-mode align` is the default. Startup is intentionally interactive:

1. The receiver connects to the slave Piper, enables it, and sets the configured
   joint control/high-follow mode.
2. It prompts: `Move both master and slave arms to the same safe visual starting
   pose. Press Enter when ready.`
3. After Enter, it silently reads the current master target and about 0.5 seconds of
   stable slave feedback from `GetArmJointMsgs()`, discarding initial/default
   all-zero feedback frames.
4. Any joint more than 15 degrees apart is printed, rejected, and the prompt
   repeats.
5. If the check passes, it slowly moves the slave from its feedback pose to
   `master_start` using small 0.3 degree steps every 20 ms.
6. Normal absolute teleop starts after the slave is close to `master_start`.

Visual alignment is the human check that both arms look like they are in the
same safe pose. CAN/raw alignment is the numeric check that master target values
and slave feedback values, both in Piper 0.001 degree units, differ by no more
than 15 degrees per joint.

Optional overrides:

```bash
PYTHONPATH=. python scripts/slave_receiver.py --config configs/default.yaml --bind-ip 0.0.0.0 --udp-port 5005 --can can0 --confirm MOVE
```

Startup mode overrides:

```bash
# No startup correction. Teleop uses slave_start + (master_current - master_start).
PYTHONPATH=. python scripts/slave_receiver.py --can can0 --confirm MOVE --init-mode offset

# Old direct startup behavior. This can jump if the arms are not already aligned.
PYTHONPATH=. python scripts/slave_receiver.py --can can0 --confirm MOVE --init-mode none
```

## Computer 1: Master Sender

```bash
PYTHONPATH=. python scripts/master_sender.py --can can0 --target-ip <COMPUTER_2_IP> --deadman
```

Optional overrides:

```bash
PYTHONPATH=. python scripts/master_sender.py --config configs/default.yaml --can can0 --target-ip <COMPUTER_2_IP> --target-port 5005 --deadman
```

The slave receiver uses Computer 2's local `time.monotonic()` receive time for
timeout safety. The sender timestamp is kept only for debugging, so the two
computers do not need synchronized wall clocks to avoid false stale-packet
rejection.

After startup initialization, accepted packets are commanded directly to the
slave by default. Slew limiting is disabled by default because it made wireless
motion much slower than wired Piper master-slave teleoperation.

## Test UDP Before Moving

Computer 2:

```bash
PYTHONPATH=. python scripts/test_udp.py receiver --bind-ip 0.0.0.0 --port 5005
```

Computer 1:

```bash
PYTHONPATH=. python scripts/test_udp.py sender --target-ip <COMPUTER_2_IP> --port 5005
```

## Test CAN

On each computer:

```bash
./scripts/setup_can.sh can0 1000000
candump can0
```

Use `scripts/decode_master_can.py` on Computer 1 to decode master Piper command
frames without sending UDP.
