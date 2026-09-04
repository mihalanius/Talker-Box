import sys
import ctypes
import ctypes.wintypes as wintypes
import time
import signal

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


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


HOOKPROC = ctypes.CFUNCTYPE(
    ctypes.c_long,
    ctypes.c_int,
    wintypes.WPARAM,
    ctypes.c_void_p,
)

KEEP_ALIVE = []


def parse_hotkey(hotkey_str):
    parts = [p.strip().lower() for p in hotkey_str.split("+")]
    vk = None
    modifiers = set()
    all_keys = []
    for p in parts:
        code = VK_MAP.get(p)
        if code is not None:
            all_keys.append(code)
            if code in MODIFIER_ALIASES:
                modifiers.add(code)
            else:
                vk = code
        elif len(p) == 1:
            code = ord(p.upper())
            all_keys.append(code)
            vk = code
    if vk is None and all_keys:
        vk = all_keys[-1]
        modifiers.discard(vk)
    return modifiers, vk


def make_listener(modifiers, main_vk):
    pressed = set()
    was_combo = [False]
    hook_id_val = [0]

    def hook_proc(nCode, wParam, lParam):
        if nCode == HC_ACTION:
            kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            vk = kb.vkCode
            is_down = wParam in (WM_KEYDOWN, WM_SYSKEYDOWN)
            is_up = wParam in (WM_KEYUP, WM_SYSKEYUP)

            if is_down:
                pressed.add(vk)
            elif is_up:
                pressed.discard(vk)

            def matches_modifier(req_mod):
                return any(v in pressed for v in MODIFIER_ALIASES.get(req_mod, {req_mod}))

            combo_pressed = (
                all(matches_modifier(m) for m in modifiers) if modifiers else True
            ) and (main_vk in pressed)

            if combo_pressed and not was_combo[0]:
                was_combo[0] = True
                sys.stdout.write("KEY_DOWN\n")
                sys.stdout.flush()
                sys.stderr.write(f"[LISTENER] KEY_DOWN vk={main_vk:#x}\n")
                sys.stderr.flush()
                if vk in (VK_LWIN, VK_RWIN):
                    return 1
                return user32.CallNextHookEx(hook_id_val[0], nCode, wParam, ctypes.c_void_p(lParam))

            if not combo_pressed and was_combo[0]:
                was_combo[0] = False
                sys.stdout.write("KEY_UP\n")
                sys.stdout.flush()
                sys.stderr.write(f"[LISTENER] KEY_UP vk={main_vk:#x}\n")
                sys.stderr.flush()
                return user32.CallNextHookEx(hook_id_val[0], nCode, wParam, ctypes.c_void_p(lParam))

            if combo_pressed and is_up and vk == main_vk:
                if vk in (VK_LWIN, VK_RWIN):
                    return 1
                return user32.CallNextHookEx(hook_id_val[0], nCode, wParam, ctypes.c_void_p(lParam))

            if is_down and vk in (VK_LWIN, VK_RWIN):
                return 1

        return user32.CallNextHookEx(hook_id_val[0], nCode, wParam, ctypes.c_void_p(lParam))

    return hook_proc, pressed, lambda: was_combo[0], hook_id_val


def main():
    if len(sys.argv) < 2:
        print("Usage: hotkey_listener.py <hotkey>", flush=True)
        return

    hotkey_str = sys.argv[1]
    modifiers, vk = parse_hotkey(hotkey_str)
    if vk is None:
        print(f"ERROR: invalid hotkey '{hotkey_str}'", flush=True)
        return

    hook_proc_fn, pressed, get_was_combo, hook_id_val = make_listener(modifiers, vk)
    c_hook_proc = HOOKPROC(hook_proc_fn)
    KEEP_ALIVE.append(hook_proc_fn)
    KEEP_ALIVE.append(c_hook_proc)

    hook_id = user32.SetWindowsHookExA(WH_KEYBOARD_LL, c_hook_proc, None, 0)
    if not hook_id:
        print("ERROR: SetWindowsHookExA failed", flush=True)
        return

    hook_id_val[0] = hook_id

    print(f"LISTENER_READY:{hotkey_str}", flush=True)

    running = True

    def shutdown(sig, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    last_heartbeat = time.time()

    msg = wintypes.MSG()
    while running:
        ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
        if ret == 0 or ret == -1:
            break

        now = time.time()
        if now - last_heartbeat >= 0.5:
            print("HEARTBEAT", flush=True)
            last_heartbeat = now

    if get_was_combo():
        sys.stdout.write("KEY_UP\n")
        sys.stdout.flush()
    user32.UnhookWindowsHookEx(hook_id)
    print("LISTENER_STOPPED", flush=True)


if __name__ == "__main__":
    main()
