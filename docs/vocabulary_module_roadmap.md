# Talker Box — План разработки модуля пользовательского словаря

## Детальная дорожная карта

---

## Обзор

**Цель:** реализовать модуль пользовательского словаря на базе hotwords sherpa-onnx, который позволит программе распознавать профессиональный жаргон, термины, устойчивые выражения и горячие клавиши.

**Стек:** Python, PyQt6, sherpa-onnx, JSON

**Сроки:** 4 фазы, ~2–3 недели

---

## Фаза 1: Ядро модуля (5–7 дней)

### Задача 1.1: Vocabulary Manager

**Файл:** `src/vocabulary/manager.py`

**Что делает:**
- Загружает JSON-словари из папки `vocabularies/`
- Сохраняет изменения
- Переключает активные категории
- Экспортирует в hotwords формат

```python
# API
class VocabularyManager:
    def __init__(self, vocab_dir: str = "vocabularies")
    def load_vocabulary(self, name: str) -> dict
    def save_vocabulary(self, name: str, data: dict)
    def get_active_words(self) -> list  # слова из активных категорий
    def add_word(self, category: str, word: str, target: str, score: float)
    def remove_word(self, category: str, word: str)
    def generate_hotwords(self, output_path: str) -> str  # возвращает путь
    def get_categories(self) -> list
    def toggle_category(self, name: str, enabled: bool)
```

**Тест:**
```python
def test_add_word():
    vm = VocabularyManager()
    vm.add_word("programming", "пул реквест", "pull request", 3.0)
    words = vm.get_active_words()
    assert ("pull request", 3.0) in words
```

---

### Задача 1.2: Hotwords Generator

**Файл:** `src/vocabulary/hotwords.py`

**Что делает:**
- Конвертирует JSON-словарь в hotwords файл
- Фильтрует по активным категориям
- Сортирует по score
- Кэширует результат

```python
class HotwordsGenerator:
    def __init__(self, vocabulary_manager: VocabularyManager)
    def generate(self, output_path: str = "hotwords_cache.txt")
    def update_score(self, word: str, new_score: float)
    def get_stats(self) -> dict  # количество слов, размер файла
```

**Формат выходного файла:**
```
# Talker Box Vocabulary — auto-generated
# Categories: programming, shortcuts, software
pull request:3.0
Docker Compose:3.0
GitHub:3.0
Ctrl + Shift + S:3.5
...
```

---

### Задача 1.3: Интеграция с transcriber.py

**Изменения в:** `src/transcriber.py`

**Что делает:**
- Перед распознаванием генерирует/обновляет hotwords файл
- Передаёт путь к hotwords файлу в sherpa-onnx конфиг
- Использует `modified_beam_search`

```python
# Изменения в Transcriber.__init__
def __init__(self):
    self.vocabulary_manager = VocabularyManager()
    self.hotwords_generator = HotwordsGenerator(self.vocabulary_manager)
    # ...

# Изменения в _load_sherpa_onnx
def _load_sherpa_onnx(self, model_path):
    # ... существующий код ...
    
    # Добавить hotwords параметры
    self.recognizer = sherpa_onnx.OfflineRecognizer(
        encoder=encoder_path,
        decoder=decoder_path,
        joiner=joiner_path,
        tokens=tokens_path,
        model_type="nemo_transducer",
        decoding_method="modified_beam_search",  # ← ВАЖНО!
        hotwords_file=self.hotwords_path,
        hotwords_score=2.0
    )
```

---

### Задача 1.4: Настройки словаря

**Изменения в:** `src/settings_manager.py`

**Добавить в DEFAULT_SETTINGS:**
```python
"vocabulary": {
    "enabled": True,
    "active_categories": ["programming", "shortcuts"],
    "hotwords_score": 2.0,
    "auto_generate": True,
    "cache_path": "hotwords_cache.txt"
}
```

---

## Фаза 2: Пост-обработка (3–4 дня)

### Задача 2.1: Post Processor

**Файл:** `src/vocabulary/post_processor.py`

**Что делает:**
- После распознавания применяет замены из словаря
- Поддерживает regex-паттерны
- Работает параллельно с hotwords

```python
class PostProcessor:
    def __init__(self, vocabulary_manager: VocabularyManager)
    def process(self, text: str) -> str
    def add_replacement(self, original: str, replacement: str)
    def add_pattern(self, pattern: str, replacement: str)
    def get_replacements(self) -> dict
```

