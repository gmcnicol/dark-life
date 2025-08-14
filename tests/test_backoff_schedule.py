from services.renderer import poller


def test_backoff_schedule_jitter(monkeypatch):
    values = iter([0.0, 0.5, 1.0])

    def fake_rand():
        return next(values)

    gen = poller.backoff_schedule(1000, factor=2, rand=fake_rand)
    assert next(gen) == 1.0  # 1000ms + 0
    assert next(gen) == 3.0  # 2000ms + 1000ms
    assert next(gen) == 8.0  # 4000ms + 4000ms

