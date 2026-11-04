# -*- coding: utf-8 -*-
"""Talker Box — установка окружения для dev-версии одним запуском.

Что делает скрипт:
  1. проверяет версию Python (нужен 3.12+; рекомендуется 3.13);
  2. создаёт `venv` (или пересоздаёт, если старое окружение сломано);
  3. ставит недостающие пакеты из `requirements.txt`;
  4. проверяет, что все модули реально импортируются;
  5. проверяет модель GigaAM в `models\\GigaAM` и докачивает её с HuggingFace;
  6. проверяет файлы проекта (шрифт, звуки, иконки, справка, словарь);
  7. прогоняет py_compile по всем модулям `src`;
  8. печатает итог и (по желанию) сразу запускает программу.

Запуск:
    py -3.13 setup_dev.py            # полная установка
    py -3.13 setup_dev.py --check    # только проверить, ничего не менять
    py -3.13 setup_dev.py --run      # установить и сразу запустить
    py -3.13 setup_dev.py --no-model # не скачивать модель

Или просто двойной клик по `install_dev.bat`.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
VENV = os.path.join(ROOT, "venv")
VENV_PY = os.path.join(VENV, "Scripts", "python.exe")
REQ_FILE = os.path.join(ROOT, "requirements.txt")
LOG_FILE = os.path.join(ROOT, "setup_dev.log")
MODEL_DIR = os.path.join(ROOT, "models", "GigaAM")

MODEL_REPO = ("https://huggingface.co/csukuangfj/"
              "sherpa-onnx-nemo-transducer-punct-giga-am-v3-russian-2025-12-16/resolve/main/")
MODEL_FILES = {
    "encoder.int8.onnx": 224570820,
    "decoder.onnx": 4600132,
    "joiner.onnx": 2712896,
    "tokens.txt": 13354,
}

PACKAGES = [
    # (модуль для импорта, имя пакета в pip)
    ("PyQt6.QtWidgets", "PyQt6"),
    ("sounddevice", "sounddevice"),
    ("numpy", "numpy"),
    ("sherpa_onnx", "sherpa-onnx"),
    ("comtypes", "comtypes"),
    ("win32ctypes", "pywin32-ctypes"),
    ("pyperclip", "pyperclip"),
]

ASSETS = [
    "fonts/Orbitron.ttf",
    "sounds/ping.wav",
    "sounds/tap_01.wav",
    "sounds/tap_02.wav",
    "sounds/transition_up.wav",
    "sounds/transition_down.wav",
    "mascot.png",
    "mascot_new.png",
    "talker_box.png",
    "talker_box.ico",
    "help.html",
    "ads.json",
    "vocabularies/programming.json",
]

DICT_TEMPLATE = """\
# Словарь неправильных слов для Talker Box
# Формат строки: Правильное слово - неправильный1, неправильный2
# Строки, начинающиеся с #, — комментарии, они не читаются.
# Правка в любом блокноте: изменения подхватываются сразу, без перезапуска.

