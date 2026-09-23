from __future__ import annotations

import ctypes
import ctypes.wintypes
import sys
from dataclasses import dataclass, field
from io import BytesIO
from threading import Event as StopEvent
from threading import Lock
from time import monotonic
from typing import Any

from .telemetry import Event, EventType
from .vision import FrameLabels, VisionRecorder


@dataclass
class LiveFrameLabels:
    """Thread-safe privileged labels synchronized from Preview telemetry."""

    active: bool = False
    episode: int = 0
    player: dict[str, Any] = field(default_factory=dict)
    blueprint: dict[str, Any] = field(default_factory=dict)
    world: dict[str, Any] = field(default_factory=dict)
    survival: dict[str, Any] = field(default_factory=dict)
    current_target: dict[str, Any] | None = None
    current_action: str | None = None
    placement_result: str | None = None
    _lock: Lock = field(default_factory=Lock, repr=False)

    def consume(self, event: Event) -> None:
        payload = event.payload
        with self._lock:
            if event.event_type is EventType.EPISODE_STARTED:
                self.episode += 1
                self.active = payload.get("vision_capture") is True
                self.blueprint = {
                    "name": payload.get("blueprint"),
                    "block": payload.get("block"),
                    "total_blocks": payload.get("total_blocks"),
                }
                self.world = {
                    "origin": payload.get("origin"),
                    # Stable across recorder restarts, unlike the local counter.
                    "episode": f"{event.timestamp}:{payload.get('bedrock_tick', 'unknown')}",
                }
                self.current_target = None
                self.current_action = "START"
                self.placement_result = None
            elif event.event_type is EventType.STATE_UPDATED:
                self.player = dict(payload.get("player") or {})
                self.survival = {"health": payload.get("health"), "hunger": payload.get("hunger")}
                self.world.update({
                    "completion": payload.get("completion"),
                    "correct": payload.get("correct"),
                    "missing": payload.get("missing"),
                    "built_actions": list(payload.get("built_actions") or []),
                })
            elif event.event_type is EventType.OBJECTIVE_SELECTED:
                self.current_target = dict(payload.get("target") or {})
                self.current_action = f"POLICY_ACTION_{payload.get('policy_action')}"
                self.placement_result = None
            elif event.event_type is EventType.MOVEMENT_STARTED:
                self.current_action = "MOVE"
            elif event.event_type is EventType.PLACEMENT_DECISION:
                self.current_action = f"PLACEMENT_{payload.get('decision')}"
            elif event.event_type is EventType.BLOCK_PLACEMENT_ATTEMPTED:
                self.current_action = "PLACE"
            elif event.event_type is EventType.BLOCK_PLACEMENT_SUCCEEDED:
                self.placement_result = "SUCCEEDED"
            elif event.event_type is EventType.BLOCK_PLACEMENT_FAILED:
                self.placement_result = "FAILED"
            elif event.event_type in (EventType.EPISODE_COMPLETED, EventType.EPISODE_FAILED):
                self.current_action = event.event_type.value
                self.active = False

    def snapshot(self) -> tuple[bool, int, FrameLabels]:
        with self._lock:
            return self.active, self.episode, FrameLabels(
                dict(self.player),
                dict(self.blueprint),
                dict(self.world),
                dict(self.survival),
                dict(self.current_target) if self.current_target else None,
                self.current_action,
                self.placement_result,
            )


def find_preview_client() -> tuple[int, int, int, int]:
    """Return the visible Minecraft Preview client rectangle in screen coordinates."""
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    matches: list[int] = []

    def process_path(hwnd) -> str:
        process_id = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        handle = kernel32.OpenProcess(0x1000, False, process_id.value)
        if not handle:
            return ""
        try:
            size = ctypes.wintypes.DWORD(32_768)
            buffer = ctypes.create_unicode_buffer(size.value)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return buffer.value.lower()
            return ""
        finally:
            kernel32.CloseHandle(handle)

    def is_preview_window(hwnd) -> bool:
        length = user32.GetWindowTextLengthW(hwnd)
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)
        if "minecraft preview" in title.value.lower() or "minecraftwindowsbeta" in process_path(hwnd):
            return True
        found = False

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def child_callback(child, _lparam):
            nonlocal found
            if "minecraftwindowsbeta" in process_path(child):
                found = True
                return False
            return True

        user32.EnumChildWindows(hwnd, child_callback, 0)
        return found

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        if is_preview_window(hwnd):
            matches.append(hwnd)
        return True

    foreground = user32.GetForegroundWindow()
    if foreground and is_preview_window(foreground):
        matches.append(foreground)
    else:
        user32.EnumWindows(callback, 0)
    if not matches:
        raise RuntimeError("A visible Minecraft Preview window was not found")
    hwnd = matches[0]
    if foreground != hwnd:
        raise RuntimeError("Minecraft Preview must be the foreground window for uncontaminated capture")
    rect = ctypes.wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    point = ctypes.wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(point))
    if rect.right <= 0 or rect.bottom <= 0:
        raise RuntimeError("Minecraft Preview is minimized or has no visible client area")
    return point.x, point.y, point.x + rect.right, point.y + rect.bottom


def capture_preview(
    recorder: VisionRecorder,
    labels: LiveFrameLabels,
    stop: StopEvent,
    fps: float = 2.0,
    warmup_seconds: float = 6.0,
) -> None:
    from PIL import ImageGrab

    interval = 1.0 / fps
    active_since: float | None = None
    active_episode = -1
    last_capture_error: str | None = None
    while not stop.is_set():
        active, episode, frame_labels = labels.snapshot()
        if not active:
            active_since = None
        elif active_since is None or episode != active_episode:
            active_since = monotonic()
            active_episode = episode
        if active:
            if monotonic() - active_since < warmup_seconds:
                stop.wait(interval)
                continue
            try:
                bounds = find_preview_client()
                last_capture_error = None
            except RuntimeError as error:
                message = str(error)
                if message != last_capture_error:
                    print(f"Vision capture waiting: {message}", file=sys.stderr, flush=True)
                    last_capture_error = message
                stop.wait(interval)
                continue
            image = ImageGrab.grab(bbox=bounds, all_screens=True)
            encoded = BytesIO()
            image.save(encoded, "JPEG", quality=85, optimize=True)
            recorder.receive(encoded.getvalue(), frame_labels)
        stop.wait(interval)
