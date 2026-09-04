# Talker Box — Инструкция для агента

## Обзор проекта

**Talker Box** — десктопное приложение для голосового ввода текста (push-to-talk). Пользователь зажимает горячую клавишу → говорит → отпускает → текст распознаётся и вставляется в активное окно через буфер обмена + SendInput.

**Стек:** Python 3.12.7, PyQt6, sherpa-onnx (GigaAM v3 trans-punct, 225 МБ, int8), sounddevice, pyperclip  
**Платформа:** Windows 10/11  
**Пользователь:** GOLDMAN, работает в cTrader, Node.js, C# WinForms  

---

## Ключевые файлы

| Файл | Назначение |
|------|-----------|
| `src/main.py` (~995 строк) | Главное окно, запись, распознавание, вставка текста, tray, watchdog |
| `src/hotkey_listener.py` (123 строки) | Отдельный процесс — опрос `GetAsyncKeyState` каждые 10мс (**ПРОБЛЕМА: не подавляет клавиши**) |
| `src/recorder.py` (78 строк) | Запись аудио через sounddevice, очередь сэмплов |
| `src/transcriber.py` (160 строк) | Загрузка моделей (sherpa-onnx/whisper/vosk), распознавание |
| `src/logger.py` (18 строк) | Логирование в `talkerbox.log` + stdout |
| `src/settings_manager.py` | Чтение/запись `settings.json` |
| `src/waveform.py` | Индикатор записи (пузырь) |
| `src/sounds.py` | Звуки старта/остановки записи |
| `src/ad_manager.py` | Рекламный баннер (отключён) |
| `settings.json` | Конфигурация: hotkey, mode, model path |
| `build.bat` | PyInstaller сборка |

---

## Текущая конфигурация

```json
{
  "hotkey": "f9",
  "mode": "hold",
  "auto_send": false,
  "active_model": "GigaAM v3 trans-punct",
  "models": [{
    "name": "GigaAM v3 trans-punct",
    "path": "D:\\OpenCode_Arhive\\Voice models\\sherpa-onnx-nemo-transducer-punct-giga-am-v3-russian-2025-12-16",
    "type": "sherpa-onnx",
    "language": "ru",
    "size": "225 MB"
  }]
}
```

**Модель:** `sherpa-onnx-nemo-transducer-punct-giga-am-v3-russian-2025-12-16`  
**Файлы модели:** `encoder.int8.onnx`, `decoder.onnx`, `joiner.onnx`, `tokens.txt`  
**Загрузка:** `sherpa_onnx.OfflineRecognizer.from_transducer()` с `model_type="nemo_transducer"`, `feature_dim=64`

---

## Архитектура горячей клавиши

### Текущая реализация: GetAsyncKeyState polling (отдельный процесс)

```
main.py → subprocess.Popen("python hotkey_listener.py <hotkey>")
         → listener печатает "KEY_DOWN"/"KEY_UP" в stdout
         → main.py читает stdout через QTimer (100мс)
         → вызывает _on_hotkey_event("DOWN"/"UP")
```

**hotkey_listener.py:**
- Парсит строку hotkey (например `ctrl+win`, `f9`, `ctrl+alt+f5`)
- Опрашивает `GetAsyncKeyState` каждые 10мс в отдельном процессе
- Печатает `KEY_DOWN`/`KEY_UP` в stdout при изменении состояния
- Отправляет `HEARTBEAT` каждые 0.5с для watchdog
- **Безопасно** — не использует хуки клавиатуры (в отличие от предыдущих версий)

**Watchdog в main.py:**
- Проверяет heartbeat каждую 1с
- Если heartbeat не пришёл 5с → перезапуск listener

### Режимы работы

- **Hold** (по умолчанию): запись пока зажата клавиша, стоп при отпускании
- **Toggle**: одно нажатие — старт, следующее — стоп

---

## Известные критические баги

### 1. RECORD_TIMEOUT срабатывает через 2-7 секунд вместо 60

**Симптом:** `QTimer.singleShot(60000, ...)` fired после 2-7с записи.  
**Лог-пример:**
```
[19:33:42.806] RECORDER_STARTED
[19:33:45.190] RECORD_TIMEOUT | 60s limit reached  ← прошло 2.4с, не 60с!
```

**Что пробовалось:**
- `QTimer.singleShot(60000, self._force_stop_recording)` — работает непредсказуемо
- Добавлен `time.monotonic()` для замера реального времени
- Добавлена проверка `elapsed > 65` в `transcribe_audio()` — пропускать старый аудио
- **Не помогло** — таймер всё равно срабатывает рано

**Возможные причины:**
- QTimer в PyQt6 может работать некорректно с большими задержками
- Старый таймер не останавливается при новой записи (запись поверх)
- multiprocessing/subprocess может влиять на event loop

