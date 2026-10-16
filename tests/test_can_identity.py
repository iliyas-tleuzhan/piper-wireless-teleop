import json
import pytest
from piper_wireless_teleop.can_identity import discover, register, resolve


def device(name, serial, path):
    return dict(name=name, serial=serial, usb_path=path, vendor="1d50", product="606f", interface="00", port="0")


def test_serial_follows_adapter_after_renumber_and_port_change():
    old = [device("can2", "LEFT", "/usb/1"), device("can1", "RIGHT", "/usb/2")]
    mapping = register("master", "can2", "can1", old)
    new = [device("can8", "RIGHT", "/usb/4"), device("can0", "LEFT", "/usb/5")]
    assert resolve(mapping, "master", new) == {"left": "can0", "right": "can8"}


@pytest.mark.parametrize("serial", ["", "DUPLICATE"])
def test_no_unique_serial_uses_fixed_ports(serial):
    old = [device("can2", serial, "/usb/1"), device("can3", serial, "/usb/2")]
    mapping = register("slave", "can2", "can3", old)
    assert mapping["arms"]["left"]["kind"] == "usb_path"
    new = [device("can3", serial, "/usb/1"), device("can2", serial, "/usb/2")]
    assert resolve(mapping, "slave", new) == {"left": "can3", "right": "can2"}


def test_missing_and_ambiguous_devices_refuse_fallback():
    old = [device("can2", "L", "/usb/1"), device("can3", "R", "/usb/2")]
    mapping = register("slave", "can2", "can3", old)
    with pytest.raises(ValueError, match="found 0"):
        resolve(mapping, "slave", old[1:])
    with pytest.raises(ValueError, match="found 2"):
        resolve(mapping, "slave", old + [device("can4", "L", "/usb/3")])
    with pytest.raises(ValueError, match="role mismatch"):
        resolve(mapping, "master", old)
    with pytest.raises(ValueError, match="different"):
        register("slave", "can2", "can2", old)


def test_sysfs_discovery(tmp_path):
    usb = tmp_path / "devices/usb1/1-4.1"
    interface = usb / "interface0"
    interface.mkdir(parents=True)
    for key, value in {"idVendor": "1d50", "idProduct": "606f", "serial": "ABC"}.items():
        (usb / key).write_text(value)
    (interface / "bInterfaceNumber").write_text("00")
    net = tmp_path / "net/can7"
    net.mkdir(parents=True)
    (net / "type").write_text("280")
    (net / "dev_port").write_text("0")
    try:
        (net / "device").symlink_to(interface, target_is_directory=True)
    except OSError:
        pytest.skip("Creating a sysfs-like symlink is unavailable on this host")
    assert discover(tmp_path / "net") == [device("can7", "ABC", str(usb))]


def test_launcher_applies_registration(tmp_path, monkeypatch, capsys):
    import piper_wireless_teleop.dual_arm as launcher
    mapping_path = tmp_path / "map.json"
    mapping_path.write_text("{}")
    monkeypatch.setattr(launcher, "resolve_file", lambda path, role: {"left": "can9", "right": "can8"})
    assert launcher.main(["slave", "--dry-run", "--identity-map", str(mapping_path)]) == 0
    output = capsys.readouterr().out
    assert "--can can9" in output and "--can can8" in output


def test_launcher_explicit_missing_map_fails(tmp_path):
    from piper_wireless_teleop.dual_arm import main
    with pytest.raises(SystemExit) as result:
        main(["slave", "--dry-run", "--identity-map", str(tmp_path / "missing.json")])
    assert result.value.code == 2
