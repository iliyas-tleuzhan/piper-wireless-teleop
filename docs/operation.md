# Operation

## Startup Order

1. Wire Computer 1 only to the master Piper.
2. Wire Computer 2 only to the slave Piper.
3. Configure CAN on both computers.
4. Start the slave receiver on Computer 2.
5. Start the master sender on Computer 1.

## Computer 2: Slave Receiver

```bash
PYTHONPATH=. python scripts/slave_receiver.py --can can0 --confirm MOVE
```

Optional overrides:

```bash
PYTHONPATH=. python scripts/slave_receiver.py --config configs/default.yaml --bind-ip 0.0.0.0 --udp-port 5005 --can can0 --confirm MOVE
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

Accepted packets are commanded directly to the slave by default. Slew limiting
is disabled by default because it made wireless motion much slower than wired
Piper master-slave teleoperation.

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