**Правила замены (из JSON):**
```json
{
  "replacements": {
    "гитхаб": "GitHub",
    "докер компоуз": "Docker Compose"
  },
  "patterns": [
    {
      "find": "контрол\\s+([а-яё]+)",
      "replace": "Ctrl + \\1"
    }
  ]
}
```

---

### Задача 2.2: Интеграция с main.py

**Изменения в:** `src/main.py`

**Добавить:**
- Кнопка «Словарь» в нижнюю панель
- Обработчик клика → открытие диалога словаря
- Вызов post_processor после распознавания

```python
# В init_ui()
self.vocab_btn = QPushButton("📚 Словарь")
self.vocab_btn.clicked.connect(self.show_vocabulary_dialog)
bottom_layout.addWidget(self.vocab_btn)

# В обработчике распознавания
def _on_speech_recognized(self, text):
    # Hotwords уже применились на уровне модели
    # Теперь пост-обработка
    processed = self.post_processor.process(text)
    # Вставка текста
    self._insert_text(processed)
```

---

## Фаза 3: UI управления словарём (4–5 дней)

### Задача 3.1: Vocabulary Dialog

**Файл:** `src/ui/vocabulary_dialog.py`

**Экраны:**

#### Экран 1: Список категорий
```
┌─────────────────────────────────────────┐
│ 📚 Пользовательский словарь             │
│                                          │
│ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐       │
│ │ 💻  │ │ ⌨   │ │ 📦  │ │ ⭐  │       │
│ │ IT  │ │Клав.│ │Прог.│ │Моё │       │
│ │ 45  │ │ 12  │ │ 18  │ │ 5  │       │
│ │  ✓  │ │  ✓  │ │  ✓  │ │  ✓ │       │
│ └─────┘ └─────┘ └─────┘ └─────┘       │
│                                          │
│ Всего: 80 слов | Hotwords: ВКЛ         │
│                                          │
│ [Настройки] [Импорт] [Экспорт]          │
└─────────────────────────────────────────┘
```

#### Экран 2: Список слов в категории
```
┌─────────────────────────────────────────┐
│ 💻 Программирование (45 слов)    [←]   │
│                                          │
│ 🔍 [_________________] [+] Добавить     │
│                                          │
│ ┌───────────────────────────────────┐   │
│ │ Слово        │ Замена      │ Score│   │
│ ├───────────────┼─────────────┼──────┤   │
│ │ пул реквест   │ pull request│ 3.0  │   │
│ │ коммит        │ commit      │ 2.5  │   │
│ │ брэнч         │ branch      │ 2.5  │   │
│ │ деплой        │ deploy      │ 2.0  │   │
│ └───────────────────────────────────┘   │
│                                          │
│ [Удалить выбранные] [Экспорт]           │
└─────────────────────────────────────────┘
```

#### Экран 3: Добавление слова
```
┌─────────────────────────────────────────┐
│ ➕ Добавить слово                   [×]  │
│                                          │
│ ASR говорит:    [гитхаб_____________]   │
│ Должно быть:    [GitHub_____________]   │
│ Категория:      [IT-словарь      ▾]    │
│ Приоритет:      [■■■■■□□□□□] 2.5      │
│                                          │
│ [Сохранить]  [Отмена]                   │
└─────────────────────────────────────────┘
```

---

### Задача 3.2: Настройки словаря

**Файл:** `src/ui/vocabulary_settings_dialog.py`

```
┌─────────────────────────────────────────┐
│ ⚙ Настройки словаря                [×]  │
│                                          │
│ Hotwords:                               │
│   [✓] Включить hotwords                 │
│   Сила буста: [■■■■■□□□□□] 2.0        │
│                                          │
│ Пост-обработка:                         │
│   [✓] Включить замены                   │
│   [✓] Включить regex-паттерны           │
│                                          │
│ Авто-обучение:                          │
│   [✓] Предлагать добавление слов        │
│   Порог: [3] исправлений                │
│                                          │
│ Кэш:                                    │
│   Hotwords файл: 2.3 KB (80 слов)       │
│   [Обновить кэш]                        │
│                                          │
│ [Сохранить]  [По умолчанию]             │
└─────────────────────────────────────────┘
```