Seed - SID, Sid, Сид, сит
Git - Гит, Гид
"""

_log_lines = []
_tty = sys.stdout.isatty()


def _setup_console():
    """UTF-8 в консоли Windows, чтобы русский текст не превращался в кракозябры."""
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def out(text=""):
    try:
        print(text)
    except Exception:
        try:
            print(text.encode("ascii", "replace").decode("ascii"))
        except Exception:
            pass
    _log_lines.append(text)


def step(num, total, title):
    out("")
    out("[%d/%d] %s" % (num, total, title))


def ok(text):
    out("      OK   " + text)


def warn(text):
    out("      !    " + text)


def err(text):
    out("      ОШИБКА  " + text)


def save_log():
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("Talker Box — setup_dev.py, %s\n\n" % time.strftime("%d.%m.%Y %H:%M:%S"))
            f.write("\n".join(_log_lines))
    except Exception:
        pass


def human(num):
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if num < 1024 or unit == "ГБ":
            return ("%.0f %s" % (num, unit)) if unit == "Б" else ("%.1f %s" % (num, unit))
        num /= 1024.0
    return "%.1f ГБ" % num


# ---------------------------------------------------------------- python / venv

def check_python():
    v = sys.version_info
    out("Python: %d.%d.%d  (%s)" % (v.major, v.minor, v.micro, sys.executable))
    if v < (3, 12):
        err("нужен Python 3.12 или новее, запущен %d.%d" % (v.major, v.minor))
        return False
    if v[:2] != (3, 13):
        warn("проект проверен на Python 3.13; у вас %d.%d — обычно работает, но при ошибках ставьте 3.13" %
            (v.major, v.minor))
    return True


def venv_python_works():
    if not os.path.exists(VENV_PY):
        return False
    try:
        r = subprocess.run([VENV_PY, "-c", "import sys; print(sys.version_info[:2])"],
                           capture_output=True, timeout=60)
        return r.returncode == 0
    except Exception:
        return False


def ensure_venv(check_only):
    if venv_python_works():
        ok("venv на месте: %s" % VENV)
        return True
    if check_only:
        err("venv отсутствует или сломан — запустите скрипт без --check")
        return False

    if os.path.exists(VENV):
        broken = VENV + "_broken"
        if os.path.exists(broken):
            import shutil
            shutil.rmtree(broken, ignore_errors=True)
        warn("старое окружение не работает — переименовываю в %s" % os.path.basename(broken))
        try:
            os.rename(VENV, broken)
        except Exception as e:
            err("не удалось убрать старый venv (%s); удалите папку venv вручную" % e)
            return False

    out("      создаю venv (это ~10 секунд)...")
    try:
        r = subprocess.run([sys.executable, "-m", "venv", VENV],
                           capture_output=True, text=True, errors="replace", timeout=600)
    except Exception as e:
        err("venv не создан: %s" % e)
        return False
    if r.returncode != 0 or not os.path.exists(VENV_PY):
        err("venv не создан: %s" % ((r.stderr or r.stdout or "").strip()[-500:]))
        return False
    ok("venv создан")
    return True


def probe(venv_py):
    """Список (модуль, пакет, версия|None) — что реально импортируется в venv."""
    code = (
        "import json, importlib\n"
        "mods = %r\n"
        "res = []\n"
        "for mod, pkg in mods:\n"
        "    try:\n"
        "        importlib.import_module(mod)\n"
        "        ver = None\n"
        "        try:\n"
        "            from importlib.metadata import version\n"
        "            ver = version(pkg)\n"
        "        except Exception:\n"
        "            pass\n"
        "        res.append([mod, pkg, ver])\n"
        "    except Exception as e:\n"
        "        res.append([mod, pkg, None])\n"
        "print(json.dumps(res, ensure_ascii=False))\n"
    ) % (PACKAGES,)
    try:
        r = subprocess.run([venv_py, "-c", code], capture_output=True, text=True, errors="replace", timeout=180)
        if r.returncode != 0:
            return [(m, p, None) for m, p in PACKAGES]
        return [tuple(x) for x in json.loads(r.stdout.strip().splitlines()[-1])]
    except Exception:
        return [(m, p, None) for m, p in PACKAGES]


def install_requirements(check_only):
    if not os.path.exists(REQ_FILE):
        err("нет файла requirements.txt")
        return False
    cmd = [VENV_PY, "-m", "pip", "install", "-r", REQ_FILE,
           "--disable-pip-version-check", "--no-input"]
    out("      pip install -r requirements.txt ...")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=3600)
    except Exception as e:
        err("pip не запустился: %s" % e)
        return False
    tail = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-6:]
    if r.returncode != 0:
        err("pip вернул ошибку %d" % r.returncode)
        for line in tail:
            out("        " + line)
        out("        Подсказка: повторите запуск (иногда обрывается канал) или включите VPN.")
        return False
    for line in tail:
        if line.strip():
            out("        " + line.strip())
    return True


# ---------------------------------------------------------------- model

def model_file_ok(name, expected, strict=False):
    path = os.path.join(MODEL_DIR, name)
    if not os.path.exists(path):
        return False, "нет файла"
    size = os.path.getsize(path)
    if size >= expected:
        return True, human(size)
    if size >= expected * 0.5 and not strict:
        return True, human(size) + " (меньше ожидаемого)"
    return False, human(size)


def download(url, dest, expected=None):
    part = dest + ".part"
    for attempt in (1, 2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "TalkerBox-setup"})
            with urllib.request.urlopen(req, timeout=90) as resp, open(part, "wb") as f:
                total = int(resp.headers.get("Content-Length") or 0) or expected or 0
                done = 0
                while True:
                    chunk = resp.read(1024 * 512)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if _tty and total:
                        sys.stdout.write("\r        %s / %s  %d%%      " %
                                         (human(done), human(total), int(done * 100 / total)))
                        sys.stdout.flush()
            if _tty:
                sys.stdout.write("\r" + " " * 60 + "\r")
            if os.path.getsize(part) == 0:
                raise IOError("пустой ответ")
            os.replace(part, dest)
            return True, None
        except Exception as e:
            try:
                if os.path.exists(part):
                    os.remove(part)
            except Exception:
                pass
            if attempt == 1:
                out("      повтор после ошибки: %s" % e)
                time.sleep(2)
            else:
                return False, str(e)
    return False, "неизвестная ошибка"


def ensure_model(check_only, allow_download):
    missing = []
    for name, expected in MODEL_FILES.items():
        good, info = model_file_ok(name, expected)
        if good:
            ok("%s  %s" % (name, info))
        else:
            warn("%s  %s" % (name, info))
            missing.append(name)

    if not missing:
        return True
    if check_only or not allow_download:
        err("модель неполная (%d из %d файлов) — запустите скрипт без --check/--no-model"
            % (len(MODEL_FILES) - len(missing), len(MODEL_FILES)))
        return False

    os.makedirs(MODEL_DIR, exist_ok=True)
    out("      скачиваю модель с HuggingFace (~221 МБ, один раз)...")
    for name in missing:
        url = MODEL_REPO + name
        dest = os.path.join(MODEL_DIR, name)
        out("      → %s" % name)
        good, error = download(url, dest, MODEL_FILES[name])
        if not good:
            err("не скачалось: %s (%s)" % (name, error))
            out("        Проверьте интернет/VPN. Файл можно скачать вручную: %s" % url)
            return False
        size = os.path.getsize(dest)
        if size < MODEL_FILES[name] * 0.9:
            err("файл %s подозрительно мал (%s)" % (name, human(size)))
            return False
        ok("%s  %s" % (name, human(size)))
    return True


# ---------------------------------------------------------------- files

def ensure_files():
    missing = [a for a in ASSETS if not os.path.exists(os.path.join(ROOT, a.replace("/", os.sep)))]
    if missing:
        err("не хватает файлов проекта: %s" % ", ".join(missing))
        out("        Похоже, папка скопирована не полностью — обновите её через git pull.")
        return False
    ok("файлы проекта на месте (%d)" % len(ASSETS))

    vocab = os.path.join(ROOT, "vocabularies")
    os.makedirs(vocab, exist_ok=True)
    dict_file = os.path.join(vocab, "Словарь.txt")
    if not os.path.exists(dict_file):
        try:
            with open(dict_file, "w", encoding="utf-8") as f:
                f.write(DICT_TEMPLATE)
            ok("создан пустой словарь vocabularies\\Словарь.txt")
        except Exception as e:
            warn("не удалось создать словарь: %s" % e)
    else:
        ok("словарь vocabularies\\Словарь.txt на месте")
    return True


def compile_sources():
    src = os.path.join(ROOT, "src")
    files = []
    for base, _dirs, names in os.walk(src):
        if "__pycache__" in base:
            continue
        for name in names:
            if name.endswith(".py"):
                files.append(os.path.join(base, name))
    if not files:
        err("в src нет .py файлов")
        return False
    try:
        r = subprocess.run([VENV_PY, "-m", "py_compile"] + files,
                           capture_output=True, text=True, errors="replace", timeout=300)
    except Exception as e:
        err("py_compile не запустился: %s" % e)
        return False
    if r.returncode != 0:
        err("ошибки компиляции:")
        for line in (r.stderr or "").strip().splitlines()[-10:]:
            out("        " + line)
        return False
    ok("%d модулей компилируются" % len(files))
    return True


def smoke_model():
    """Минимальная проверка: модель реально грузится sherpa-onnx (без микрофона)."""
    code = (
        "import os, sherpa_onnx\n"
        "d = %r\n"
        "rec = sherpa_onnx.OfflineRecognizer.from_transducer(\n"
        "    encoder=os.path.join(d, 'encoder.int8.onnx'),\n"
        "    decoder=os.path.join(d, 'decoder.onnx'),\n"
        "    joiner=os.path.join(d, 'joiner.onnx'),\n"
        "    tokens=os.path.join(d, 'tokens.txt'),\n"
        "    model_type='nemo_transducer', feature_dim=64, num_threads=2)\n"
        "print('loaded')\n"
    ) % (MODEL_DIR,)
    try:
        r = subprocess.run([VENV_PY, "-c", code], capture_output=True, text=True, errors="replace", timeout=300)
    except Exception as e:
        warn("проверка загрузки модели пропущена: %s" % e)
        return True
    if r.returncode != 0:
        err("sherpa-onnx не смог загрузить модель:")
        for line in (r.stderr or "").strip().splitlines()[-6:]:
            out("        " + line)
        return False
    ok("sherpa-onnx загружает модель GigaAM")
    return True


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description="Установка окружения Talker Box (dev-версия)")
    parser.add_argument("--check", action="store_true", help="только проверить, ничего не менять")
    parser.add_argument("--run", action="store_true", help="запустить программу после установки")
    parser.add_argument("--no-model", action="store_true", help="не скачивать модель")
    args = parser.parse_args()

    _setup_console()
    total = 7
    out("=" * 62)
    out("  Talker Box — установка окружения для dev-версии")
    out("  папка проекта: %s" % ROOT)
    out("  режим: %s" % ("только проверка" if args.check else "установка"))
    out("=" * 62)

    problems = []

    step(1, total, "Python")
    if not check_python():
        problems.append("Python слишком старый")

    step(2, total, "Виртуальное окружение venv")
    if not ensure_venv(args.check):
        problems.append("venv")
        finish(problems)
        return 1

    step(3, total, "Пакеты (requirements.txt)")
    state = probe(VENV_PY)
    missing = [pkg for _mod, pkg, ver in state if ver is None]
    if missing:
        warn("не хватает: %s" % ", ".join(missing))
        if args.check:
            problems.append("пакеты: " + ", ".join(missing))
        elif not install_requirements(args.check):
            problems.append("pip install")
        else:
            state = probe(VENV_PY)
            missing = [pkg for _mod, pkg, ver in state if ver is None]
            if missing:
                problems.append("пакеты после установки: " + ", ".join(missing))
            else:
                ok("все пакеты установлены")
    else:
        ok("все пакеты уже стоят")
    for _mod, pkg, ver in state:
        ok("%-16s %s" % (pkg, ver or "НЕ УСТАНОВЛЕН"))

    step(4, total, "Модель распознавания GigaAM")
    if not ensure_model(args.check, allow_download=not args.no_model):
        problems.append("модель GigaAM")

    step(5, total, "Файлы проекта и словарь")
    if not ensure_files():
        problems.append("файлы проекта")

    step(6, total, "Компиляция модулей")
    if not compile_sources():
        problems.append("компиляция")

    step(7, total, "Проверка загрузки модели")
    if not problems and not smoke_model():
        problems.append("загрузка модели")

    code = finish(problems)
    if code == 0 and (args.run or (not args.check and _ask_run())):
        launch()
    save_log()
    return code


def finish(problems):
    out("")
    out("=" * 62)
    if problems:
        out("  ЕСТЬ ПРОБЛЕМЫ:")
        for p in problems:
            out("   - " + p)
        out("")
        out("  Лог: %s" % LOG_FILE)
        out("=" * 62)
        save_log()
        return 1
    out("  ГОТОВО. Окружение рабочее, можно запускать dev-версию.")
    out("  Запуск: start.bat  (или venv\\Scripts\\pythonw.exe src\\main.py)")
    out("  Лог: %s" % LOG_FILE)
    out("=" * 62)
    save_log()
    return 0


def _ask_run():
    if not sys.stdin or not sys.stdin.isatty():
        return False
    try:
        answer = input("\nЗапустить Talker Box сейчас? [y/N]: ").strip().lower()
    except Exception:
        return False
    return answer in ("y", "yes", "д", "да")


def launch():
    out("")
    out("Запускаю Talker Box...")
    # pythonw — без лишнего чёрного окна, логи всё равно пишутся в talkerbox.log
    py = os.path.join(VENV, "Scripts", "pythonw.exe")
    if not os.path.exists(py):
        py = VENV_PY
    try:
        subprocess.Popen([py, os.path.join("src", "main.py")], cwd=ROOT)
    except Exception as e:
        err("не удалось запустить: %s" % e)


if __name__ == "__main__":
    sys.exit(main())
