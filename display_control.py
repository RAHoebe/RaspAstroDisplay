"""Backend-owned backlight timer. No disk writes during activity or fades."""
from pathlib import Path
import os
import threading
import time

from providers import read_json, save_json


DEFAULT = dict(active=70, idle=10, timeout=60, auto_dim=True)


def validate(value, previous=None, legacy=False):
    if not isinstance(value, dict) or set(value) - set(DEFAULT):
        raise ValueError('Invalid display profile')
    profile = dict(previous or DEFAULT, **value)
    for key, low, high in [('active', 5, 100), ('idle', 5, 100), ('timeout', 10, 3600)]:
        n = profile[key]
        if type(n) is not int or not low <= n <= high:
            raise ValueError('Invalid display profile')
        if key != 'timeout' and key in value and not legacy and n % 5:
            raise ValueError('Brightness must use steps of 5')
    if type(profile['auto_dim']) is not bool or profile['idle'] > profile['active']:
        raise ValueError('Idle brightness exceeds active brightness')
    return profile


class DisplayController:
    def __init__(self, state, device=None, clock=time.monotonic):
        self.path = Path(state) / 'brightness.json'
        self.device = device
        self.clock = clock
        self.lock = threading.RLock()
        saved = read_json(self.path, {})
        if not isinstance(saved, dict):
            saved = {}
        legacy = saved.get('percent', 70)
        try:
            self.profile = validate(saved.get('display', dict(active=legacy, idle=min(10, legacy))), legacy=True)
        except (ValueError, TypeError):
            self.profile = dict(DEFAULT)
        self.last_activity = clock()
        self.dimmed = False
        self.current = self.profile['active']
        self.fade = None
        self.last_written = None
        self.available = False
        self.maximum = 0
        if device:
            try:
                self.maximum = int((device.parent / 'max_brightness').read_text())
                self.available = self.maximum > 0 and os.access(device, os.W_OK)
            except (OSError, ValueError):
                pass

    def view(self):
        with self.lock:
            return dict(profile=dict(self.profile), available=self.available, dimmed=self.dimmed and self.available,
                        current=round(self.current), seconds_until_idle=max(0, self.profile['timeout']-(self.clock()-self.last_activity)))

    def _write(self):
        if self.available:
            value = max(1, round(self.maximum*self.current/100))
            if value != self.last_written:
                try:
                    self.device.write_text(str(value))
                    self.last_written = value
                except OSError:
                    # Fail open: a failed backlight must never swallow normal touches.
                    self.available = False
                    self.dimmed = False

    def _transition(self, dimmed, at):
        self.dimmed = dimmed
        self.fade = (at, self.current, self.profile['idle' if dimmed else 'active'], 1.0 if dimmed else .2)

    def tick(self):
        with self.lock:
            at = self.clock()
            idle = self.available and self.profile['auto_dim'] and at-self.last_activity >= self.profile['timeout']
            if idle != self.dimmed:
                self._transition(idle, at)
            if self.fade:
                start, value, target, duration = self.fade
                fraction = min(1, max(0, (at-start)/duration))
                self.current = value + (target-value)*fraction
                if fraction == 1:
                    self.fade = None
            self._write()

    def activity(self):
        with self.lock:
            self.tick()
            wake_only = self.available and self.dimmed
            self.last_activity = self.clock()
            if self.dimmed:
                self._transition(False, self.last_activity)
            return dict(self.view(), wake_only=wake_only)

    def update(self, value, legacy=False):
        with self.lock:
            profile = validate(value, self.profile, legacy)
            if profile != self.profile:
                # Retain percent for v1.0 rollback and older backup restorers.
                save_json(self.path, dict(percent=profile['active'], display=profile))
                self.profile = profile
                self._transition(self.dimmed and profile['auto_dim'], self.clock())
            return self.view()

    def start(self):
        saved = dict(percent=self.profile['active'], display=self.profile)
        if read_json(self.path, {}) != saved:
            save_json(self.path, saved)
        self._write()  # Every process start begins at the saved active brightness.
        def run():
            while True:
                self.tick()
                time.sleep(.04)
        threading.Thread(target=run, daemon=True, name='backlight').start()