---

## Фаза 4: Авто-обучение (3–4 дня)

### Задача 4.1: Auto Learner

**Файл:** `src/vocabulary/auto_learner.py`

**Что делает:**
- Сравнивает текст от ASR с финальным текстом
- Находит расхождения
- Предлагает пользователю добавить правило

```python
class AutoLearner:
    def __init__(self, vocabulary_manager: VocabularyManager)
    def on_text_inserted(self, asr_text: str, final_text: str)
    def get_pending_suggestions(self) -> list
    def accept_suggestion(self, index: int)
    def reject_suggestion(self, index: int)
```

---

### Задача 4.2: UI предложений

**Файл:** `src/ui/suggestion_dialog.py`

```
┌─────────────────────────────────────────┐
│ 💡 Предложение добавления правила       │
│                                          │
│ ASR сказал:    "гитхаб"                 │
│ Должно быть:   "GitHub"                 │
│                                          │
│ Категория: [IT-словарь          ▾]     │
│ Приоритет: [■■■■■□□□□□] 2.5           │
│                                          │
│ [Добавить] [Изменить] [Пропустить]      │
│                                          │
│ Осталось: 3 предложения                  │
└─────────────────────────────────────────┘
```

---

## Фаза 5: Предустановленные словари (2–3 дня)

### Задача 5.1: Создание словарей

| Файл | Категория | Количество слов |
|------|-----------|-----------------|
| `vocabularies/programming.json` | Программирование | 50+ |
| `vocabularies/shortcuts.json` | Горячие клавиши | 30+ |
| `vocabularies/software.json` | Программы | 30+ |
| `vocabularies/medical.json` | Медицина | 40+ |
| `vocabularies/finance.json` | Финансы | 40+ |
| `vocabularies/gaming.json` | Игры | 30+ |

### Задача 5.2: Экспорт/Импорт

**Поддерживаемые форматы:**
- JSON (полный формат Talker Box)
- TXT (слово → замена, по одной на строку)
- CSV (слово;замена;категория)
- Hotwords (для sherpa-onnx)

---

## Структура файлов после реализации

```
Talker Box/
├── src/
│   ├── main.py
│   ├── transcriber.py          # + hotwords интеграция
│   ├── settings_manager.py     # + настройки словаря
│   ├── vocabulary/
│   │   ├── __init__.py
│   │   ├── manager.py          # управление словарями
│   │   ├── hotwords.py         # генерация hotwords файла
│   │   ├── post_processor.py   # замены после распознавания
│   │   └── auto_learner.py     # авто-обучение
│   └── ui/
│       ├── vocabulary_dialog.py
│       ├── vocabulary_settings_dialog.py
│       └── suggestion_dialog.py
├── vocabularies/
│   ├── programming.json
│   ├── shortcuts.json
│   ├── software.json
│   ├── medical.json
│   ├── finance.json
│   └── gaming.json
└── hotwords_cache.txt          # автогенерируемый
```

---

## Порядок разработки

```
День 1-2:   Vocabulary Manager + Hotwords Generator
День 3-4:   Интеграция с transcriber.py + тесты
День 5-6:   Post Processor
День 7-8:   UI: Vocabulary Dialog (список категорий + слов)
День 9-10:  UI: Добавление/редактирование слов
День 11-12: Auto Learner
День 13-14: UI: Предустановленные словари + Настройки
День 15-16: Импорт/Экспорт
День 17-18: Тестирование + баги
День 19-20: Финальная сборка + установщик
```

---

## Зависимости

```
Vocabulary Manager ──┬──▶ Hotwords Generator ──▶ transcriber.py
                     │
                     ├──▶ Post Processor ──▶ main.py
                     │
                     └──▶ Auto Learner ──▶ UI предложений
```

---

## Критерии готовности

- [ ] JSON-словарь загружается и сохраняется
- [ ] Hotwords файл генерируется автоматически
- [ ] sherpa-onnx принимает hotwords файл
- [ ] Распознавание учитывает hotwords
- [ ] Post processor применяет замены
- [ ] UI позволяет добавлять/удалять слова
- [ ] Предустановленные словари работают
- [ ] Импорт/экспорт в разных форматах
- [ ] Авто-обучение предлагает правила
- [ ] Установщик включает словари
- [ ] Нет регрессии в основном функционале
