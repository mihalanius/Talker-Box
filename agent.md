# Talker Box — Инструкция для агента

> **✅ Версия v2.0 — текущая версия.**  
> GigaAM зашита как единственная модель, выбор моделей удалён.

## Обзор проекта

**Talker Box** — десктопное приложение для голосового ввода текста (push-to-talk). 
  Пользователь зажимает горячую клавишу → говорит → отпускает → текст распознаётся и вставляется в активное окно через буфер обмена + SendInput.

**Стек:** Python 3.13.15, PyQt6, sherpa-onnx (GigaAM v3 trans-punct, 220 МБ), sounddevice, pyperclip  
**Платформа:** Windows 10/11  
**Пользователь:** GOLDMAN, работает в cTrader, Node.js, C# WinForms  
**GitHub:** https://github.com/mihalanius/Talker-Box.git

---

## Ключевые файлы

| Файл | Назначение |
|------|-----------|
| `src/main.py` | Главное окно, UI, запись, распознавание, вставка текста, tray |
| `src/hotkey_hook.py` | In-process WH_KEYBOARD_LL хук — горячая клавиша, подавление клавиш |
| `src/recorder.py` | Запись аудио через sounddevice |
| `src/transcriber.py` | Загрузка моделей sherpa-onnx, распознавание |
| `src/logger.py` | Логирование в `talkerbox.log` + stdout |
| `src/settings_manager.py` | Чтение/запись `settings.json`, BUILTIN_MODEL |
| `src/waveform.py` | Индикатор записи |
| `src/sounds.py` | Звуки старта/остановки записи |
| `src/ad_manager.py` | Рекламный баннер (отключён, высота 0) |
| `help.html` | HTML-руководство пользователя |
| `settings.json` | Конфигурация: hotkey, mode |
| `build.bat` | PyInstaller сборка + копирование модели в dist |

---

## Текущая конфигурация (v2.0)

```json
{
  "hotkey": "ctrl+win",
  "mode": "hold",
  "auto_send": true,
  "auto_start": true,
  "minimize_to_tray": true
}
```

**Модель зашита в программу:** GigaAM v3 trans-punct  
**Путь модели в dist:** `models/GigaAM/` (рядом с exe)  
**Путь модели при dev:** `D:\OpenCode_Arhive\Voice models\GigaAM v3 trans-punct (220 Mb)`  
**Файлы модели:** `encoder.int8.onnx`, `decoder.onnx`, `joiner.onnx`, `tokens.txt`

---

## Что изменилось в v2.0

- Удалена поддержка Vosk и Whisper моделей
- Удалён UI выбора моделей (кнопка "Сменить Модель", лейбл с названием)
- GigaAM зашита как единственная модель через `BUILTIN_MODEL` в settings_manager.py
- `load_active_model()` загружает только встроенную модель из `models/GigaAM/` рядом с exe
- Удалены методы: `_load_new_model()`, `_detect_model_type()`, `_update_model_label()`, `show_models()`
- Удалены: `_load_whisper()`, `_transcribe_whisper()`, `_load_vosk()`, `_transcribe_vosk()` из transcriber.py
- `build.bat` копирует GigaAM модель в `dist/TalkerBox/models/GigaAM/`
- Установщик включает модель (220 МБ)

---

## Архитектура горячей клавиши

### Текущая реализация: In-process WH_KEYBOARD_LL hook

```
main.py → hotkey_hook.py (HotkeyListener)
         → SetWindowsHookExA(WH_KEYBOARD_LL) в отдельном потоке
         → GetMessageW loop
         → callback("DOWN"/"UP")
         → QTimer.singleShot в main.py
```

**hotkey_hook.py:**
- `HotkeyListener` — класс с WH_KEYBOARD_LL хуком
- `parse_hotkey()` — парсит строки типа `ctrl+win`, `f9`, `ctrl+shift`
- `start_capture(callback)` — QTimer-based захват горячей клавиши
- `stop()` — unhooks directly

**Ключевые находки:**
- `CFUNCTYPE`: `ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_int, wintypes.WPARAM, ctypes.c_void_p)`
- `CallNextHookEx` lParam: передавать `ctypes.c_void_p(lParam)` для избежания OverflowError
- `GetMessageW` обязателен для WH_KEYBOARD_LL — `MsgWaitForMultipleObjects` НЕ работает
- Подпроцесс с CREATE_NO_WINDOW блокирует хуки — хук должен работать in-process
- Win key перехватывается ОС — Qt `keyPressEvent` его не видит
- Ctrl+Win: ОС генерирует синтетические UP events — fix: подавлять ALL key DOWN пока combo активно

