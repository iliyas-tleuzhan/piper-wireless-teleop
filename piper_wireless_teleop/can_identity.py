"""Remember USB CAN adapters by serial number or fixed USB port; never move arms."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def default_map(role):
    return ROOT / "configs" / f"can-identities-{role}.json"


def read_text(path, default=""):
    try:
        return path.read_text().strip()
    except FileNotFoundError:
        return default


def discover(net_root=Path("/sys/class/net")):
    devices = []
    for net in sorted(Path(net_root).iterdir()):
        if read_text(net / "type") != "280":  # ARPHRD_CAN, independent of interface name
            continue
        device = (net / "device").resolve()
        interface = ""
        usb = None
        for parent in [device, *device.parents]:
            if not interface:
                interface = read_text(parent / "bInterfaceNumber")
            if (parent / "idVendor").is_file() and (parent / "idProduct").is_file():
                usb = parent
                break
        if usb is None:
            continue
        devices.append(dict(name=net.name, vendor=read_text(usb / "idVendor"),
                            product=read_text(usb / "idProduct"),
                            serial=read_text(usb / "serial"), usb_path=str(usb),
                            interface=interface, port=read_text(net / "dev_port", "0")))
    return devices


def matches(device, identity):
    keys = ("vendor", "product", "interface", "port", identity["kind"])
    return all(device.get(key) == identity.get(key) for key in keys)


def register(role, left, right, devices):
    if left == right:
        raise ValueError("Left and right must be different CAN interfaces")
    identities = {}
    for label, name in (("left", left), ("right", right)):
        candidates = [dev for dev in devices if dev["name"] == name]
        if len(candidates) != 1:
            raise ValueError(f"{name}: expected one USB CAN adapter; inspect list output")
        dev = candidates[0]
        identity = {key: dev[key] for key in ("vendor", "product", "interface", "port")}
        identity.update(kind="serial", serial=dev["serial"])
        if not dev["serial"] or sum(matches(d, identity) for d in devices) != 1:
            identity.pop("serial")
            identity.update(kind="usb_path", usb_path=dev["usb_path"])
        if sum(matches(d, identity) for d in devices) != 1:
            raise ValueError(f"{name}: adapter channels cannot be uniquely identified")
        identities[label] = identity
    result = dict(version=1, role=role, arms=identities)
    resolve(result, role, devices)
    return result


def resolve(mapping, role, devices):
    if not isinstance(mapping, dict) or mapping.get("version") != 1 or mapping.get("role") != role:
        raise ValueError("Identity map version/role mismatch")
    arms = mapping.get("arms")
    if not isinstance(arms, dict) or set(arms) != {"left", "right"}:
        raise ValueError("Identity map must contain left and right")
    names = {}
    for label, identity in arms.items():
        if not isinstance(identity, dict) or identity.get("kind") not in ("serial", "usb_path"):
            raise ValueError(f"{label}: invalid identity")
        keys = ("vendor", "product", "interface", "port", identity["kind"])
        if any(not isinstance(identity.get(key), str) for key in keys) or not identity[identity["kind"]]:
            raise ValueError(f"{label}: incomplete identity")
        candidates = [dev for dev in devices if matches(dev, identity)]
        if len(candidates) != 1:
            raise ValueError(f"{label}: expected one matching adapter, found {len(candidates)}; refusing fallback to CAN numbers")
        names[label] = candidates[0]["name"]
    if names["left"] == names["right"]:
        raise ValueError("Both arm identities resolve to the same CAN interface")
    return names


def resolve_file(path, role):
    with Path(path).open(encoding="utf-8") as handle:
        return resolve(json.load(handle), role, discover())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("list", "register", "check", "setup"))
    parser.add_argument("--role", choices=("master", "slave"), default="master")
    parser.add_argument("--left")
    parser.add_argument("--right")
    parser.add_argument("--map", type=Path)
    parser.add_argument("--bitrate", type=int, default=1000000)
    args = parser.parse_args(argv)
    path = args.map if args.map is not None else default_map(args.role)
    try:
        if args.action == "list":
            devices = discover()
            if not devices:
                print("No USB CAN interfaces found.")
            for dev in devices:
                print(f"{dev['name']}: serial={dev['serial'] or '(none)'} USB={dev['usb_path']} interface={dev['interface']} channel={dev['port']}")
            return 0
        if args.action == "register":
            if not args.left or not args.right:
                parser.error("register requires --left and --right after physically checking cables")
            mapping = register(args.role, args.left, args.right, discover())
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
            temporary.replace(path)
            print(f"Saved {path}")
            for label, identity in mapping["arms"].items():
                print(f"{label}: remembered by {identity['kind']}")
            print("USB-path identities require the same ports/hub topology. Serial identities follow the adapters.")
            return 0
        names = resolve_file(path, args.role)
        for label, name in names.items():
            print(f"{label}: {name}")
        if args.action == "setup":
            if args.bitrate <= 0:
                raise ValueError("bitrate must be positive")
            # No shell expansion; no motor commands are sent.
            for name in names.values():
                for command in (["sudo", "ip", "link", "set", "dev", name, "down"],
                                ["sudo", "ip", "link", "set", "dev", name, "type", "can", "bitrate", str(args.bitrate), "restart-ms", "100"],
                                ["sudo", "ip", "link", "set", "dev", name, "up"]):
                    subprocess.run(command, check=True)
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))

if __name__ == "__main__":
    raise SystemExit(main())
