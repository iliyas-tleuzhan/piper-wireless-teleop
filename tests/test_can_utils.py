"""Tests for SocketCAN maintenance helpers."""

from __future__ import annotations

import subprocess

from piper_wireless_teleop.can_utils import reset_can_interface


def test_reset_can_interface_runs_standard_command_sequence(monkeypatch) -> None:
    """CAN reset matches scripts/setup_can.sh behavior."""

    calls: list[list[str]] = []

    def fake_run(command: list[str], check: bool) -> None:
        calls.append(command)
        assert check is True

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert reset_can_interface("can0", 1000000) is True
    assert calls == [
        ["sudo", "ip", "link", "set", "can0", "down"],
        [
            "sudo",
            "ip",
            "link",
            "set",
            "can0",
            "type",
            "can",
            "bitrate",
            "1000000",
        ],
        ["sudo", "ip", "link", "set", "can0", "up"],
        ["ip", "-details", "link", "show", "can0"],
    ]


def test_reset_can_interface_returns_false_on_failure(monkeypatch) -> None:
    """Shutdown cleanup should warn but not crash if sudo/ip fails."""

    def fake_run(command: list[str], check: bool) -> None:
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert reset_can_interface("can0", 1000000) is False


def test_reset_can_interface_returns_false_when_command_is_missing(monkeypatch) -> None:
    """Missing sudo/ip should also be treated as a non-crashing reset failure."""

    def fake_run(command: list[str], check: bool) -> None:
        raise FileNotFoundError(command[0])

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert reset_can_interface("can0", 1000000) is False
