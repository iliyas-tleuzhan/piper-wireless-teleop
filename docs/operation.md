# Operation

## Startup Order

1. Wire Computer 1 only to the master Piper.
2. Wire Computer 2 only to the slave Piper.
3. Configure CAN on both computers.
4. Start the slave receiver on Computer 2.
5. Start the master sender on Computer 1.

## Computer 2: Slave Receiver

```bash
python scripts/slave_receiver.py --can can0 --confirm MOVE
```

Optional overrides:

```bash
python scripts/slave_receiver.py --config configs/default.yaml --bind-ip 0.0.0.0 --udp-port 5005 --can can0 --confirm MOVE
```

## Computer 1: Master Sender

```bash
python scripts/master_sender.py --target-ip <COMPUTER_2_IP> --can can0 --deadman
```

Optional overrides:

```bash
python scripts/master_sender.py --config configs/default.yaml --target-ip <COMPUTER_2_IP> --target-port 5005 --can can0 --deadman
```

## Test UDP Before Moving

Computer 2:

```bash
python scripts/test_udp.py receiver --bind-ip 0.0.0.0 --port 5005
```

Computer 1:

```bash
python scripts/test_udp.py sender --target-ip <COMPUTER_2_IP> --port 5005
```

## Test CAN

On each computer:

```bash
./scripts/setup_can.sh can0 1000000
candump can0
```

Use `scripts/decode_master_can.py` on Computer 1 to decode master Piper command
frames without sending UDP.
