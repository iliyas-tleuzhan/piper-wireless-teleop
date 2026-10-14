"""Check routing validation, real UDP isolation and worker shutdown."""
import argparse
import importlib.util
from pathlib import Path
import sys
import os
import zipfile
import pytest
import yaml
from piper_wireless_teleop.dual_arm import ROOT, build_commands, load_routes, main, supervise
from piper_wireless_teleop.udp_transport import UdpReceiver, UdpSender


def test_defaults_and_commands():
    routes = load_routes(ROOT / "configs/dual_arm.yaml")
    args = argparse.Namespace(role="slave", config=str(ROOT / "configs/default.yaml"),
                              bind_ip="0.0.0.0", confirm="MOVE", init_mode="align")
    commands = build_commands(args, routes)
    assert commands["left"][commands["left"].index("--can") + 1] == "can3"
    assert commands["right"][commands["right"].index("--can") + 1] == "can2"
    assert commands["left"][commands["left"].index("--udp-port") + 1] == "5005"
    assert commands["right"][commands["right"].index("--udp-port") + 1] == "5006"


@pytest.mark.parametrize("key", ["master_can", "slave_can", "udp_port"])
def test_duplicate_routing_rejected(tmp_path, key):
    routes = load_routes(ROOT / "configs/dual_arm.yaml")
    routes["right"][key] = routes["left"][key]
    path = tmp_path / "routes.yaml"
    path.write_text(yaml.safe_dump({"arms": routes}))
    with pytest.raises(ValueError, match="different"):
        load_routes(path)


def test_slave_requires_confirmation():
    with pytest.raises(SystemExit) as exc:
        main(["slave"])
    assert exc.value.code == 2
    assert main(["slave", "--dry-run"]) == 0


def test_udp_pairs_do_not_cross_route():
    left = UdpReceiver("127.0.0.1", 0, 0.05)
    right = UdpReceiver("127.0.0.1", 0, 0.05)
    sender_left = UdpSender("127.0.0.1", left._socket.getsockname()[1])
    sender_right = UdpSender("127.0.0.1", right._socket.getsockname()[1])
    try:
        sender_left.send(b"left")
        assert left.recv()[0] == b"left"
        assert right.recv() is None
        sender_right.send(b"right")
        assert right.recv()[0] == b"right"
        assert left.recv() is None
    finally:
        for obj in (left, right, sender_left, sender_right):
            obj.close()


@pytest.mark.skipif(os.name != "posix", reason="SIGINT cleanup requires Linux deployment")
def test_worker_exit_stops_sibling(tmp_path):
    marker = tmp_path / "stopped"
    code = ("import signal,time,pathlib; "
            f"signal.signal(signal.SIGINT, lambda *a: (pathlib.Path({str(marker)!r}).write_text('yes'), exit(0))); "
            "time.sleep(30)")
    result = supervise({"left": [sys.executable, "-c", code],
                        "right": [sys.executable, "-c", "import time; time.sleep(1); exit(3)"]})
    assert result == 3
    assert marker.read_text() == "yes"


def test_role_bundles_exclude_development_and_other_worker(tmp_path):
    spec = importlib.util.spec_from_file_location("bundle", ROOT / "scripts/build_runtime_bundle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for role in ("master", "slave"):
        with zipfile.ZipFile(module.build_bundle(role, tmp_path)) as bundle:
            names = bundle.namelist()
            assert not any("tests/" in name or "arduino/" in name or "/.git/" in name for name in names)
            worker = "master_sender.py" if role == "master" else "slave_receiver.py"
            other = "slave_receiver.py" if role == "master" else "master_sender.py"
            assert any(name.endswith(worker) for name in names)
            assert not any(name.endswith(other) for name in names)


def test_master_commands_keep_separate_routes():
    routes = load_routes(ROOT / "configs/dual_arm.yaml")
    args = argparse.Namespace(role="master", config=str(ROOT / "configs/default.yaml"),
                              target_ip="192.0.2.10", deadman=True)
    commands = build_commands(args, routes)
    for label, port in (("left", "5005"), ("right", "5006")):
        cmd = commands[label]
        assert cmd[cmd.index("--target-port") + 1] == port
        assert cmd[cmd.index("--can") + 1] == routes[label]["master_can"]
        assert "--deadman" in cmd


def test_worker_failure_terminates_other_worker():
    assert supervise({"left": [sys.executable, "-c", "import time; time.sleep(30)"],
                      "right": [sys.executable, "-c", "exit(4)"]}) == 4


def test_bundle_normalizes_windows_shell_line_endings(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("bundle_crlf", ROOT / "scripts/build_runtime_bundle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / "source"
    import shutil
    shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns(".git", "dist", "__pycache__", ".pytest_cache"))
    script = source / "scripts/install_runtime.sh"
    script.write_bytes(script.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    monkeypatch.setattr(module, "ROOT", source)
    with zipfile.ZipFile(module.build_bundle("slave", tmp_path / "output")) as bundle:
        payload = bundle.read("piper-teleop-slave/scripts/install_runtime.sh")
        assert b"\r" not in payload
        assert b"set -euo pipefail\n" in payload


@pytest.mark.parametrize("role", ["master", "slave"])
def test_extracted_bundle_worker_imports_without_checkout(tmp_path, role):
    """Worker --help exercises imports without connecting to hardware."""
    import subprocess
    spec = importlib.util.spec_from_file_location("bundle_imports", ROOT / "scripts/build_runtime_bundle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with zipfile.ZipFile(module.build_bundle(role, tmp_path)) as bundle:
        bundle.extractall(tmp_path / "extract")
    root = tmp_path / "extract" / f"piper-teleop-{role}"
    env = dict(os.environ)
    # Preserve installed test dependencies, but remove the source checkout.
    paths = [entry for entry in env.get("PYTHONPATH", "").split(os.pathsep)
             if entry and Path(entry).resolve() != ROOT]
    env["PYTHONPATH"] = os.pathsep.join([str(root), *paths])
    worker = "master_sender.py" if role == "master" else "slave_receiver.py"
    result = subprocess.run([sys.executable, str(root / "scripts" / worker), "--help"],
                            cwd=root, env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout


def test_supervisor_isolates_workers_from_terminal_signals(monkeypatch):
    import piper_wireless_teleop.dual_arm as dual
    import io
    class Worker:
        def __init__(self): self.stdout = io.StringIO()
        def poll(self): return 2
        def wait(self, timeout=None): return 2
    calls = []
    def spawn(*args, **kwargs):
        calls.append(kwargs)
        return Worker()
    monkeypatch.setattr(dual.subprocess, "Popen", spawn)
    assert dual.supervise({"left": ["worker"], "right": ["worker"]}) == 2
    assert len(calls) == 2
    assert all(call["start_new_session"] == (os.name == "posix") for call in calls)
