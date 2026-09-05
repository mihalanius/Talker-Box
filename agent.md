# Talker Box — Инструкция для агента

> **✅ Версия v1.16 — стабильная рабочая версия.**  
> Следующее изменение: v2.0.

## Обзор проекта

**Talker Box** — десктопное приложение для голосового ввода текста (push-to-talk). 
  Пользователь зажимает горячую клавишу → говорит → отпускает → текст распознаётся и вставляется в активное окно через буфер обмена + SendInput.

**Стек:** Python 3.13.15, PyQt6, sherpa-onnx (GigaAM v3 trans-punct, 225 МБ, int8), sounddevice, pyperclip  
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
| `src/transcriber.py` | Универсальная загрузка моделей (sherpa-onnx/whisper/vosk), распознавание |
| `src/logger.py` | Логирование в `talkerbox.log` + stdout |
| `src/settings_manager.py` | Чтение/запись `settings.json` |
| `src/waveform.py` | Индикатор записи |
| `src/sounds.py` | Звуки старта/остановки записи |
| `src/ad_manager.py` | Рекламный баннер (отключён, высота 0) |
| `help.html` | HTML-руководство пользователя |
| `settings.json` | Конфигурация: hotkey, mode, model path |
| `build.bat` | PyInstaller сборка |

---

## Текущая конфигурация

```json
{
  "hotkey": "win+ctrl",
  "mode": "hold",
  "auto_send": true,
  "active_model": "GigaAM v3 trans-punct (220 Mb)",
  "models": [{
    "name": "GigaAM v3 trans-punct (220 Mb)",
    "path": "D:/OpenCode_Arhive/Voice models/GigaAM v3 trans-punct (220 Mb)",
    "type": "sherpa-onnx",
    "language": "ru",
    "size": ""
  }]
}
```

**Модель по умолчанию:** GigaAM v3 trans-punct  
**Файлы модели:** `encoder.int8.onnx`, `decoder.onnx`, `joiner.onnx`, `tokens.txt`

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

## Универсальная загрузка моделей

### Поддерживаемые типы

| Тип | Определение | Пример |
|-----|-------------|--------|
| `sherpa-onnx` | encoder+decoder+joint или onnx+tokens | GigaAM, Zipformer |
| `vosk` | final.mdl или am/conf/graph | vosk-model-small-en-us |
| `whisper` | *-encoder.onnx + *-decoder.onnx + *-tokens.txt | sherpa-onnx-whisper-tiny |

### Автоопределение типа (`_detect_model_type`)

1. Сначала проверяет whisper (`*-encoder.onnx`, `*-decoder.onnx`)
2. Затем sherpa-onnx (encoder/decoder/joint/onnx + tokens)
3. Затем vosk (final.mdl или am/conf/graph)
4. Если ничего не подошло → `unknown`

### Загрузка sherpa-onnx (`_load_sherpa_onnx`)

1. Ищет tokens.txt (или *-tokens.txt) в корне и подпапках
2. Ищет encoder/decoder/joint по шаблонам
3. Пробует загрузить как NeMo transducer (с `model_type="nemo_transducer"`)
4. Если ошибка — пробует стандартный transducer (для Zipformer)
5. Если нет joint/joiner — пробует CTC (model.onnx + tokens)

### Обработка ошибок

- **При старте:** если модель не загрузилась → программа запускается без распознавания
- **При загрузке:** показывает диалог ошибки с описанием
- **При распознавании:** ловит исключения, пишет в лог

---

## UI (v1.16)

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
5. Модели (название + кнопка "Сменить Модель")
6. Неоновые линии + версия + справка

---

## Доступные модели

| Модель | Размер | Язык | Тип |
|--------|--------|------|-----|
| GigaAM v3 trans-punct | 220 MB | Русский | sherpa-onnx (NeMo) |
| GigaAM v2 transducer | 230 MB | Русский | sherpa-onnx (NeMo) |
| Zipformer Rus | 255 MB | Русский | sherpa-onnx (стандартный) |
| vosk-model-small-en-us | 45 MB | Английский | vosk |
| Vosk English mobile | 67 MB | Английский | vosk |
| Vosk Ru | 87 MB | Русский | vosk |

**Ссылки:**
- GigaAM v3: https://huggingface.co/csukuangfj/sherpa-onnx-nemo-transducer-punct-giga-am-v3-russian-2025-12-16
- Все модели sherpa-onnx: https://github.com/k2-fsa/sherpa-onnx/releases/tag/asr-models


---

## Правила работы

1. **Не показывать todo списки в чате** — замерзают и висят
2. **Не переименовывать файлы/проект** во время работы — ломает пути/импорты
3. **Python:** `C:\Program Files\Python312\python.exe` — НЕ в PATH, использовать полный путь
4. **Сборка:** `build.bat` → PyInstaller → `dist/TalkerBox/`
5. **Коммиты:** На GitHub (`https://github.com/mihalanius/Talker-Box.git`)
6. **Когда менять дизайн** — если что-то сломалось, откатиться на `git checkout v1.16`
7. **Писать только на русском** — пользователь просил

---

## Среда

- **OS:** Windows 10/11
- **Python:** 3.12.7 (`C:\Program Files\Python312\`)
- **pip пакеты:** PyQt6, sounddevice, numpy, pyperclip, onnxruntime, sherpa-onnx v1.13.7, vosk, pyWin32
- **Git:** `https://github.com/mihalanius/Talker-Box.git`
- **Рабочая папка:** `D:\OpenCode_Arhive\Talker Box\`
- **Модели:** `D:\OpenCode_Arhive\Voice models\`
