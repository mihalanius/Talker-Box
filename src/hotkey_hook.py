import ctypes
import ctypes.wintypes as wintypes
import threading
import time
from PyQt6.QtCore import QTimer

user32 = ctypes.windll.user32

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
HC_ACTION = 0
VK_LWIN = 0x5B
VK_RWIN = 0x5C

VK_MAP = {
    "ctrl": 0x11, "lctrl": 0x11, "rctrl": 0x11,
    "shift": 0x10, "lshift": 0x10, "rshift": 0x10,
    "alt": 0x12, "lalt": 0x12, "ralt": 0x12,
    "win": 0x5B, "lwin": 0x5B, "rwin": 0x5C,
    "space": 0x20, "enter": 0x0D, "esc": 0x1B,
    "tab": 0x09, "capslock": 0x14,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45,
    "f": 0x46, "g": 0x47, "h": 0x48, "i": 0x49, "j": 0x4A,
    "k": 0x4B, "l": 0x4C, "m": 0x4D, "n": 0x4E, "o": 0x4F,
    "p": 0x50, "q": 0x51, "r": 0x52, "s": 0x53, "t": 0x54,
    "u": 0x55, "v": 0x56, "w": 0x57, "x": 0x58, "y": 0x59, "z": 0x5A,
    "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
}

MODIFIER_ALIASES = {
    0x11: {0x11, 0xA2, 0xA3},
    0x10: {0x10, 0xA0, 0xA1},
    0x12: {0x12, 0xA4, 0xA5},
    0x5B: {0x5B, 0x5C},
}

VK_NAMES = {v: k for k, v in VK_MAP.items() if len(k) <= 2 and k.isalpha()}


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


KEEP_ALIVE = []


def parse_hotkey(hotkey_str):
    parts = [p.strip().lower() for p in hotkey_str.split("+")]
    vk = None
    modifiers = set()
    for p in parts:
        code = VK_MAP.get(p)
        if code is None and len(p) == 1:
            code = ord(p.upper())
        if code is not None:
            if code in MODIFIER_ALIASES:
                modifiers.add(code)
            else:
                vk = code
    if vk is None and modifiers:
        vk = None
    return modifiers, vk


class HotkeyListener:
    def __init__(self, hotkey_str, on_down, on_up):
        self.hotkey_str = hotkey_str
        self.on_down = on_down
        self.on_up = on_up
        self._thread = None
        self._running = False
        self._hook_id = 0
        self._modifiers, self._main_vk = parse_hotkey(hotkey_str)

    def start(self):
        self.stop()
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._hook_id:
            user32.UnhookWindowsHookEx(self._hook_id)
            self._hook_id = 0
        self._thread = None

    def _run(self):
        pressed = set()
        was_combo = False
        hook_id_val = [0]

        combo_keys = set()
        for m in self._modifiers:
            combo_keys.update(MODIFIER_ALIASES.get(m, {m}))
        if self._main_vk is not None:
            combo_keys.add(self._main_vk)

        def hook_proc(nCode, wParam, lParam):
            nonlocal was_combo
            if nCode == HC_ACTION:
                kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                vk = kb.vkCode
                is_down = wParam in (WM_KEYDOWN, WM_SYSKEYDOWN)
                is_up = wParam in (WM_KEYUP, WM_SYSKEYUP)

                if is_down:
                    pressed.add(vk)
                elif is_up:
                    pressed.discard(vk)

                all_mods_pressed = all(
                    any(v in pressed for v in MODIFIER_ALIASES.get(m, {m}))
                    for m in self._modifiers
                ) if self._modifiers else True

                main_in_combo = self._main_vk is None or self._main_vk in pressed
                combo_pressed = all_mods_pressed and main_in_combo

                if was_combo and is_down:
                    return 1

                if combo_pressed and not was_combo:
                    was_combo = True
                    try:
                        self.on_down()
                    except Exception:
                        pass
                    return 1

                if was_combo and not pressed:
                    was_combo = False
                    try:
                        self.on_up()
                    except Exception:
                        pass

                if is_down and vk in (VK_LWIN, VK_RWIN):
                    return 1

            return user32.CallNextHookEx(hook_id_val[0], nCode, wParam, ctypes.c_void_p(lParam))

        HOOKPROC = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_int, wintypes.WPARAM, ctypes.c_void_p)
        c_hook_proc = HOOKPROC(hook_proc)
        KEEP_ALIVE.append(c_hook_proc)

        hook_id = user32.SetWindowsHookExA(WH_KEYBOARD_LL, c_hook_proc, None, 0)
        if not hook_id:
            return

        hook_id_val[0] = hook_id
        self._hook_id = hook_id

        msg = wintypes.MSG()
        while self._running:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0 or ret == -1:
                break

        user32.UnhookWindowsHookEx(hook_id)


