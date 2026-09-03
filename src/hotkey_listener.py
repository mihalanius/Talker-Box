import sys
import ctypes
import ctypes.wintypes as wintypes
import time

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

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

MODIFIER_VKS = {0x11, 0x10, 0x12, 0x5B, 0x5C}


def parse_hotkey(hotkey_str):
    parts = [p.strip().lower() for p in hotkey_str.split("+")]
    target_vks = set()
    for p in parts:
        vk = VK_MAP.get(p)
        if vk:
            target_vks.add(vk)
        elif len(p) == 1:
            target_vks.add(ord(p.upper()))
    return target_vks


def is_modifier(vk):
    return vk in MODIFIER_VKS


def main():
    if len(sys.argv) < 2:
        print("Usage: hotkey_listener.py <hotkey>", flush=True)
        return

    hotkey_str = sys.argv[1]
    target_vks = parse_hotkey(hotkey_str)
    if not target_vks:
        print(f"ERROR: invalid hotkey '{hotkey_str}'", flush=True)
        return

    pressed_vks = set()
    hook_id = None
    callback = None
    user32 = ctypes.windll.user32

    def process_event(vk, is_down):
        if is_down:
            pressed_vks.add(vk)
        else:
            pressed_vks.discard(vk)

        target_pressed = target_vks.issubset(pressed_vks)
        non_modifier_pressed = any(
            v for v in pressed_vks if not is_modifier(v)
        )

        if target_pressed:
            if target_vks == pressed_vks or (
                not non_modifier_pressed and len(target_vks) == len([v for v in target_vks if is_modifier(v)])
            ):
                if is_down:
                    print("KEY_DOWN", flush=True)
                else:
                    print("KEY_UP", flush=True)

    @ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
    def hook_proc(nCode, wParam, lParam):
        if nCode >= 0:
            kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            vk = kb.vkCode
            msg = wParam

            if msg in (WM_KEYDOWN, WM_SYSKEYDOWN):
                process_event(vk, True)
            elif msg in (WM_KEYUP, WM_SYSKEYUP):
                process_event(vk, False)

        return user32.CallNextHookEx(hook_id, nCode, wParam, lParam)

    class KBDLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ("vkCode", wintypes.DWORD),
            ("scanCode", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    callback = hook_proc
    hook_id = user32.SetWindowsHookExA(
        WH_KEYBOARD_LL, callback, None, 0
    )

    if not hook_id:
        print("ERROR: SetWindowsHookEx failed", flush=True)
        return

    print(f"LISTENER_READY:{hotkey_str}", flush=True)

    msg = wintypes.MSG()
    while user32.GetMessageA(ctypes.byref(msg), None, 0, 0) != 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageA(ctypes.byref(msg))

    user32.UnhookWindowsHookEx(hook_id)


if __name__ == "__main__":
    main()
