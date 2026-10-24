# Talker Box — Нейромодуль пользовательского словаря

## Технический план разработки

---

## 1. Обзор

**Цель:** создание модуля, который позволит программе распознавать специфическую лексику — жаргон, термины, имена, аббревиатуры, устойчивые выражения — в зависимости от профессии и контекста пользователя.

**Проблема:** стандартная ASR-модель обучена на общем корпусе текста и плохо распознаёт:
- Профессиональный жаргон (медицина, финансы, IT)
- Имена собственные и топонимы
- Сленг и разговорные формы
- Устойчивые выражения («пул реквест» → «pull request»)
- Сокращения и аббревиатуры

**Решение:** многоуровневая система адаптации распознавания через пользовательский словарь, передаваемый модели в runtime.

---

## 2. Архитектура модуля

```
┌─────────────────────────────────────────────────────┐
│                    Talker Box                        │
│                                                      │
│  ┌──────────────┐    ┌──────────────────────────┐   │
│  │   GUI:        │    │   Vocabulary Manager     │   │
│  │  - Словари    │───▶│  - Загрузка/сохранение   │   │
│  │  - Категории  │    │  - Фильтрация по теме    │   │
│  │  - Правила    │    │  - Приоритизация слов    │   │
│  │  - Импорт     │    │  - Авто-обучение         │   │
│  └──────────────┘    └──────────┬───────────────┘   │
│                                 │                    │
│                                 ▼                    │
│  ┌──────────────────────────────────────────────┐   │
│  │           ASR Engine (sherpa-onnx)            │   │
│  │                                                │   │
│  │  ┌─────────────┐  ┌────────────────────────┐ │   │
│  │  │ GigaAM Model│  │ Hotwords Integration   │ │   │
│  │  │ (NeMo)      │◀─│ - Hotwords file        │ │   │
│  │  │             │  │ - Modified beam search  │ │   │
│  │  └─────────────┘  │ - Contextual biasing   │ │   │
│  │                    └────────────────────────┘ │   │
│  └──────────────────────────────────────────────┘   │
│                                 │                    │
│                                 ▼                    │
│  ┌──────────────────────────────────────────────┐   │
│  │         Post-processing Pipeline              │   │
│  │  - Замена правил из словаря                   │   │
│  │  - Коррекция по паттернам                     │   │
│  │  - Предложение добавления нового правила      │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

---

## 3. Методы интеграции словаря

### 3.1. Передача словаря в ASR-модель (Runtime Vocabulary)

Это основной метод. Словарь передаётся модели **до начала распознавания** каждого сегмента.

#### Поддерживаемые фичи sherpa-onnx:

| Фича | Описание | Применимость |
|-------|----------|--------------|
| **Hotwords** | Буст конкретных слов/фраз через Aho-corasick автомат | ✅ Основной метод |
| **Contextual biasing** | Синоним hotwords — приоритетное распознавание контекста | ✅ То же что hotwords |
| **Phrase hints** | Подсказки фраз — одна фраза = одна строка в hotwords файле | ✅ Через hotwords |
| **Custom vocabulary** | Пользовательский словарь через hotwords файл | ✅ Через hotwords |
| **Vocabulary biasing** | Сила буста через параметр `hotwords-score` | ✅ Настраиваемый |
| **Grammar constraints** | Ограничения грамматики через FST | ❌ Не поддерживается в sherpa-onnx |

#### Реализация:

```python
# Формирование hotwords файла из пользовательского словаря
def generate_hotwords_file(vocabulary: dict, output_path: str):
    """
    Генерирует hotwords файл из пользовательского словаря.
    
    Формат строки: "фраза:score"
    Пример:
      Docker Compose:3.0
      пул реквест:2.5
      контекстное распознавание:2.0
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        for category, words in vocabulary.items():
            for word, score in words.items():
                f.write(f"{word}:{score}\n")

# Передача в sherpa-onnx
config = {
    "hotwords_file": "user_vocabulary.txt",
    "hotwords_score": 2.0,
    "decoding_method": "modified_beam_search"  # Обязательно!
}
```

#### Параметры настройки:

| Параметр | Описание | Диапазон |
|----------|----------|----------|
| `hotwords_score` | Сила буста слова | 1.0–5.0 |
| `decoding_method` | Метод декодирования | `modified_beam_search` |
| `max_active` | Макс. активных состояний | 32–128 |
| `beam` | Ширина луча | 4–16 |

---

### 3.2. Пост-обработка (Post-processing)

Дополнительный уровень — замена слов после распознавания, но до вставки в текстовое поле.

#### Правила замены:

```json
{
  "replacements": {
    "гит хаб": "GitHub",
    "докер компоуз": "Docker Compose",
    "пул реквест": "pull request",
    "контрол шифт эс": "Ctrl + Shift + S",
    "юзер интерфейс": "user interface",
    "энGINEр": "инженер"
  },
  "patterns": [
    {
      "find": "контрол\\s+([а-яё]+)",
      "replace": "Ctrl + \\1",
      "description": "Ctrl + клавиша"
    }
  ]
}
```

#### Алгоритм:

1. ASR возвращает текст
2. Применяются прямые замены из `replacements`
3. Применяются regex-паттерны из `patterns`
4. Результат вставляется в активное окно

---

## 4. Структура JSON-словаря

### 4.1. Основная структура

```json
{
  "version": "1.0",
  "name": "IT-словарь",
  "description": "Словарь для IT-специалистов",
  "language": "ru",
  "categories": {
    "programming": {
      "name": "Программирование",
      "icon": "💻",
      "words": {
        "пул реквест": {"target": "pull request", "score": 3.0},
        "коммит": {"target": "commit", "score": 2.5},
        "брэнч": {"target": "branch", "score": 2.5},
        "репозиторий": {"target": "repository", "score": 2.0},
        "деплой": {"target": "deploy", "score": 2.0},
        "рефакторинг": {"target": "refactoring", "score": 2.0}
      }
    },
    "shortcuts": {
      "name": "Горячие клавиши",
      "icon": "⌨",
      "words": {
        "контрол шифт эс": {"target": "Ctrl + Shift + S", "score": 3.5},
        "контрол це": {"target": "Ctrl + C", "score": 3.0},
        "альт таб": {"target": "Alt + Tab", "score": 3.0},
        "вин дот": {"target": "Win + .", "score": 2.5}
      }
    },
    "software": {
      "name": "Программы",
      "icon": "📦",
      "words": {
        "докер компоуз": {"target": "Docker Compose", "score": 3.0},
        "гит хаб": {"target": "GitHub", "score": 3.0},
        "гит лаб": {"target": "GitLab", "score": 3.0},
        "вижуал студио код": {"target": "Visual Studio Code", "score": 2.5},
        "ноушн": {"target": "Notion", "score": 2.0}
      }
    },
    "names": {
      "name": "Имена",
      "icon": "👤",
      "words": {
        "машин": {"target": "Машин", "score": 2.0},
        "голдман": {"target": "Goldman", "score": 2.5}
      }
    },
    "medical": {
      "name": "Медицина",
      "icon": "🏥",
      "words": {
        "гипертензия": {"target": "гипертензия", "score": 2.0},
        "кардиомиопатия": {"target": "кардиомиопатия", "score": 2.0}
      }
    },
    "finance": {
      "name": "Финансы",
      "icon": "💰",
      "words": {
        "кэшбэк": {"target": "кэшбэк", "score": 2.0},
        "диверсификация": {"target": "диверсификация", "score": 2.0}
      }
    },
    "custom": {
      "name": "Пользовательские",
      "icon": "⭐",
      "words": {}
    }
  },
  "settings": {
    "default_score": 2.0,
    "max_score": 5.0,
    "auto_learn": true,
    "auto_learn_threshold": 3,
    "post_processing_enabled": true
  }
}
```

### 4.2. Формат Hotwords файла (автогенерация)

```
# Auto-generated from user vocabulary
# Talker Box v2.0
pull request:3.0
commit:2.5
branch:2.5
repository:2.0
deploy:2.0
refactoring:2.0
Ctrl + Shift + S:3.5
Ctrl + C:3.0
Alt + Tab:3.0
Win + .:2.5
Docker Compose:3.0
GitHub:3.0
GitLab:3.0
Visual Studio Code:2.5
Notion:2.0
```

---

## 5. Автоматическое обучение (Auto-learning)

### 5.1. Принцип работы

```
Пользователь говорит: "Открой гит хаб"
       │
       ▼
ASR распознаёт: "Открой гитхаб" (без дефиса/пробела)
       │
       ▼
Пост-обработка: "Открой GitHub" (по правилу из словаря)
       │
       ▼
Пользователь видит результат: "Открой GitHub"
       │
       ▼
Варианты:
  a) Всё верно → ничего не делать
  b) Ошибка → пользователь исправляет вручную
       │
       ▼
Система сравнивает: "гитхаб" vs "GitHub"
       │
       ▼
Предложение: Добавить правило? "гитхаб" → "GitHub"
       │
       ▼
[Добавить] → правило сохраняется в словарь
[Пропустить] → игнорируется
```

### 5.2. Реализация

```python
class AutoLearner:
    """Автоматическое обучение на исправлениях пользователя."""
    
    def __init__(self, vocabulary_path: str):
        self.vocabulary = self._load_vocabulary(vocabulary_path)
        self.pending_suggestions = []
        self.correction_buffer = []
    
    def on_text_inserted(self, original_asr: str, final_text: str):
        """
        Вызывается после вставки текста.
        Сравнивает распознанный текст с финальным.
        """
        if original_asr != final_text:
            # Найдём различия
            diff = self._find_diff(original_asr, final_text)
            if diff:
                self._suggest_rule(diff)
    
    def _find_diff(self, asr_text: str, final_text: str):
        """
        Находит замены: что ASR сказал → что должно быть.
        Возвращает список пар (original, replacement).
        """
        # Нормализация и сравнение
        asr_words = asr_text.lower().split()
        final_words = final_text.lower().split()
        
        replacements = []
        # Алгоритм поиска最长公共子序列 (LCS)
        # для определения замен
        return replacements
    
    def _suggest_rule(self, diff):
        """Предлагает пользователю добавить правило."""
        for original, replacement in diff:
            self.pending_suggestions.append({
                "original": original,
                "replacement": replacement,
                "score": 2.0,
                "category": "custom",
                "auto_generated": True
            })
    
    def accept_suggestion(self, suggestion_id: int):
        """Принятие предложения — добавление в словарь."""
        suggestion = self.pending_suggestions[suggestion_id]
        self._add_to_vocabulary(
            suggestion["original"],
            suggestion["replacement"],
            suggestion["category"],
            suggestion["score"]
        )
        self.pending_suggestions.pop(suggestion_id)
    
    def _add_to_vocabulary(self, word, target, category, score):
        """Добавление слова в JSON-словарь."""
        if category not in self.vocabulary["categories"]:
            category = "custom"
        
        self.vocabulary["categories"][category]["words"][word] = {
            "target": target,
            "score": score,
            "auto_added": True,
            "added_at": datetime.now().isoformat()
        }
        self._save_vocabulary()
        self._regenerate_hotwords_file()
```

### 5.3. Интерфейс предложений

```
┌─────────────────────────────────────────────┐
│  💡 Предложение добавления правила          │
│                                              │
│  ASR сказал:    "гитхаб"                    │
│  Должно быть:    "GitHub"                    │
│                                              │
│  Категория: [IT-словарь        ▾]           │
│  Приоритет:  [■■■■■□□□□□] 2.5              │
│                                              │
│  [Добавить]  [Изменить]  [Пропустить]       │
└─────────────────────────────────────────────┘
```

---

## 6. Интерфейс управления словарём

### 6.1. Главный экран

```
┌─────────────────────────────────────────────────────┐
│  📚 Пользовательский словарь                        │
│                                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │ 💻 IT    │ │ ⌨ Клавиши│ │ 📦 Проги │ ...        │
│  │   45 слов│ │   12 слов│ │   18 слов│            │
│  └──────────┘ └──────────┘ └──────────┘            │
│                                                      │
│  🔍 Поиск: [_____________] [+] Добавить слово       │
│                                                      │
│  ┌─────────────────────────────────────────────┐   │
│  │ Слово           │ Замена        │ Score │ ⚙  │   │
│  ├─────────────────┼───────────────┼───────┼──┤   │
│  │ пул реквест     │ pull request  │  3.0  │ ✏🗑│   │
│  │ докер компоуз   │ Docker Compose│  3.0  │ ✏🗑│   │
│  │ конт шифт эс    │ Ctrl+Shift+S  │  3.5  │ ✏🗑│   │
│  │ гит хаб         │ GitHub        │  3.0  │ ✏🗑│   │
│  └─────────────────────────────────────────────┘   │
│                                                      │
│  [Импорт] [Экспорт] [Авто-обучение: ВКЛ]           │
└─────────────────────────────────────────────────────┘
```

### 6.2. Добавление нового слова

```
┌─────────────────────────────────────────────┐
│  ➕ Добавить слово                           │
│                                              │
│  ASR говорит:    [гитхаб_____________]       │
│  Должно быть:    [GitHub_____________]       │
│  Категория:      [IT-словарь        ▾]      │
│  Приоритет:      [■■■■■□□□□□] 2.5          │
│                                              │
│  [Сохранить]  [Отмена]                       │
└─────────────────────────────────────────────┘
```

### 6.3. Импорт/Экспорт

```python
# Поддерживаемые форматы импорта
IMPORT_FORMATS = {
    "json": "JSON-словарь Talker Box",
    "txt": "Текстовый файл (одно слово на строку)",
    "csv": "CSV (слово;замена;категория)",
    "hotwords": "Hotwords файл sherpa-onnx"
}

# Экспорт
EXPORT_FORMATS = {
    "json": "Полный словарь с настройками",
    "hotwords": "Hotwords файл для sherpa-onnx",
    "txt": "Только слова и замены"
}
```

---

## 7. Интеграция с текущей сборкой

### 7.1. Файловая структура

```
Talker Box/
├── src/
│   ├── main.py
│   ├── vocabulary/
│   │   ├── __init__.py
│   │   ├── manager.py          # Управление словарями
│   │   ├── auto_learner.py     # Авто-обучение
│   │   ├── hotwords.py         # Генерация hotwords файла
│   │   ├── post_processor.py   # Пост-обработка текста
│   │   └── importer.py         # Импорт/экспорт
│   └── ui/
│       └── vocabulary_dialog.py # UI управления словарём
├── vocabularies/
│   ├── it.json                  # IT-словарь
│   ├── medical.json             # Медицинский
│   ├── finance.json             # Финансовый
│   └── custom.json              # Пользовательский
└── hotwords_cache.txt           # Кэш hotwords файла
```

### 7.2. Изменения в transcriber.py

```python
class Transcriber:
    def __init__(self):
        self.vocabulary_manager = VocabularyManager()
        self.post_processor = PostProcessor()
        self.auto_learner = AutoLearner()
    
    def recognize(self, audio_data):
        # 1. Генерация hotwords файла из активного словаря
        hotwords_path = self.vocabulary_manager.generate_hotwords()
        
        # 2. Распознавание с hotwords
        result = self._recognize_with_hotwords(
            audio_data, 
            hotwords_path
        )
        
        # 3. Пост-обработка (замена правилами)
        processed = self.post_processor.process(result)
        
        # 4. Авто-обучение (сравнение ASR vs финал)
        self.auto_learner.on_text_inserted(result, processed)
        
        return processed
```

### 7.3. Изменения в settings.json

```json
{
  "hotkey": "ctrl+win",
  "mode": "hold",
  "auto_send": true,
  "vocabulary": {
    "enabled": true,
    "active_categories": ["programming", "shortcuts", "software"],
    "custom_vocabulary_path": "vocabularies/custom.json",
    "auto_learn": true,
    "auto_learn_threshold": 3,
    "hotwords_score": 2.0,
    "post_processing": true
  }
}
```

---

## 8. Предустановленные словари

| Словарь | Категория | Описание |
|---------|-----------|----------|
| `it.json` | Программирование | Git, Docker, APIs, фреймворки |
| `shortcuts.json` | Горячие клавиши | Windows, VS Code, браузеры |
| `medical.json` | Медицина | Термины, лекарства, процедуры |
| `finance.json` | Финансы | Банкинг, инвестиции, бухучёт |
| `gaming.json` | Игры | Жаргон геймеров, стриминг |
| `legal.json` | Юриспруденция | Законы, термины, формулировки |

---

## 9. Приоритеты разработки

### Фаза 1: Базовая функциональность
- [ ] JSON-словарь с категориями
- [ ] Генерация hotwords файла
- [ ] Передача в sherpa-onnx
- [ ] UI для добавления слов

### Фаза 2: Пост-обработка
- [ ] Движок замен (regex + словарь)
- [ ] UI для управления правилами
- [ ] Импорт/экспорт

### Фаза 3: Авто-обучение
- [ ] Сравнение ASR vs финальный текст
- [ ] Предложение правил пользователю
- [ ] Накопление статистики

### Фаза 4: Продвинутые фичи
- [ ] Предустановленные словари
- [ ] Облачная синхронизация словарей
- [ ] Адаптация под конкретного пользователя

---

## 10. Ограничения и риски

| Риск | Описание | Митигация |
|------|----------|-----------|
| **Латентность** | Загрузка hotwords файла перед каждым распознаванием | Кэширование, генерация при старте |
| **Размер словаря** | Большой словарь замедляет Aho-corasick | Лимит 10000 слов, приоритизация |
| **Точность** | Буст слов может снижать точность других слов | Настройка `hotwords-score`, тестирование |
| **Формат** | Hotwords файл требует特定ный формат | Автоконвертация из JSON |
| **Мультиязычность** | Смешение языков в одном словаре | Поддержка UTF-8, нормализация |

---

## 11. Заключение

Данный модуль позволит Talker Box адаптироваться под конкретного пользователя и его профессиональную область. Ключевые преимущества:

1. **Локальность** — словарь хранится на компьютере, ничего не отправляется
2. **Обучаемость** — система запоминает исправления пользователя
3. **Модульность** — можно отключить/включить категории
4. **Совместимость** — работает через hotwords API sherpa-onnx
5. **Простота** — JSON-формат, понятный пользователям

Интеграция с GigaAM через hotwords — это proven approach, который уже реализован в sherpa-onnx и не требует переобучения модели.
