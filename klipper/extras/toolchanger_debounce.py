# Shared debounce state machine for toolchanger detection signals
#
# This file may be distributed under the terms of the GNU GPLv3 license.

class Debouncer:
    """Reports a value only once it hasn't changed for debounce_time.

    Feed it readings via note_reading(); it self-manages a reactor timer,
    canceling and rescheduling on every new reading until one holds long
    enough to fire the callback.
    """
    def __init__(self, reactor, debounce_time, callback):
        self.reactor = reactor
        self.debounce_time = debounce_time
        self.callback = callback
        self._timer = None

    def note_reading(self, eventtime, value):
        if self.debounce_time <= 0.:
            self.callback(eventtime, value)
            return
        if self._timer is not None:
            self.reactor.unregister_timer(self._timer)
        self._timer = self.reactor.register_timer(
            lambda t: self._fire(eventtime, value),
            self.reactor.monotonic() + self.debounce_time)

    def _fire(self, eventtime, value):
        self._timer = None
        self.callback(eventtime, value)
        return self.reactor.NEVER

    def is_pending(self):
        return self._timer is not None

    def cancel(self):
        if self._timer is not None:
            self.reactor.unregister_timer(self._timer)
            self._timer = None
