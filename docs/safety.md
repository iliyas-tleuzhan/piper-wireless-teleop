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
normal teleop. It does not command the slave while the operator is positioning
the arms.

The operator must visually place the master and slave arms in the same safe
starting pose. The receiver silently compares the current master joint target
with stable slave feedback from `GetArmJointMsgs()`. The master target is
sampled in short windows so queued UDP packets are skipped. Both values are
official Piper raw joint units of 0.001 degrees. Initial/default all-zero
feedback frames are discarded before the comparison.

Visual alignment is the human pose check. CAN/raw alignment is the numeric
check. Every joint must be within 15 degrees. If any joint is farther away, the
receiver stays in initialization and keeps checking silently.

When the numeric check passes, only the slave arm is slowly corrected from its
current feedback pose to the sampled current master pose using 0.3 degree
steps every 20 ms. Ctrl+C stops the process, and the alignment motion times out
after 10 seconds. Gripper commands are not sent until normal teleop starts.

`--init-mode offset` is a fallback that avoids startup correction. It records
the sampled current master and slave poses, then commands
`slave_init_current + (master_current - master_init_current)` during teleop.
`--init-mode none` still performs the same current master/current slave check,
then skips the slow correction and starts normal absolute teleop from the
checked pose.

## Normal Teleop Motion

After startup initialization, the slave does not reject or slow down a normal
target just because it differs from the previous target. The default path sends
the latest valid target to `JointCtrl()` immediately.

The checked-in hard bounds use the official Piper-X SDK presets:
J1 `-150..150`, J2 `0..180`, J3 `-170..0`, J4 `-89..89`,
J5 `-89..89`, and J6 `-170..170` degrees. These are local clamps
before sending `JointCtrl()`; they do not write persistent firmware settings.
Source: [AgileX pyAgxArm model presets](https://github.com/agilexrobotics/pyAgxArm/blob/master/pyAgxArm/api/constants.py).

The receiver still uses `piper_sdk.C_PiperInterface_V2`. Updating these clamps
is not an SDK migration or hardware compatibility certification. Installed SDK
limits and the arm's firmware limits can further restrict commands. Verify both
before motion; do not disable their limits merely to match this preset.

An optional hidden fallback can be enabled with `safety.enable_slew_limit: true`
and `safety.max_step_deg`, but the default is `false` because always limiting
steps made the robot barely move during normal wireless teleop.
