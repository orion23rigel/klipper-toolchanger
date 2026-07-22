# Debounce Unification Design

## Background

The toolchanger plugin debounces two unrelated physical signals with two
independently-evolved implementations:

- `tool.py` debounces the per-tool **detection pin** (fed by Klipper's
  `buttons` extra via push callbacks) with a correct trailing-edge reactor
  timer: cancel-and-reschedule on every new reading, fire once stable.
- `tool_probe_endstop.py` debounces the **tool probe endstop** signal with a
  separate, hand-rolled busy-poll loop (`_query_open_tools_debounced`) that
  mixes wall-clock stability tracking with a `toolhead.get_last_move_time()`
  "settle" condition that is effectively dead code in normal use (it only
  advances if moves are already queued ahead of the call, which doesn't
  happen inside this synchronous poll).

Git history shows ~15 commits touching this area (added/reverted/re-added
debounce logic, several "prevent crash" fixes), including the bug fixed in
commit `b1cedc0` (wrong dict key read while handling a failed-detection
case introduced by this same debounce logic). The duplication and ad hoc
implementation are a recurring source of bugs.

## Goal

Consolidate on one shared, independently-tested debounce state machine,
used by both signals via different feed models appropriate to their
underlying hardware:

- The detection pin keeps its push model (background, event-driven via
  `buttons`).
- The tool probe endstop keeps its on-demand poll model (bounded, only
  while a caller is actively waiting) rather than becoming continuously
  monitored — `query_endstop()` is an MCU round-trip, not something to poll
  in the background indefinitely (this is why Klipper's own homing/probing
  code queries on demand rather than continuously).

## Design

### New shared class: `klipper/extras/toolchanger_debounce.py`

```python
class Debouncer:
    """Reports a value only once it hasn't changed for debounce_time.
    Feed it readings via note_reading(); it self-manages a reactor timer,
    canceling and rescheduling on every new reading until one holds long
    enough to fire the callback."""
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
```

This is `tool.py`'s existing cancel-and-reschedule logic, extracted so it's
shared and independently testable.

### `tool.py` integration

`_handle_detect`, `_detect_debounced`, and the `_detect_timer` field
collapse into one `Debouncer` instance (`callback=self._apply_detect`).
`_handle_detect(eventtime, is_triggered)` becomes
`self._debouncer.note_reading(eventtime, is_triggered)`.
`is_detection_pending()` becomes `self._debouncer.is_pending()`.
This is a pure extraction — runtime behavior is unchanged.

### `tool_probe_endstop.py` integration

One `Debouncer` per tool probe, created once
(`debounce_time=self.probe_debounce`), callback records the debounced
value. `_query_open_tools_debounced` becomes a bounded loop that, each
~10ms tick, queries every probe and feeds the result into its `Debouncer`
via `note_reading`, exiting early once none are pending, or on an overall
timeout (same safety cap as today). This removes the dead
`print_time`/`settle_until` branch and replaces the ad hoc dict-comparison
with the same tested stability logic `tool.py` uses. It still only runs
while a caller is actively waiting (`DETECT_ACTIVE_TOOL_PROBE`, or the
pre-toolchange check) — never as background polling.

### Config compatibility

`detection_debounce` (tool/toolchanger sections) and `probe_debounce`
(`tool_probe_endstop` section) keep their current names, defaults, and
semantics. No `printer.cfg` changes required on deploy.

### Testing

New `klipper/tests/test_debounce.py` (first tests in this repo) using a
small `FakeReactor`: a controllable virtual clock, a dict of scheduled
`(time, callback)` entries, and an `advance_to(t)` helper that fires due
timers in order. Pure logic, no Klipper printer object graph needed.

Cases:
- single reading fires callback only after `debounce_time` elapses
- rapid toggling before it settles keeps resetting the timer and never
  fires early
- `debounce_time=0` fires synchronously, no timer registered
- `cancel()` prevents a pending callback from firing
- `is_pending()` is accurate at each step (relied on by
  `_wait_for_detection_debounce` and the probe poll loop to know when to
  stop waiting)

### Rollout

This exact code area caused the crash fixed in `b1cedc0`, plus a long
history of similar bugs. After unit tests pass:
1. Deploy to `trident.local`.
2. Run a short/non-critical print with a few toolchanges to confirm
   normal behavior.
3. Deliberately provoke a slow/marginal detection read (e.g. a tool not
   fully seated) to confirm both the debounce and the failure-recovery
   path behave as expected.
4. Only then trust it on an unattended production print.

## Out of scope

- `toolchanger.py`'s `_wait_for_detection_debounce` (polls for the
  detection-pin debouncers to finish) is left as is — it's a
  wait-for-completion loop, not a debounce implementation, and Klipper's
  cooperative-scheduling model makes poll-with-pause the idiomatic way to
  block synchronously inside a gcode handler.
- Investigating why T1's detection didn't confirm on the pickup that
  triggered the original crash is a separate, hardware-side investigation.
