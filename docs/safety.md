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

## Receiver Timeout

Older code compared the sender wall-clock packet timestamp against Computer 2's
wall clock. That can falsely reject fresh packets when the two computers are not
clock-synchronized.

The slave now uses receiver-side `time.monotonic()` for timeout safety. When a
valid UDP packet arrives, Computer 2 records the local monotonic receive time. If
no valid packet arrives for `network.receiver_timeout_s`, the slave holds the
last command and prints a rate-limited warning.

The sender timestamp remains in the packet only for debugging and log
correlation. NTP clock sync is still useful for comparing logs between
computers, but it is not required for teleoperation timeout safety.

## Sequence Numbers

The slave uses `seq` to ignore duplicate or out-of-order UDP packets and to
count dropped packets. Sequence numbers are not used to estimate elapsed time.

## Slew Limiting

The slave does not freeze on large target jumps. Instead, it moves from the last
commanded joint target toward the new target by at most `safety.max_step_deg` per
cycle. This keeps motion continuous while preventing a single packet from
causing a large step command.