**Рекомендация:** Заменить `QTimer.singleShot` на `threading.Timer` или опрос `time.monotonic()` в отдельном потоке. Или вообще убрать таймер и положиться на ручное управление (hotkey UP/DOWN).

### 2. Win key в комбинациях открывает системное меню

**Симптом:** При использовании `ctrl+win` — Win key иногда срабатывает как одиночное нажатие → открывает меню Пуск / выбор аудиоустройств.  
**Причина:** `GetAsyncKeyState` только считывает состояние клавиши. Он НЕ подавляет системное поведение Win key. Windows видит Win нажатой и реагирует.

**Как решено в Type v2.0.0:**
1. Type использует нативный C++ `windows-key-listener.exe` который ставит **`SetWindowsHookExA(WH_KEYBOARD_LL, ...)`**
2. Хук **подавляет** клавиши — когда Ctrl+Win нажат, Win key перехватывается хуком и НЕ передаётся в Windows
3. Ключевой момент: `CallNextHookEx` вызывается ТОЛЬКО для клавищ которые НЕ входят в нашу комбинацию
4. Для modifier-only комбинаций (все клавиши — модификаторы) Type ОБЯЗАТЕЛЬНО использует нативный listener, а не Electron globalShortcut

**Строка из windowsKeyManager.js (строка 83):**
> "The native process suppresses the captured keystrokes so Win+letter shortcuts do not escape to the shell while the settings field is armed."

**Рекомендация:** Переписать `hotkey_listener.py` на использование `SetWindowsHookExA(WH_KEYBOARD_LL)` с правильным `CallNextHookEx`:
```python
def hook_proc(nCode, wParam, lParam):
    if nCode >= 0:
        vk = lParam & 0xFF
        if is_key_down(lParam):
            pressed_keys.add(vk)
            if combo_satisfied(pressed_keys):
                suppress = True  # Наша комбинация — подавляем
                return 1  # НЕ вызываем CallNextHookEx
        else:
            pressed_keys.discard(vk)
    return user32.CallNextHookEx(hook_id, nCode, wParam, lParam)  # Пропускаем
```

**ВАЖНО:** Предыдущая попытка использовать SetWindowsHookExA **убила клавиатуру** потому что НЕ вызывался CallNextHookEx. Это прерывает цепочку хуков и блокирует ВСЕ нажатия.

### 3. Garbled text — модель выдаёт мусор после нескольких записей

**Симптом:** Первые 3-5 записей работают нормально, затем модель начинает выдавать `'��?...` (битый UTF-8 / мусор).  
**Лог-пример:**
```
[19:32:55.809] TRANSCRIBE_DONE | text='...мусор...'
[19:33:04.754] TRANSCRIBE_DONE | text='...мусор...'
```

**Возможные причины:**
- Потокобезопасность: `self.recognizer` используется из разных потоков без блокировки
- Накопление состояния в recognizer (sherpa-onnx может накапливать контекст)
- Проблемы с памятью при больших записях (>10с)
- Буфер аудио повреждается при длинных записях

**Рекомендация:**
- Добавить `threading.Lock` к `self.recognizer`
- Пересоздавать recognizer периодически или после N записей
- Проверить, не повреждается ли `audio_data` перед передачей в модель

### 4. Toggle mode работает "через раз"

**Симптом:** In toggle mode, first press starts recording, second press should stop, but sometimes doesn't.  
**Причина:** Возможна гонка состояний между `_on_hotkey_event` и `stop_recording`. Hotkey UP приходит когда recording уже остановлен, или DEBOUNCE блокирует легитимные нажатия.

### 5. Hold mode — горячая клавиша не всегда отслеживает отпускание

**Симптом:** User отпускает клавишу, но `HOTKEY_UP` приходит с задержкой или не приходит до следующего нажатия.  
**Лог-пример:**
```
[19:33:42.745] HOTKEY_DOWN
[19:33:45.190] RECORD_TIMEOUT  ← recording остановлен таймером, не hotkey UP
[19:33:46.443] HOTKEY_UP  ← пришёл через 1.2с после реального отпускания
```

**Причина:** 10мс опрос может пропустить brief release, или hotkey UP блокируется `_suppress_hotkey` (который активен 300мс после вставки текста).

---

## Что уже пробовалось (и результат)

