from toolchanger_debounce import Debouncer


class FakeReactor:
    """Minimal stand-in for Klipper's reactor: a controllable virtual
    clock plus a list of (waketime, callback) timer entries. advance_to()
    fires all due timers in waketime order, matching reactor.py's contract
    that a timer callback's return value becomes its next waketime."""
    NEVER = 9999999999999999.

    def __init__(self):
        self.time = 0.0
        self.timers = []

    def monotonic(self):
        return self.time

    def register_timer(self, callback, waketime=None):
        timer = [self.NEVER if waketime is None else waketime, callback]
        self.timers.append(timer)
        return timer

    def unregister_timer(self, timer):
        if timer in self.timers:
            self.timers.remove(timer)

    def advance_to(self, t):
        self.time = t
        while True:
            due = [tm for tm in self.timers if tm[0] <= self.time]
            if not due:
                break
            due.sort(key=lambda tm: tm[0])
            timer = due[0]
            self.timers.remove(timer)
            waketime, callback = timer
            next_time = callback(self.time)
            if next_time != self.NEVER:
                self.timers.append([next_time, callback])


def test_fires_after_debounce_time_elapses():
    reactor = FakeReactor()
    calls = []
    debouncer = Debouncer(reactor, 0.05, lambda et, v: calls.append((et, v)))

    debouncer.note_reading(0.0, True)
    assert calls == []
    assert debouncer.is_pending()

    reactor.advance_to(0.05)
    assert calls == [(0.0, True)]
    assert not debouncer.is_pending()


def test_rapid_toggle_resets_timer():
    reactor = FakeReactor()
    calls = []
    debouncer = Debouncer(reactor, 0.05, lambda et, v: calls.append((et, v)))

    debouncer.note_reading(0.0, True)
    reactor.advance_to(0.03)
    debouncer.note_reading(0.03, False)  # resets the timer before it fires
    reactor.advance_to(0.05)
    assert calls == []  # would have fired at 0.05 if not reset

    reactor.advance_to(0.08)
    assert calls == [(0.03, False)]


def test_zero_debounce_fires_immediately():
    reactor = FakeReactor()
    calls = []
    debouncer = Debouncer(reactor, 0.0, lambda et, v: calls.append((et, v)))

    debouncer.note_reading(1.23, True)
    assert calls == [(1.23, True)]
    assert not debouncer.is_pending()
    assert reactor.timers == []


def test_cancel_prevents_fire():
    reactor = FakeReactor()
    calls = []
    debouncer = Debouncer(reactor, 0.05, lambda et, v: calls.append((et, v)))

    debouncer.note_reading(0.0, True)
    debouncer.cancel()
    reactor.advance_to(0.1)
    assert calls == []
    assert not debouncer.is_pending()


def test_is_pending_accurate_at_each_step():
    reactor = FakeReactor()
    debouncer = Debouncer(reactor, 0.05, lambda et, v: None)

    assert not debouncer.is_pending()
    debouncer.note_reading(0.0, True)
    assert debouncer.is_pending()
    reactor.advance_to(0.05)
    assert not debouncer.is_pending()
