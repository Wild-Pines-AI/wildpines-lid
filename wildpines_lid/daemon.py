"""Animation daemon. Init sequence, then loops Wild Pines frames with latch per frame.
Restores firmware default on any exit path."""

from __future__ import annotations

import signal
import sys
import time

from . import protocol
from .animations import wildpines
from .hid_io import LidDevice


class AnimationDaemon:
    def __init__(
        self,
        policy: protocol.SafetyPolicy | None = None,
        duration: float | None = None,
        brightness: int = protocol.BRIGHTNESS_FULL,
    ) -> None:
        self._policy = policy or protocol.SafetyPolicy(
            allow_rollback=True,
            allow_brightness=True,
            allow_custom_frames=True,
        )
        self._running = True
        self._duration = duration
        self._brightness = brightness

    def _handle_signal(self, signum, frame) -> None:
        self._running = False

    def run(self) -> int:
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        start = time.monotonic()
        with LidDevice(policy=self._policy) as dev:
            try:
                dev.init_sequence(brightness=self._brightness)
                while self._running:
                    for fb in wildpines.frames():
                        if not self._running:
                            break
                        if self._duration and (time.monotonic() - start) >= self._duration:
                            self._running = False
                            break
                        for pkt in fb.build_frame():
                            dev.write(pkt)
                        time.sleep(wildpines.FRAME_MS / 1000)
            finally:
                try:
                    dev.restore_default()
                except Exception as e:
                    print(f"warning: restore-default failed: {e}", file=sys.stderr)
        return 0
