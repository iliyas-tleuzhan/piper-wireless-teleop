"""Exercise the real sender with deterministic CAN timeouts and delayed sends."""
from types import SimpleNamespace
import can
import pytest
import scripts.master_sender as sender


@pytest.mark.parametrize("stall", [False, True])
def test_250hz_deadlines_survive_idle_can_without_drift_or_bursts(monkeypatch, stall):
    clock = SimpleNamespace(now=0.0)
    samples = []
    timeouts = []
    class Bus:
        def __init__(self):
            self.frames = iter(can.Message(arbitration_id=key, data=bytes(8), is_extended_id=False)
                               for key in (0x155, 0x156, 0x157))
            self.closed = False
        def recv(self, timeout):
            timeouts.append(timeout)
            assert 0 <= timeout <= 0.001
            if clock.now >= 1.0:
                raise KeyboardInterrupt
            frame = next(self.frames, None)
            clock.now += 0.000001 if frame is not None else timeout
            return frame
        def shutdown(self): self.closed = True
    class Transport:
        closed = False
        def send(self, data):
            samples.append(clock.now)
            # Packet encoding/transmission work should not accumulate schedule drift.
            clock.now += 0.0003
            if stall and len(samples) == 25:
                clock.now += 0.025
        def close(self): self.closed = True
    bus = Bus()
    transport = Transport()
    monkeypatch.setattr(sender, "parse_args", lambda: SimpleNamespace(
        config="configs/default.yaml", can="can2", target_ip="127.0.0.1", target_port=5005, deadman=True))
    monkeypatch.setattr(sender.can.interface, "Bus", lambda **kwargs: bus)
    monkeypatch.setattr(sender, "UdpSender", lambda *args: transport)
    monkeypatch.setattr(sender, "time", SimpleNamespace(monotonic=lambda: clock.now, time=lambda: 1000 + clock.now))
    sender.main()
    assert bus.closed and transport.closed
    assert 240 <= len(samples) <= 251
    gaps = [b-a for a, b in zip(samples, samples[1:])]
    if stall:
        assert max(gaps) >= 0.025
        # One send can immediately precede a scheduled slot after a stall, but
        # no series of catch-up packets is sent for all missed deadlines.
        assert sum(gap < 0.003 for gap in gaps) <= 1
    else:
        assert all(abs(gap - 0.004) < 0.00001 for gap in gaps)
        assert abs(samples[-1] - len(samples) * 0.004) < 0.00001
