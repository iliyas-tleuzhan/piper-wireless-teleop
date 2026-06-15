# Safety

Keep an E-stop or power cutoff nearby whenever the slave arm can move.

Start with the master and slave arms in similar poses. The slave receiver uses a
slew limiter, but it is not a substitute for safe initial positioning.

Do not run direct same-CAN-bus master/slave teleoperation and wireless teleop at
the same time. In wireless mode, the master and slave must not share a CAN bus.

## Deadman

The slave ignores packets where `deadman=false`. The normal master command uses
`--deadman` so the operator makes an explicit choice to send active motion
targets.

## Stale Packets

The slave ignores packets older than `network.max_packet_age_s`. This prevents
old UDP packets from commanding the robot after a network interruption.

## Slew Limiting

The slave does not freeze on large target jumps. Instead, it moves from the last
commanded joint target toward the new target by at most `safety.max_step_deg` per
cycle. This keeps motion continuous while preventing a single packet from
causing a large step command.
