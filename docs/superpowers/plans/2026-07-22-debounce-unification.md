# Debounce Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the toolchanger's two independently-evolved debounce implementations (tool.py's pin debounce, tool_probe_endstop.py's ad hoc poll loop) with one shared, unit-tested `Debouncer` class, fed via push (pin) or bounded on-demand poll (probe endstop) as appropriate to each signal's hardware.

**Architecture:** A new dependency-free `Debouncer` class in `klipper/extras/toolchanger_debounce.py` implements trailing-edge stability tracking (cancel-and-reschedule reactor timer, fire once stable). `tool.py` feeds it from its existing `buttons` push callback. `tool_probe_endstop.py` feeds it from a bounded poll loop that only runs while a caller is actively waiting, then delegates to the existing (unchanged) `_query_open_tools()` for the final raw reading — preserving today's exact fallback behavior on both the "settled" and "timed out" exit paths.

**Tech Stack:** Python 3 (Klipper klippy host code), pytest for the new unit tests (first tests in this repo).

## Global Constraints

- Config option names, sections, and defaults must not change: `detection_debounce` (tool/toolchanger sections, default `0.050`), `probe_debounce` (`tool_probe_endstop` section, default `0.5`). No `printer.cfg` changes required on deploy.
- No new external dependencies in the Klipper extras themselves (stdlib only, matching existing style). pytest is a test-only dependency, already available locally (8.3.3).
- The new `Debouncer` class must work against Klipper's real `reactor` object: `monotonic()`, `register_timer(callback, waketime)`, `unregister_timer(timer)`, `NEVER` — the same interface `tool.py`'s original code already used.
- `tool.py`'s refactor must be a pure extraction — identical runtime behavior, no change to `detection_debounce` semantics or the `is_detection_pending()` public interface (consumed by `toolchanger.py:617,622`).
- `tool_probe_endstop.py`'s refactor must preserve the exact current fallback behavior: the final candidate list always comes from one fresh raw `query_endstop()` pass (via the existing, unchanged `_query_open_tools()`), regardless of whether the loop exited because readings settled or because it hit the timeout — this matches today's behavior and must not regress.
- This code area has caused two production crashes already (most recently commit `b1cedc0`). No task in this plan touches `printer.cfg` or gets deployed to `trident.local` automatically — deployment is a manual, operator-run step (Task 4).

---

### Task 1: Shared `Debouncer` class with unit tests

**Files:**
- Create: `klipper/extras/toolchanger_debounce.py`
- Create: `klipper/tests/conftest.py`
- Test: `klipper/tests/test_debounce.py`

**Interfaces:**
- Produces: `Debouncer(reactor, debounce_time, callback)` with methods `note_reading(eventtime, value)`, `is_pending() -> bool`, `cancel()`. `callback(eventtime, value)` is invoked once `value` has held steady for `debounce_time` seconds (or immediately, synchronously, if `debounce_time <= 0.`). Tasks 2 and 3 consume this exact constructor and method set.

- [ ] **Step 1: Create the test path-setup file**

`klipper/tests/conftest.py`:
```python
import os
import sys

_EXTRAS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "extras")
if _EXTRAS_DIR not in sys.path:
    sys.path.insert(0, _EXTRAS_DIR)
```

