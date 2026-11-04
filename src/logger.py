import os
import datetime

from paths import get_exe_dir

# файл лога кладём рядом с программой: в onefile-сборке __file__ смотрит в _MEIPASS,
# поэтому от него путь не считается — иначе лог писался во временную папку и терялся
LOG_FILE = os.path.join(get_exe_dir(), "talkerbox.log")


def log(event, details=""):
    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"[{ts}] {event}"
    if details:
        line += f" | {details}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