### Режимы работы

- **Hold** (по умолчанию): запись пока зажата клавиша, стоп при отпускании
- **Toggle**: одно нажатие — старт, следующее — стоп

---

## Загрузка модели (v2.0)

### Встроенная модель

- Определена в `settings_manager.py` как `BUILTIN_MODEL`
- Путь: `models/GigaAM/` относительно exe (в dev — полный путь)
- Тип: `sherpa-onnx` (NeMo transducer)

### Загрузка sherpa-onnx (`_load_sherpa_onnx`)

1. Ищет tokens.txt в корне и подпапках
2. Ищет encoder/decoder/joint по шаблонам
3. Пробует загрузить как NeMo transducer (с `model_type="nemo_transducer"`)
4. Если ошибка — пробует стандартный transducer (для Zipformer)
5. Если нет joint/joiner — пробует CTC (model.onnx + tokens)

### Обработка ошибок

- **При старте:** если модель не загрузилась → программа запускается без распознавания
- **При распознавании:** ловит исключения, пишет в лог

---

## UI (v2.0)

### Цветовая схема
- Основной фон: градиент `#0a1628` (сверху) → `#1a1a2e` (снизу)
- Акцент 1: `#00ff88` (зелёный неон)
- Акцент 2: `#00f7ff` (голубой неон)
- Текст: `#eee`
- Фон элементов: `#16213e`

### Компоненты
- **Звёзды** — `StarsWidget`: 50 мерцающих точек, анимация через QTimer
- **Неоновые линии** — `_paint_neon_line()`: fade-эффект по краям
- **Чекбокс** — `NeonCheckBox`: кастомный, квадратный с галочкой
- **Кнопки** — `QPushButton` с неоновым стилем
- **ComboBox** — неоновый стиль для выбора режима
- **Справка** — `help.html`, открывается через webbrowser

### Структура окна
1. Неоновая линия сверху
2. Подсказка (текст без рамки, прозрачный фон — звёзды видны)
3. Неоновая линия
4. Настройки (Режим, Авто-отправка, Горячая клавиша)
5. Неоновые линии + версия + справка

---

## Доступные модели (зашиты в установщик)

| Модель | Размер | Язык | Тип |
|--------|--------|------|-----|
| GigaAM v3 trans-punct | 220 MB | Русский + транскрипция + пунктуация | sherpa-onnx (NeMo) |

**Ссылки:**
- GigaAM v3: https://huggingface.co/csukuangfj/sherpa-onnx-nemo-transducer-punct-giga-am-v3-russian-2025-12-16
- Все модели sherpa-onnx: https://github.com/k2-fsa/sherpa-onnx/releases/tag/asr-models
- Модели Vosk (устарели): https://alphacephei.com/vosk/models

---

## Среда

- **OS:** Windows 10/11
- **Python:** 3.13.15 (`C:\Program Files\Python313\`)
- **pip пакеты:** PyQt6, sounddevice, numpy, pyperclip, sherpa-onnx>=1.13.0, pyWin32
- **Git:** `https://github.com/mihalanius/Talker-Box.git`
- **Рабочая папка:** `D:\OpenCode_Arhive\Talker Box\`
- **Модели (dev):** `D:\OpenCode_Arhive\Voice models\`
- **Inno Setup:** `C:\Program Files (x86)\Inno Setup 6\ISCC.exe`
- **Установщик:** `installer\Output\TalkerBoxSetup.exe`

---

## Правила работы

1. **Не показывать todo списки в чате** — замерзают и висят
2. **Не переименовывать файлы/проект** во время работы — ломает пути/импорты
3. **Python:** `C:\Program Files\Python313\python.exe` — НЕ в PATH, использовать полный путь
4. **Сборка:** `build.bat` → PyInstaller → `dist/TalkerBox/` → ISCC → `installer/Output/`
5. **Коммиты:** На GitHub (`https://github.com/mihalanius/Talker-Box.git`)
6. **Когда менять дизайн** — если что-то сломалось, откатиться на `git checkout v1.18`
7. **Писать только на русском** — пользователь просил
8. **Модель зашита** — выбор моделей в UI нет, только GigaAM

---

## Git история

| Тег | Описание |
|-----|----------|
| v2.0 | Удалена поддержка Vosk/Whisper, GigaAM зашита как единственная модель |
| v1.18 | Whisper detection fix, скачены Parakeet v2/v3 |
| v1.17 | Исправлены пути для PyInstaller,.autostart, иконка, звуки, справка |
| v1.16 | Стабильная версия с выбором моделей |
