#!/usr/bin/env bash
set -euo pipefail

# tmux session name. Existing sessions with this name are replaced.
SESSION="piper-teleop"

# Computer 2 SSH target.
COMPUTER2_USER="dase_iot"
COMPUTER2_IP="192.168.50.1"

# Repository paths on Computer 1 and Computer 2.
LOCAL_REPO="$HOME/Iliyas/piper-wireless-teleop-main"
REMOTE_REPO="$HOME/Iliyas/piper-wireless-teleop-main"

# Conda environment used by both sides.
CONDA_ENV="piper-wireless-teleop"

# CAN interfaces on Computer 1 and Computer 2.
LOCAL_CAN="can0"
REMOTE_CAN="can0"

# UDP target for master_sender.py. By default this is Computer 2.
UDP_TARGET_IP="$COMPUTER2_IP"

# Computer 2 must have an SSH server running:
#   sudo apt install -y openssh-server
#   sudo systemctl enable --now ssh

# Check required local command-line tools before creating the session.
if ! command -v tmux >/dev/null 2>&1; then
    echo "tmux is not installed. Run: sudo apt install -y tmux"
    exit 1
fi

if ! command -v ssh >/dev/null 2>&1; then
    echo "ssh is not installed. Run: sudo apt install -y openssh-client"
    exit 1
fi

# Quote a value so it can be safely inserted into a bash command string.
shell_quote() {
    printf "%q" "$1"
}

# Build the Computer 2 command locally so the editable variables above are
# expanded before ssh starts the remote shell.
REMOTE_CMD="cd $(shell_quote "$REMOTE_REPO") && source ~/miniconda3/etc/profile.d/conda.sh && conda activate $(shell_quote "$CONDA_ENV") && PYTHONPATH=. python scripts/slave_receiver.py --can $(shell_quote "$REMOTE_CAN") --bind-ip 0.0.0.0 --confirm MOVE"
LEFT_CMD="ssh -t $(shell_quote "${COMPUTER2_USER}@${COMPUTER2_IP}") $(shell_quote "$REMOTE_CMD")"

# Build the Computer 1 command. It waits for Enter so the slave receiver can be
# confirmed ready before master_sender.py starts sending UDP packets.
RIGHT_CMD="cd $(shell_quote "$LOCAL_REPO") && source ~/miniconda3/etc/profile.d/conda.sh && conda activate $(shell_quote "$CONDA_ENV") && echo 'Wait until slave_receiver is ready, then press Enter to start master_sender...' && read -r && PYTHONPATH=. python scripts/master_sender.py --can $(shell_quote "$LOCAL_CAN") --target-ip $(shell_quote "$UDP_TARGET_IP") --deadman"

# Replace any previous teleop tmux session with a clean one.
tmux kill-session -t "$SESSION" 2>/dev/null || true

# Create a new side-by-side tmux session:
#   left pane  = Computer 2 slave_receiver.py over SSH
#   right pane = local Computer 1 master_sender.py
tmux new-session -d -s "$SESSION" "bash -lc $(shell_quote "$LEFT_CMD")"
tmux split-window -h -t "$SESSION" "bash -lc $(shell_quote "$RIGHT_CMD")"
tmux select-pane -t "$SESSION:0.0"

# Attach the terminal to the new teleop session.
tmux attach-session -t "$SESSION"
