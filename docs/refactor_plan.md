# Talker Box — План правок по рекомендациям Devin AI

## Приоритет: ВЫСОКИЙ

### 1. Жёсткие пути в build.bat
**Файл:** `build.bat`
**Проблема:** Строка 2 — `cd /d "D:\OpenCode_Arhive\Talker Box"`
**Решение:** Заменить на `cd /d "%~dp0"`
**Время:** 5 минут

### 2. Загрузка модели в отдельном потоке
**Файл:** `src/main.py`
**Проблема:** Модель GigaAM загружается синхронно, блокирует UI на 2-3 секунды
**Решение:**
- Создать `src/model_loader.py` с `QThread`
- Показывать индикатор загрузки
- Разблокировать UI после загрузки
**Время:** 30 минут

---

## Приоритет: СРЕДНИЙ

### 3. Вынести константы в config.py
**Файл:** `src/config.py` (создать)
**Что вынести:**
```python
# Размеры окон
WINDOW_WIDTH = 585
WINDOW_HEIGHT = 419
WAVEFORM_WIDTH = 200
WAVEFORM_HEIGHT = 30

# Тайминги
STARS_ANIMATION_INTERVAL = 150  # удалить после удаления звёзд

# Кнопки панели
HEADER_BTN_SIZE = 20
BOTTOM_BTN_WIDTH = 150
BOTTOM_BTN_HEIGHT = 40
```
**Время:** 20 минут

### 4. Вынести стили в theme.py
**Файл:** `src/theme.py` (создать)
**Что вынести:**
```python
class Theme:
    BG_TOP = "#0d1225"
    BG_MIDDLE = "#111830"
    BG_BOTTOM = "#0a0f1f"
    ACCENT_GREEN = "#00ff88"
    ACCENT_BLUE = "#00f7ff"
    ACCENT_ORANGE = "#ff8800"
    ACCENT_PURPLE = "#aa44ff"
    TEXT_COLOR = "#e0e0e0"
    PANEL_BORDER_ACTIVE = "#00ff88"
    PANEL_BORDER_INACTIVE = "#444444"
    PANEL_HOVER_LIGHT = "#666666"
    PANEL_HOVER_DARK = "#555555"
```
**Время:** 20 минут

### 5. Создать requirements.txt
**Файл:** `requirements.txt` (создать)
**Содержимое:**
```
PyQt6>=6.6.0
sounddevice>=0.4.0
numpy>=1.24.0
pyperclip>=1.8.0
sherpa-onnx>=1.13.0
pywin32>=306
```
**Время:** 5 минут

---

## Приоритет: НИЗКИЙ

### 6. Централизация путей
**Файл:** `src/paths.py`
**Проблема:** `_get_base_dir()` дублируется в main.py, settings_manager.py, transcriber.py
**Решение:** Оставить в `paths.py`, импортировать оттуда
**Время:** 10 минут

### 7. Очистить устаревшие настройки
**Файл:** `src/settings_manager.py`
**Проблема:** settings.json может содержать `active_model`, `models` (удалены в v2.0)
**Решение:** При загрузке удалять устаревшие поля
**Время:** 10 минут

### 8. Удалить неиспользуемый код
**Удалить:**
- `StarsWidget` из main.py (не отображается)
- Импорт `random`, `math` связанных со звёздами
- Таймер анимации звёзд
**Время:** 5 минут

---

## ИТОГО

| Приоритет | Пунктов | Время |
|-----------|---------|-------|
| Высокий | 2 | 35 мин |
| Средний | 3 | 45 мин |
| Низкий | 3 | 25 мин |
| **ИТОГО** | **8** | **~105 мин** |

---

## ПОРЯДОК ВЫПОЛНЕНИЯ

1. Удалить StarsWidget (быстро, сразу видно результат)
2. build.bat — исправить пути (быстро)
3. Создать config.py и theme.py
4. Обновить main.py для использования config/theme
5. Создать requirements.txt
6. Исправить paths.py
7. Очистить settings_manager.py
8. Создать model_loader.py для фоновой загрузки

---

## НЕ ТРОГАТЬ

- hotkey_hook.py / hotkey_listener.py — всё работает
- try-except pass — осознанно
- Импорты внутри функций — нормально
- Разделение UI — не нужно для такого проекта
- Тесты — ручного тестирования достаточно
- Docstring — личный проект
- Логирование — уровни не нужны
