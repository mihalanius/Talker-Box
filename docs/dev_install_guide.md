# Talker Box — установка окружения для dev-версии

Инструкция для запуска **dev-версии** из исходников на чистом Windows 10/11 (64-bit):
что поставить, в каком порядке, как проверить и что делать, если не запускается.

Готовый установщик (`TalkerBoxSetup.exe`) это НЕ требует — там всё внутри. Здесь — только
запуск из папки проекта через `start.bat`.

> HTML-версия этой инструкции (для чтения в браузере): `docs\dev_install_guide.html`

---

## Короткий чек-лист

1. Python **3.13** (64-bit) → установить
2. Visual C++ Redistributable 2015–2022 (x64) → обычно уже есть, проверить
3. Папка проекта с исходниками
4. Модель `models\GigaAM` (220 МБ, 4 файла) на месте
5. `setup.bat` — создаёт `venv` и ставит пакеты (один раз)
6. `start.bat` — запуск

---

## 1. Python 3.13

Скачать: <https://www.python.org/downloads/windows/> — **Windows installer (64-bit)**, версия 3.13
(на эталонной машине — 3.13.15).

При установке:

- галочка **Add python.exe to PATH** — можно поставить (удобнее), но `setup.bat` её не требует:
  он сам ищет Python в `%LOCALAPPDATA%\Programs\Python\Python313` и `C:\Program Files\Python313`;
- **Install launcher for all users** — можно оставить по умолчанию.

Проверка (открыть «Командную строку»):

```bat
py -3.13 -V
```

Ожидаемо: `Python 3.13.x`. Если `py` не найден — проверить полный путь:

```bat
"%LOCALAPPDATA%\Programs\Python\Python313\python.exe" -V
```

> Python 3.12 рядом не мешает — `setup.bat` ищет именно 3.13. Проект проверен на 3.13.15.

## 2. Visual C++ Redistributable

Нужен для PyQt6 и sherpa-onnx. Лучше поставить заранее:
<https://aka.ms/vs/17/release/vc_redist.x64.exe>

Если он уже стоит, установщик просто предложит «Repair / Uninstall» — можно закрыть.

## 3. Папка проекта

Вариант А (с историей git):

```bat
git clone https://github.com/mihalanius/Talker-Box.git "D:\OpenCode_Arhive\Talker Box"
```

