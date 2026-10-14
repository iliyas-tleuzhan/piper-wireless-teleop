"""Validated left/right routing and supervision of independent teleop workers."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_routes(path):
    with Path(path).open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    arms = data.get("arms") if isinstance(data, dict) else None
    if not isinstance(arms, dict) or set(arms) != {"left", "right"}:
        raise ValueError("arms must contain exactly left and right")
    for label, route in arms.items():
        if not isinstance(route, dict):
            raise ValueError(f"{label}: expected a mapping")
        for key in ("master_can", "slave_can"):
            value = route.get(key)
            if not isinstance(value, str) or not value or any(c.isspace() for c in value):
                raise ValueError(f"{label}: invalid {key}")
        port = route.get("udp_port")
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError(f"{label}: invalid udp_port")
    for key in ("master_can", "slave_can", "udp_port"):
        if arms["left"][key] == arms["right"][key]:
            raise ValueError(f"left and right must use different {key}")
    return arms


def build_commands(args, routes):
    commands = {}
    for label in ("left", "right"):
        route = routes[label]
        script = "master_sender.py" if args.role == "master" else "slave_receiver.py"
        cmd = [sys.executable, "-u", str(ROOT / "scripts" / script),
               "--config", str(Path(args.config).resolve()),
               "--can", route[f"{args.role}_can"]]
        if args.role == "master":
            cmd += ["--target-ip", args.target_ip, "--target-port", str(route["udp_port"])]
            if args.deadman:
                cmd += ["--deadman"]
        else:
            cmd += ["--bind-ip", args.bind_ip, "--udp-port", str(route["udp_port"]),
                    "--confirm", args.confirm, "--init-mode", args.init_mode]
        commands[label] = cmd
    return commands


def supervise(commands):
    workers = []
    readers = []
    stopping = threading.Event()
    def stop(_signum, _frame):
        stopping.set()
    previous = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        previous[sig] = signal.signal(sig, stop)
    def relay(label, stream):
        for line in stream:
            print(f"[{label.upper()}] {line.rstrip()}", flush=True)
        stream.close()
    try:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        for label, cmd in commands.items():
            if stopping.is_set():
                break
            worker = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, text=True,
                                      # Isolate Linux workers from terminal Ctrl+C;
                                      # the supervisor delivers one cleanup signal.
                                      start_new_session=(os.name == "posix"))
            workers.append(worker)
            reader = threading.Thread(target=relay, args=(label, worker.stdout), daemon=True)
            reader.start()
            readers.append(reader)
        while not stopping.wait(0.1):
            for worker in workers:
                code = worker.poll()
                if code is not None:
                    print("A teleop worker exited; stopping both workers.", flush=True)
                    return code if code != 0 else 1
        return 0
    finally:
        # SIGINT invokes the existing workers' cleanup (including slave CAN reset).
        for worker in workers:
            if worker.poll() is None:
                worker.send_signal(signal.SIGINT if os.name == "posix" else signal.SIGTERM)
        deadline = time.monotonic() + 5
        for worker in workers:
            try:
                worker.wait(timeout=max(0.01, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait()
        for reader in readers:
            reader.join(timeout=1)
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=("master", "slave"))
    parser.add_argument("--routing", default=str(ROOT / "configs/dual_arm.yaml"))
    parser.add_argument("--config", default=str(ROOT / "configs/default.yaml"))
    parser.add_argument("--target-ip")
    parser.add_argument("--bind-ip", default="0.0.0.0")
    parser.add_argument("--deadman", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--init-mode", choices=("align", "offset", "none"), default="align")
    parser.add_argument("--dry-run", action="store_true", help="Print routing without starting workers or accessing hardware")
    args = parser.parse_args(argv)
    if args.role == "master" and not args.target_ip:
        parser.error("master requires --target-ip")
    if args.role == "slave" and not args.dry_run and args.confirm != "MOVE":
        parser.error("slave requires --confirm MOVE")
    try:
        routes = load_routes(args.routing)
        if not Path(args.config).is_file():
            raise ValueError("runtime config does not exist")
        commands = build_commands(args, routes)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        parser.error(str(exc))
    for label, command in commands.items():
        print(f"{label}: {' '.join(command)}", flush=True)
    if args.dry_run:
        return 0
    return supervise(commands)

if __name__ == "__main__":
    raise SystemExit(main())
