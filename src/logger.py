import os
import datetime

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)))
LOG_FILE = os.path.join(LOG_DIR, "talkerbox.log")


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
