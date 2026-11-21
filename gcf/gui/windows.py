from __future__ import annotations

import ctypes
import re
from ctypes import wintypes
from dataclasses import dataclass

user32 = ctypes.windll.user32


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    pid: int
    window_rect: tuple[int, int, int, int]  # left, top, right, bottom
    client_rect: tuple[int, int, int, int]  # left, top, width, height


@dataclass
class MonitorInfo:
    index: int
    device: str
    left: int
    top: int
    width: int
    height: int
    primary: bool


class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
        ("szDevice", wintypes.WCHAR * 32),
    ]


user32.GetForegroundWindow.restype = wintypes.HWND
user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
user32.MonitorFromWindow.restype = wintypes.HMONITOR
user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFOEXW)]
user32.GetMonitorInfoW.restype = wintypes.BOOL


def _text(hwnd: int) -> str:
    n = user32.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def _rects(hwnd: int):
    wr = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(wr))
    cr = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(cr))
    point = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(point))
    return (wr.left, wr.top, wr.right, wr.bottom), (point.x, point.y, cr.right, cr.bottom)


def list_windows() -> list[WindowInfo]:
    result: list[WindowInfo] = []
    proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        title = _text(hwnd)
        if not title.strip():
            return True
        wr, cr = _rects(hwnd)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        result.append(WindowInfo(int(hwnd), title, int(pid.value), wr, cr))
        return True

    user32.EnumWindows(proc(callback), 0)
    return result


def find_window(title: str, exclude: tuple[str, ...] = ()) -> WindowInfo | None:
    title_l = title.lower()
    candidates = []
    for w in list_windows():
        if any(x.lower() in w.title.lower() for x in exclude):
            continue
        if title_l in w.title.lower():
            candidates.append(w)
    if not candidates:
        return None
    exact = [w for w in candidates if w.title.lower() == title_l]
    if exact:
        return max(exact, key=lambda w: w.client_rect[2] * w.client_rect[3])
    return max(candidates, key=lambda w: w.client_rect[2] * w.client_rect[3])


def title_from_obs_item(item_name: str) -> str:
    m = re.match(r"^\[[^\]]+\]:\s*(.*)$", item_name)
    return m.group(1) if m else item_name


def list_monitors() -> list[MonitorInfo]:
    result: list[MonitorInfo] = []
    proc = ctypes.WINFUNCTYPE(
        ctypes.c_bool, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM
    )

    def callback(hmonitor, _hdc, _rect, _lparam):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            r = info.rcMonitor
            result.append(MonitorInfo(
                index=len(result),
                device=info.szDevice,
                left=r.left,
                top=r.top,
                width=r.right - r.left,
                height=r.bottom - r.top,
                primary=bool(info.dwFlags & 1),
            ))
        return True

    user32.EnumDisplayMonitors(0, 0, proc(callback), 0)
    result.sort(key=lambda m: (m.left, m.top))
    for i, m in enumerate(result):
        m.index = i
    return result


def monitor_at(left: int, top: int) -> MonitorInfo | None:
    for m in list_monitors():
        if m.left == left and m.top == top:
            return m
    return None


def monitor_rect_from_obs_item(item_name: str, index: int) -> MonitorInfo | None:
    m = re.search(r"@\s*(-?\d+)\s*,\s*(-?\d+)", item_name)
    if m:
        found = monitor_at(int(m.group(1)), int(m.group(2)))
        if found:
            return found
    monitors = list_monitors()
    if 0 <= index < len(monitors):
        return monitors[index]
    return monitors[0] if monitors else None


def foreground_window() -> WindowInfo | None:
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    title = _text(hwnd)
    if not title.strip():
        return None
    wr, cr = _rects(hwnd)
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return WindowInfo(int(hwnd), title, int(pid.value), wr, cr)


def monitor_for_window(hwnd: int) -> MonitorInfo | None:
    hmon = user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
    if not hmon:
        return None
    info = MONITORINFOEXW()
    info.cbSize = ctypes.sizeof(MONITORINFOEXW)
    if not user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
        return None
    r = info.rcMonitor
    return MonitorInfo(0, info.szDevice, r.left, r.top, r.right - r.left, r.bottom - r.top, bool(info.dwFlags & 1))


def primary_screen() -> tuple[int, int, int, int]:
    return (0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))