| Подход | Результат |
|--------|-----------|
| `SetWindowsHookExA` (WH_KEYBOARD_LL) без CallNextHookEx | **Убил клавиатуру** — не вызывали CallNextHookEx → прервали цепочку хуков |
| `SetWindowsHookExA` (WH_KEYBOARD_LL) С CallNextHookEx | **НЕ ПРОБОВАЛИ** — это правильный подход как в Type |
| `RegisterHotKey` в Python | Ненадёжно — не ловит UP events, не работает с some combos |
| `GetAsyncKeyState` polling (текущее) | Работает, но Win key проблема + premature timeout |
| `QTimer.singleShot(60000)` | Срабатывает рано (2-7с вместо 60с) |
| `time.monotonic()` в transcribe_audio | Помогает пропускать stale audio, но не решает timeout |
| Watchdog (heartbeat) | Работает — перезапускает listener при зависании |
| Очередь с `get_nowait()` | Убирает блокировку main thread |
| Звуки старта/остановки | Работают |
| Стрижка `{}` `[]` из вывода | Работает, но не решает garbled text |

---

## Сравнение с "Type v2.0.0" (конкурент)

**Type** — Electron приложение с нативным C++ hotkey exe.  
**Архитектура Type (извлечена из app.asar):**

1. **Hotkey:** По умолчанию `Control+Super` (modifier-only)
2. **Определение:** `isModifierOnlyHotkey()` проверяет что ВСЕ части — модификаторы
3. **Для modifier-only:** Запускает нативный `windows-key-listener.exe` (НЕ Electron globalShortcut)
4. **C++ бинарник:** Ставит `SetWindowsHookExA(WH_KEYBOARD_LL)` с **подавлением клавиш**
5. **Подавление:** Win key перехватывается хуком → Windows НЕ видит → меню НЕ открывается
6. **State machine:** `MIN_HOLD_DURATION_MS = 150ms` debounce
7. **События:** `KEY_DOWN`/`KEY_UP` через stdout → `WindowsKeyManager` → callback

**Ключевые файлы Type:**
- `src/helpers/windowsKeyManager.js` — обёртка над `windows-key-listener.exe`
- `src/helpers/hotkeyManager.js` — определение типа hotkey, routing на нативный/globalShortcut
- `src/helpers/windowManager.js` — push-to-talk state machine

| Aspect | Type | Talker Box |
|--------|------|------------|
| Hotkey method | `SetWindowsHookExA(WH_KEYBOARD_LL)` (C++) — **подавляет** | `GetAsyncKeyState` poll (Python) — **не подавляет** |
| Win key behavior | Перехватывается хуком, Windows НЕ видит | Windows видит → открывает меню |
| State machine | 150ms debounce, push/tap modes | Нет debounce, toggle/hold |
| Modifier-only | Обязательно через нативный listener | Через GetAsyncKeyState (проблема) |
| Paste | `SendInput` (C++) | `pyperclip` + `SendInput` (Python ctypes) |
| Model | GigaAM v3 E2E RNNT (851 МБ float32) | GigaAM v3 trans-punct (225 МБ int8) |

**Вывод:** Type правильный подход — `SetWindowsHookExA(WH_KEYBOARD_LL)` с `CallNextHookEx` для пропуска не-наших клавиш. Наша ошибка: предыдущая реализация НЕ вызывала `CallNextHookEx` → убивала клавиатуру.

---

## Правила работы

1. **Не показывать/todo списки в чате** — замерзают и висят
2. **Не переименовывать файлы/проект** во время работы — ломает пути/импорты
3. **Python:** `C:\Program Files\Python312\python.exe` — НЕ в PATH, использовать полный путь
4. **Сборка:** `build.bat` → PyInstaller → `dist/TalkerBox/`
5. **Коммиты:** Делать на GitHub (`https://github.com/mihalanius/Talker-Box.git`)
6. **Теги:** v1.13 = baseline (commit `d98c766`), v1.14 = текущая (commit `c367af8`)

---

## Приоритеты для решения

1. **Win key problem** → Переписать `hotkey_listener.py` на `SetWindowsHookExA(WH_KEYBOARD_LL)` с правильным `CallNextHookEx` (подавление клавиш как в Type)
2. **RECORD_TIMEOUT** → Заменить `QTimer.singleShot` на `threading.Timer` или ручной опрос
3. **Garbled text** → Добавить threading.Lock к recognizer, пересоздаватор recognizer периодически
4. **Toggle reliability** → State machine с 150ms debounce (как в Type: `MIN_HOLD_DURATION_MS`)
5. **Hold mode UP detection** → Два последовательных чтения для подтверждения отпускания

---

## Среда

- **OS:** Windows 10/11
- **Python:** 3.12.7 (`C:\Program Files\Python312\`)
- **pip пакеты:** PyQt6, sounddevice, numpy, pyperclip, onnxruntime, sherpa-onnx v1.13.7
- **Git:** `https://github.com/mihalanius/Talker-Box.git`
- **Рабочая папка:** `D:\OpenCode_Arhive\Talker Box\`
- **Модель:** `D:\OpenCode_Arhive\Voice models\sherpa-onnx-nemo-transducer-punct-giga-am-v3-russian-2025-12-16`