This lets test files `import toolchanger_debounce` directly, without needing `__init__.py` package files anywhere under `klipper/` (Klipper's own runtime loads extras dynamically, not as a standard package — adding `__init__.py` there could interfere with that loader, so we keep this path manipulation entirely on the test side).

- [ ] **Step 2: Write the failing tests**

`klipper/tests/test_debounce.py`:
```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest klipper/tests/test_debounce.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'toolchanger_debounce'`

- [ ] **Step 4: Implement the `Debouncer` class**

`klipper/extras/toolchanger_debounce.py`:
```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest klipper/tests/test_debounce.py -v`
Expected: PASS — 5 passed

- [ ] **Step 6: Commit**

```bash
git add klipper/extras/toolchanger_debounce.py klipper/tests/conftest.py klipper/tests/test_debounce.py
git commit -m "feat: add shared Debouncer state machine with unit tests"
```

---

### Task 2: Refactor `tool.py` to use `Debouncer`

**Files:**
- Modify: `klipper/extras/tool.py:7` (import)
- Modify: `klipper/extras/tool.py:39-42` (field init)
- Modify: `klipper/extras/tool.py:115-136` (`_handle_detect`, `_detect_debounced`, `is_detection_pending`, `_apply_detect`)

**Interfaces:**
- Consumes: `Debouncer(reactor, debounce_time, callback)`, `.note_reading(eventtime, value)`, `.is_pending()` from Task 1.
- Produces: no change to `Tool.is_detection_pending()` or `Tool.detection_debounce` — both keep their existing signatures, since `toolchanger.py:617,622` reads them directly.

- [ ] **Step 1: Add the import**

In `klipper/extras/tool.py`, change:
```python
from . import toolchanger
```
to:
```python
from . import toolchanger
from . import toolchanger_debounce
```

- [ ] **Step 2: Replace the timer field with a `Debouncer` instance**

Change:
```python
        detect_pin_name = config.get('detection_pin', None)
        self.detect_state = toolchanger.DETECT_UNAVAILABLE
        self.detection_debounce = self._config_getfloat(config, 'detection_debounce', 0.050)
        self._detect_timer = None
```
to:
```python
        detect_pin_name = config.get('detection_pin', None)
        self.detect_state = toolchanger.DETECT_UNAVAILABLE
        self.detection_debounce = self._config_getfloat(config, 'detection_debounce', 0.050)
        self._debouncer = toolchanger_debounce.Debouncer(
            self.printer.get_reactor(), self.detection_debounce, self._apply_detect)
```

- [ ] **Step 3: Replace the debounce methods**

Change:
```python
    def _handle_detect(self, eventtime, is_triggered):
        if self.detection_debounce <= 0.:
            self._apply_detect(eventtime, is_triggered)
            return
        reactor = self.printer.get_reactor()
        if self._detect_timer is not None:
            reactor.unregister_timer(self._detect_timer)
        self._detect_timer = reactor.register_timer(
            lambda t: self._detect_debounced(eventtime, is_triggered),
            reactor.monotonic() + self.detection_debounce)

    def _detect_debounced(self, eventtime, is_triggered):
        self._detect_timer = None
        self._apply_detect(eventtime, is_triggered)
        return self.printer.get_reactor().NEVER

    def is_detection_pending(self):
        return self._detect_timer is not None

    def _apply_detect(self, eventtime, is_triggered):
        self.detect_state = toolchanger.DETECT_ABSENT if is_triggered else toolchanger.DETECT_PRESENT
        self.toolchanger.note_detect_change(self, eventtime)
```
to:
```python
    def _handle_detect(self, eventtime, is_triggered):
        self._debouncer.note_reading(eventtime, is_triggered)

    def is_detection_pending(self):
        return self._debouncer.is_pending()

    def _apply_detect(self, eventtime, is_triggered):
        self.detect_state = toolchanger.DETECT_ABSENT if is_triggered else toolchanger.DETECT_PRESENT
        self.toolchanger.note_detect_change(self, eventtime)
```

- [ ] **Step 4: Verify no leftover references and the file compiles**

Run:
```bash
python3 -m py_compile klipper/extras/tool.py
grep -n "_detect_timer\|_detect_debounced" klipper/extras/tool.py
```
Expected: `py_compile` produces no output (success); `grep` finds nothing (both names fully removed).

- [ ] **Step 5: Run the full test suite to confirm no regression in Task 1's tests**

Run: `pytest klipper/tests/ -v`
Expected: PASS — same tests as before, unaffected (this task doesn't touch `toolchanger_debounce.py`)

- [ ] **Step 6: Commit**

```bash
git add klipper/extras/tool.py
git commit -m "refactor: use shared Debouncer for tool detection pin"
```

---

### Task 3: Refactor `tool_probe_endstop.py` to use `Debouncer`

**Files:**
- Modify: `klipper/extras/tool_probe_endstop.py:6` (import)
- Modify: `klipper/extras/tool_probe_endstop.py:16` (field init)
- Modify: `klipper/extras/tool_probe_endstop.py:79-85` (`add_probe`)
- Modify: `klipper/extras/tool_probe_endstop.py:112-142` (`_query_open_tools_debounced`)
- Modify: `klipper/extras/tool_probe_endstop.py:183` (call site in `cmd_DETECT_ACTIVE_TOOL_PROBE`)

**Interfaces:**
- Consumes: `Debouncer(reactor, debounce_time, callback)`, `.note_reading(eventtime, value)`, `.is_pending()` from Task 1. Also consumes the existing, unchanged `_query_open_tools(self) -> list[tool_probe]` (already defined at `tool_probe_endstop.py:100-110`).
- Produces: `_query_open_tools_debounced(self) -> list[tool_probe]` — same return type as before, but no longer takes a `debounce_time` argument (it was always called with `self.probe_debounce`, so the parameter was redundant).

- [ ] **Step 1: Add the import**

In `klipper/extras/tool_probe_endstop.py`, change:
```python
from . import probe
```
to:
```python
from . import probe
from . import toolchanger_debounce
```

- [ ] **Step 2: Add the per-probe debouncer dict**

Change:
```python
        self.probes = []
        self.tool_number_to_probe = {}
```
to:
```python
        self.probes = []
        self.tool_number_to_probe = {}
        self._debouncers = {}
```

- [ ] **Step 3: Create a `Debouncer` for each probe as it's registered**

Change:
```python
    def add_probe(self, config, tool_probe):
        if tool_probe.tool_number is not None:
            if tool_probe.tool_number in self.tool_number_to_probe:
                raise config.error(f"Duplicate tool probe nr: {tool_probe.tool_number}")
            self.tool_number_to_probe[tool_probe.tool_number] = tool_probe
        self.probes.append(tool_probe)
        self.mcu_probe.add_mcu(tool_probe.mcu_probe)
```
to:
```python
    def add_probe(self, config, tool_probe):
        if tool_probe.tool_number is not None:
            if tool_probe.tool_number in self.tool_number_to_probe:
                raise config.error(f"Duplicate tool probe nr: {tool_probe.tool_number}")
            self.tool_number_to_probe[tool_probe.tool_number] = tool_probe
        self.probes.append(tool_probe)
        self.mcu_probe.add_mcu(tool_probe.mcu_probe)
        self._debouncers[tool_probe] = toolchanger_debounce.Debouncer(
            self.reactor, self.probe_debounce, lambda eventtime, triggered: None)
```

(The callback is a no-op: this `Debouncer` is only used to detect *when readings have stabilized* — `is_pending()` — not to record the value itself. The final candidate list always comes from a fresh raw query via `_query_open_tools()`, exactly as before, so the debounced value never needs to be stored separately.)

- [ ] **Step 4: Replace the poll loop**

Change:
```python
    def _query_open_tools_debounced(self, debounce_time=0.5):
        reactor = self.reactor
        print_time = self.toolhead.get_last_move_time()
        settle_until = print_time + debounce_time
        start_time = reactor.monotonic()
        last_change_time = start_time
        last_state = None
        while reactor.monotonic() - start_time < debounce_time + 0.5:
            print_time = self.toolhead.get_last_move_time()
            if print_time >= settle_until:
                break
            current_state = {}
            for tool_probe in self.probes:
                triggered = tool_probe.mcu_probe.query_endstop(print_time)
                if tool_probe.tool_number is not None:
                    current_state[tool_probe.tool_number] = triggered
            if current_state != last_state:
                last_state = current_state
                last_change_time = reactor.monotonic()
            elif reactor.monotonic() - last_change_time >= debounce_time:
                break
            reactor.pause(reactor.monotonic() + 0.01)
        self.last_query.clear()
        candidates = []
        for tool_probe in self.probes:
            triggered = tool_probe.mcu_probe.query_endstop(print_time)
            if tool_probe.tool_number is not None:
                self.last_query[tool_probe.tool_number] = triggered
            if not triggered:
                candidates.append(tool_probe)
        return candidates
```
to:
```python
    def _query_open_tools_debounced(self):
        reactor = self.reactor
        max_wait = reactor.monotonic() + self.probe_debounce + 0.5
        while reactor.monotonic() < max_wait:
            print_time = self.toolhead.get_last_move_time()
            now = reactor.monotonic()
            for tool_probe in self.probes:
                triggered = tool_probe.mcu_probe.query_endstop(print_time)
                self._debouncers[tool_probe].note_reading(now, triggered)
            if not any(d.is_pending() for d in self._debouncers.values()):
                break
            reactor.pause(reactor.monotonic() + 0.01)
        return self._query_open_tools()
```

This removes the `print_time`/`settle_until` branch entirely — it only ever advanced if moves were already queued ahead of this synchronous call, which doesn't happen in normal use, so it was dead weight. The remaining logic reuses the exact same `Debouncer` stability tracking `tool.py` uses, then falls back to `_query_open_tools()` for the final raw snapshot, matching today's behavior on both the "settled early" and "hit the timeout" exit paths.

- [ ] **Step 5: Update the call site**

Change:
```python
        active_tools = self._query_open_tools_debounced(self.probe_debounce)
```
to:
```python
        active_tools = self._query_open_tools_debounced()
```

- [ ] **Step 6: Verify no leftover references and the file compiles**

Run:
```bash
python3 -m py_compile klipper/extras/tool_probe_endstop.py
grep -n "settle_until\|last_change_time\|_query_open_tools_debounced(self.probe_debounce)" klipper/extras/tool_probe_endstop.py
```
Expected: `py_compile` produces no output (success); `grep` finds nothing.

- [ ] **Step 7: Run the full test suite to confirm no regression**

Run: `pytest klipper/tests/ -v`
Expected: PASS — same as Task 1/2 (this task doesn't change `toolchanger_debounce.py`'s tested behavior)

- [ ] **Step 8: Commit**

```bash
git add klipper/extras/tool_probe_endstop.py
git commit -m "refactor: use shared Debouncer for tool probe endstop detection"
```

---

### Task 4: Manual deployment and on-printer validation

**This task is performed by the operator (Orion) directly on `trident.local` — it is not automated, since it requires physical printer access and interactive SSH password auth that tooling in this environment cannot perform.**

- [ ] **Step 1: Deploy the three changed/new files to the printer**

From your own machine (not through automated tooling):
```bash
scp klipper/extras/toolchanger_debounce.py klipper/extras/tool.py klipper/extras/tool_probe_endstop.py pi@trident.local:~/klipper/klippy/extras/
```

- [ ] **Step 2: Restart Klipper and confirm clean startup**

```bash
ssh pi@trident.local "sudo systemctl restart klipper"
```
Then check Mainsail/Fluidd console for a clean `Printer is ready` with no tracebacks, and confirm `klippy.log` shows no import errors for `toolchanger_debounce`.

- [ ] **Step 3: Run a short, non-critical print with a few toolchanges**

Confirm tool pickups/dropoffs behave identically to before (no change expected — Task 2/3 are behavior-preserving refactors of the working path).

- [ ] **Step 4: Deliberately provoke a slow/marginal detection read**

E.g. don't fully seat a tool, or nudge a detection switch, to force a `detected_tool != tool` situation after pickup. Confirm:
- The debounce still waits the expected `~0.5s` (`probe_debounce`) / `~0.05s` (`detection_debounce`) before deciding, matching current behavior.
- The failure-recovery path (`toolchanger.py:502-510`, patched in commit `b1cedc0`) still engages correctly and does not crash.

- [ ] **Step 5: Only after Steps 3-4 pass, trust this on an unattended production print.**
