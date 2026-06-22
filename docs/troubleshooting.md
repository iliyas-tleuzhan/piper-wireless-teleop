# Troubleshooting

## `can0` Not Found

Run `ip link` and confirm the CAN adapter appears. Check drivers, USB
connection, and adapter power. Use the correct interface name if it is not
`can0`.

## `candump can0` Shows Nothing

Check CAN-H/CAN-L wiring, termination, bitrate `1000000`, Piper power, and that
the arm is connected to the correct computer.

## UDP Packets Not Arriving

Verify the Computer 2 IP address, subnet, firewall rules, and UDP port `5005`.
Use `scripts/test_udp.py` before involving either robot.

## Slave Not Moving

Confirm the slave command includes `--confirm MOVE`, the master command includes
`--deadman`, `piper_sdk` is installed, CAN is configured, and the slave is not
printing receiver-timeout or deadman warnings.

## Packets Arrive, Gripper Moves, Joints Do Not

Symptom: packets arrive, `target_deg` and `cmd_deg` change, and the gripper
moves, but the slave joints do not move.

Likely cause: the slave Piper controller may be stuck in a stale
hold/control/motion-mode state. `GripperCtrl()` can still work while
`JointCtrl()` is ignored.

Recovery:

1. Stop `slave_receiver.py`.
2. Run `PYTHONPATH=. python slave_release.py`.
3. Restart `slave_receiver.py`.
4. If joints still do not move, fully power-cycle/unplug/replug the slave Piper
   arm.
5. Bring `can0` back up if needed.
6. Run `PYTHONPATH=. python scripts/test_slave_small_move.py --can can0 --confirm MOVE`.
7. Then run full teleop again.

## Slave Movement Delayed

Disable verbose packet logging, check Wi-Fi quality, reduce network congestion,
and verify both computers have stable CPU load. The master sends continuously at
the configured rate, so long delays usually come from network or robot-side SDK
latency.

## Slave Holds Position After Movement

This can be normal if the latest master target stops changing. The master sender
continues sending the latest target at a fixed rate so the slave holds the most
recent commanded pose.

## Receiver Timeout Warnings

If the slave prints `No valid packets ... holding last command`, valid UDP
packets are not arriving before `network.receiver_timeout_s`. Check the target
IP address, firewall, Wi-Fi quality, subnet, UDP port `5005`, and whether
packets are malformed or missing `deadman=true`.

This warning is no longer caused by Computer 1 and Computer 2 wall clocks being
different. Sender timestamps are not used for safety-critical packet rejection.
NTP is still useful for log comparison, but it is not required for teleoperation
timeout behavior.

If older logs reported a negative stale-packet age, that was the old
cross-computer timestamp bug. Negative packet age is no longer treated as an
error.

## Duplicate or Out-of-Order Packets

The slave ignores packets whose `seq` is less than or equal to the last accepted
sequence number. If dropped packet counts rise, inspect Wi-Fi quality, network
load, and whether multiple master senders are accidentally targeting the same
slave receiver.

## Slave Barely Moves

Slew limiting is disabled by default. If the slave still barely moves, check
whether your config explicitly sets `safety.enable_slew_limit: true`, whether
the master is sending changing joint targets, and whether `deadman=true` packets
are being accepted.

Also check the local hard bounds in `piper_wireless_teleop/safety.py`. The
default joint limits use the wider Piper motion envelope for normal teleop while
keeping simple hard stops.

## Wrong IP Address

Run `ip addr` on Computer 2 and use that address in Computer 1's
`--target-ip`.

## Firewall or Network Issues

Allow UDP port `5005` or temporarily test on an isolated network. Avoid guest
Wi-Fi networks that block client-to-client traffic.

## Master and Slave on Same CAN Bus

Stop immediately and rewire. Wireless mode requires separate CAN buses:
Computer 1 to master only, Computer 2 to slave only.
