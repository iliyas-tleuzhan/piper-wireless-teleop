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
printing stale packet or deadman warnings.

## Slave Movement Delayed

Disable verbose packet logging, check Wi-Fi quality, reduce network congestion,
and verify both computers have stable CPU load. The master sends continuously at
the configured rate, so long delays usually come from network or robot-side SDK
latency.

## Slave Holds Position After Movement

This can be normal if the latest master target stops changing. The master sender
continues sending the latest target at a fixed rate so the slave holds the most
recent commanded pose.

## Packet Stale Warnings

Check clock behavior, network latency, Wi-Fi drops, and whether packets are being
queued by a firewall or VPN. The default max packet age is `0.25 s`.

## Wrong IP Address

Run `ip addr` on Computer 2 and use that address in Computer 1's
`--target-ip`.

## Firewall or Network Issues

Allow UDP port `5005` or temporarily test on an isolated network. Avoid guest
Wi-Fi networks that block client-to-client traffic.

## Master and Slave on Same CAN Bus

Stop immediately and rewire. Wireless mode requires separate CAN buses:
Computer 1 to master only, Computer 2 to slave only.
