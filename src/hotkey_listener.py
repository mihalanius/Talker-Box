import sys
import ctypes
import ctypes.wintypes as wintypes
import time
import signal
import datetime

user32 = ctypes.windll.user32

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

MODIFIER_CHECK = {
    0x11: [0x11, 0xA2, 0xA3],
    0x10: [0x10, 0xA0, 0xA1],
    0x12: [0x12, 0xA4, 0xA5],
    0x5B: [0x5B, 0x5C],
}


def parse_hotkey(hotkey_str):
    parts = [p.strip().lower() for p in hotkey_str.split("+")]
    vk = None
    modifiers = set()
    all_keys = []
    for p in parts:
        code = VK_MAP.get(p)
        if code is not None:
            all_keys.append(code)
            if code in MODIFIER_CHECK:
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


def is_key_pressed(vk):
    state = user32.GetAsyncKeyState(vk)
    return (state & 0x8000) != 0


def main():
    if len(sys.argv) < 2:
        print("Usage: hotkey_listener.py <hotkey>", flush=True)
        return

    hotkey_str = sys.argv[1]
    modifiers, vk = parse_hotkey(hotkey_str)
    if vk is None:
        print(f"ERROR: invalid hotkey '{hotkey_str}'", flush=True)
        return

    print(f"LISTENER_READY:{hotkey_str}", flush=True)

    was_pressed = False
    running = True

    def shutdown(sig, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    last_heartbeat = time.time()

    while running:
        try:
            all_mod_pressed = all(is_key_pressed(m) for m in modifiers) if modifiers else True
            main_pressed = is_key_pressed(vk)
            combo_pressed = all_mod_pressed and main_pressed

            if combo_pressed and not was_pressed:
                was_pressed = True
                print("KEY_DOWN", flush=True)
                sys.stderr.write(f"[LISTENER] KEY_DOWN vk={vk:#x} mods={modifiers}\n")
                sys.stderr.flush()
            elif not combo_pressed and was_pressed:
                was_pressed = False
                print("KEY_UP", flush=True)
                sys.stderr.write(f"[LISTENER] KEY_UP vk={vk:#x} mods={modifiers}\n")
                sys.stderr.flush()

            now = time.time()
            if now - last_heartbeat >= 0.5:
                print("HEARTBEAT", flush=True)
                last_heartbeat = now

            time.sleep(0.01)
        except Exception as e:
            print(f"ERROR: {e}", flush=True)
            time.sleep(0.1)

    if was_pressed:
        print("KEY_UP", flush=True)
    print("LISTENER_STOPPED", flush=True)


if __name__ == "__main__":
    main()