def start_capture(callback):
    VK_NAMES = {
        0x11: "ctrl", 0xA2: "ctrl", 0xA3: "ctrl",
        0x10: "shift", 0xA0: "shift", 0xA1: "shift",
        0x12: "alt", 0xA4: "alt", 0xA5: "alt",
        0x5B: "win", 0x5C: "win",
        0x41: "a", 0x42: "b", 0x43: "c", 0x44: "d", 0x45: "e",
        0x46: "f", 0x47: "g", 0x48: "h", 0x49: "i", 0x4A: "j",
        0x4B: "k", 0x4C: "l", 0x4D: "m", 0x4E: "n", 0x4F: "o",
        0x50: "p", 0x51: "q", 0x52: "r", 0x53: "s", 0x54: "t",
        0x55: "u", 0x56: "v", 0x57: "w", 0x58: "x", 0x59: "y", 0x5A: "z",
        0x70: "f1", 0x71: "f2", 0x72: "f3", 0x73: "f4",
        0x74: "f5", 0x75: "f6", 0x76: "f7", 0x77: "f8",
        0x78: "f9", 0x79: "f10", 0x7A: "f11", 0x7B: "f12",
        0x20: "space", 0x0D: "enter", 0x1B: "esc",
        0x09: "tab", 0x14: "capslock",
    }

    state = {"pressed": set(), "peak": set(), "seen": False, "done": False, "hook_id": 0}

    def hook_proc(nCode, wParam, lParam):
        if nCode == HC_ACTION:
            kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            vk = kb.vkCode
            is_down = wParam in (WM_KEYDOWN, WM_SYSKEYDOWN)
            is_up = wParam in (WM_KEYUP, WM_SYSKEYUP)

            if is_down:
                state["pressed"].add(vk)
                state["peak"] = set(state["pressed"])
                state["seen"] = True
            elif is_up:
                state["pressed"].discard(vk)
                if state["seen"] and not state["pressed"]:
                    state["done"] = True

        return user32.CallNextHookEx(state["hook_id"], nCode, wParam, ctypes.c_void_p(lParam))

    HOOKPROC = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_int, wintypes.WPARAM, ctypes.c_void_p)
    c_hook_proc = HOOKPROC(hook_proc)
    KEEP_ALIVE.append(c_hook_proc)

    hook_id = user32.SetWindowsHookExA(WH_KEYBOARD_LL, c_hook_proc, None, 0)
    if not hook_id:
        callback(None)
        return

    state["hook_id"] = hook_id

    def poll():
        if state["done"]:
            user32.UnhookWindowsHookEx(hook_id)
            keys = state["peak"]
            parts = []
            for vk in sorted(keys):
                name = VK_NAMES.get(vk, chr(vk) if 32 <= vk < 127 else f"vk{vk}")
                parts.append(name)
            callback("+".join(parts) if parts else None)
            return
        QTimer.singleShot(16, poll)

    QTimer.singleShot(16, poll)