Вариант Б — скопировать папку проекта целиком (с `src\`, `installer\`, `fonts\`, `sounds\`).

Путь с пробелами (`D:\OpenCode_Arhive\Talker Box`) работает — все батники используют `%~dp0`
и `cd /d`, поэтому запускать их можно откуда угодно.

> **Не нужно** копировать `venv\`, `dist\`, `__pycache__\`, `build\` — это создаётся заново.
> Но и мешать они не будут.

## 4. Модель распознавания GigaAM

Без модели программа запустится, но распознавать не будет (в логе — `MODEL_ERROR`).

Нужна папка **`models\GigaAM`** в корне проекта с четырьмя файлами:

| Файл | Размер |
|---|---|
| `encoder.int8.onnx` | ~224 МБ |
| `decoder.onnx` | ~4,6 МБ |
| `joiner.onnx` | ~2,7 МБ |
| `tokens.txt` | ~13 КБ |

Скачать: <https://huggingface.co/csukuangfj/sherpa-onnx-nemo-transducer-punct-giga-am-v3-russian-2025-12-16>

Раскладка в итоге:

```
Talker Box\
├─ models\
│  └─ GigaAM\
│     ├─ encoder.int8.onnx
│     ├─ decoder.onnx
│     ├─ joiner.onnx
│     └─ tokens.txt
├─ src\
├─ venv\            ← создаст setup.bat
├─ setup.bat
└─ start.bat
```

Проверка из папки проекта:

```bat
dir models\GigaAM
```

Должны быть видны ровно эти четыре файла (остальные из архива модели не обязательны).

## 5. Установка пакетов: `setup.bat`

Двойной клик по **`setup.bat`** в папке проекта. Что он делает:

1. ищет Python 3.13 (перебор известных путей → `where python`);
2. если `venv\` нет — создаёт виртуальное окружение `venv` **на этом Python**;
3. обновляет `pip` и ставит пакеты из `requirements.txt`;
4. пишет `Setup complete. Run start.bat to launch.` и ждёт нажатия клавиши.

Важно: пакеты ставятся **внутрь `venv`**, система не засоряется. `venv` привязан к конкретному
Python — если Python переустановить или удалить, `venv` перестанет работать (лечится удалением
папки `venv` и повторным `setup.bat`).

### Что должно стоять после setup.bat

Проверка:

```bat
venv\Scripts\python.exe -m pip list
```

Ожидаемые пакеты (версии — эталонные, допускаются более новые):

| Пакет | Версия | Зачем |
|---|---|---|
| PyQt6 (+ PyQt6-Qt6, PyQt6-sip) | 6.11.0 / 6.11.2 / 13.13.0 | интерфейс программы |
| sounddevice | 0.5.6 | запись с микрофона (PortAudio внутри пакета) |
| numpy | 2.5.4 | обработка аудио |
| sherpa-onnx (+ sherpa-onnx-core) | 2.0.0 | распознавание речи GigaAM |
| comtypes | 1.4.17 | UI Automation — позиция каретки для облачка |
| pywin32-ctypes | 0.2.3 | Win32 API (хук клавиатуры, SendInput) |
| pyperclip | 1.11.0 | остался с ранних версий, в работе не используется |

Плюс `pyinstaller` — он ставится не в `setup.bat`, а в `build.bat` (только для сборки exe).

### Установка вручную (если не хочется батника)

Из папки проекта:

```bat
"%LOCALAPPDATA%\Programs\Python\Python313\python.exe" -m venv venv
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
```

Это ровно то же, что делает `setup.bat`.

## 6. Запуск

```bat
start.bat
```

`start.bat` проверяет наличие `venv` (если нет — сам вызовет `setup.bat`) и запускает
`venv\Scripts\python.exe src\main.py`. Окно консоли остаётся открытым — это нормально, туда
пишутся логи.

Запуск без чёрного окна консоли:

```bat
venv\Scripts\pythonw.exe src\main.py
```

При старте в логе должно быть:

```
MIC_SELECTED | (системный по умолчанию) -> device=None
MODEL_LOADED | GigaAM v3 trans-punct
```

Модель грузится ~2–5 секунд. Дальше — программа в трее, горячая клавиша по умолчанию `Ctrl+Win`.

---

## 7. Если не запускается

**`ERROR: Python 3.13 not found`** — Python не установлен в стандартный путь. Проверить:

```bat
where python
```

Если находит 3.12 или ничего — переустановить 3.13 из python.org (или в `setup.bat` вписать свой путь).

**`'python' is not recognized`** — Python не в PATH. Это не мешает `start.bat`, но для команд
вручную используйте полный путь `"%LOCALAPPDATA%\Programs\Python\Python313\python.exe"`.

**Ошибка при `pip install` (таймаут, обрыв)** — плохой канал. Повторить `setup.bat`; при
повторяющихся обрывах поставить зеркало:

```bat
venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.org/simple --timeout 60 --retries 10
```

**`ImportError: DLL load failed` при старте** (PyQt6, sherpa-onnx) — не установлен
Visual C++ Redistributable x64 (пункт 2), либо стоит 32-битный Python. Нужен 64-bit.

**Программа открылась, но текст не распознаётся** — нет модели: проверить `models\GigaAM`
(все 4 файла), в логе `talkerbox.log` искать `MODEL_ERROR` / `MODEL_LOADED`.

**В логе `MODEL_ERROR` при наличии файлов** — модель повреждена при скачивании (проверить
размер `encoder.int8.onnx` ≈ 224 МБ, при обрыве он будет меньше).

**Микрофон молчит** — Настройки → строка «Микрофон» → выбрать устройство; в Windows
«Параметры → Конфиденциальность → Микрофон» разрешить доступ приложениям.

**Горячая клавиша не срабатывает** — в трее уже висит старая копия Talker Box (хук занимает
комбинацию). Диспетчер задач → завершить все `TalkerBox.exe` / `python.exe` / `pythonw.exe`
с этим проектом, запустить заново. Если не помогает — запускать не от имени администратора
(хук клавиатуры в другом уровне целостности не видит нажатий).

**`venv` сломался после переустановки Python** (`Fatal error in launcher`, пустой `pip list`) —
удалить папку `venv` и запустить `setup.bat` заново.

**Кракозябры в консоли** (`MIC_SELECTED | (����...`) — это кодировка консоли, на работу не влияет.
Записи в `talkerbox.log` пишутся в UTF-8 корректно.

---

## 8. Файлы, которые создаются при работе (в папке проекта)

| Файл | Что это |
|---|---|
| `settings.json` | настройки программы (хоткей, режим, цвета облачка, микрофон) |
| `talkerbox.log` | лог событий и распознавания |
| `src\crash.log` | traceback, если программа падала |
| `history.txt` | история сеансов распознавания (вкладка «История») |
| `vocabularies\Словарь.txt` (+ `.bak`) | словарь замен слов (вкладка «Словарь») |

Всё это рабочие данные — их можно удалять по одному, программа создаст заново.

## 9. Обновление проекта

```bat
git pull
```

Если менялся `requirements.txt` — повторить `setup.bat`. Дальше обычный `start.bat`.
Сборка установщика — `build.bat` (PyInstaller-часть) и затем `ISCC.exe installer\talkerbox.iss`.

## 10. Требования к машине

- Windows 10/11, 64-bit
- ~700 МБ свободного места (`venv` ~340 МБ + модель 221 МБ)
- 4 ГБ ОЗУ минимум (проверено на 14 ГБ; модель int8 работает на CPU, видеокарта не нужна)
- Любой микрофон (встроенный, гарнитура, USB-петличка)
