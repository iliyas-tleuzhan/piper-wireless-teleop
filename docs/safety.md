# Safety

Keep an E-stop or power cutoff nearby whenever the slave arm can move.

Start with the master and slave arms in similar poses. By default the receiver
uses `--init-mode align`, so it does not command the slave to the master pose as
soon as teleop starts.

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
computers, but it is not required for teleoperation timeout safety. A negative
computed packet age is not a safety error.

## Sequence Numbers

The slave uses `seq` to ignore duplicate or out-of-order UDP packets and to
count dropped packets. Sequence numbers are not used to estimate elapsed time.

## Startup Alignment

`--init-mode align` is the default startup mode. The receiver first connects to
and enables the slave Piper using the same joint control/high-follow setup as
normal teleop. It then waits for a valid master packet but does not command the
slave yet.

The operator must visually place the master and slave arms in the same safe
starting pose and press Enter. The receiver then compares the latest master
joint target with stable slave feedback from `GetArmJointMsgs()`. Both values
are official Piper raw joint units of 0.001 degrees. Initial/default all-zero
feedback frames are discarded before the comparison.

Visual alignment is the human pose check. CAN/raw alignment is the numeric
check. Every joint must be within 15 degrees. If any joint is farther away, the
receiver prints the joint number and the difference, and asks the operator to
adjust both arms again.

When the numeric check passes, the slave still does not move automatically. The
operator presses Enter; then only the slave arm is slowly corrected from its
current feedback pose to the confirmed `master_start` pose using 0.3 degree
steps every 20 ms. Ctrl+C stops the process, and the alignment motion times out
after 10 seconds. Gripper commands are not sent until normal teleop starts.

`--init-mode offset` is a fallback that avoids startup correction. It records
`master_start` and `slave_start`, then commands
`slave_start + (master_current - master_start)` during teleop. `--init-mode none`
keeps the old direct startup behavior and prints a warning because the slave can
jump if the two arms are not already aligned.

## Normal Teleop Motion

After startup initialization, the slave does not reject or slow down a normal
target just because it differs from the previous target. The default path sends
the latest valid target to `JointCtrl()` immediately.

The checked-in hard bounds are intentionally simple and wide enough for normal
Piper master-slave teleop: J1 `-154..154`, J2 `0..195`, J3 `-175..0`, J4
`-106..106`, J5 `-75..75`, and J6 `-100..100` degrees. These are local clamps
before sending the existing direct `JointCtrl()` command.

An optional hidden fallback can be enabled with `safety.enable_slew_limit: true`
and `safety.max_step_deg`, but the default is `false` because always limiting
steps made the robot barely move during normal wireless teleop.
