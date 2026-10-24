# Talker Box — Техническая документация модуля словаря

---

## 1. Как hotwords работает внутри sherpa-onnx

### Общая идея

Hotwords — это **механизм приоритизации** распознавания. Модель GigaAM использует **нейросеть** для распознавания речи, но не понимает контекст или термины. Hotwords говорят модели: «Эти слова важнее других».

### Техническая реализация

#### Этап 1: Загрузка hotwords

```
hotwords_cache.txt
        │
        ▼
Aho-Corasick автомат (алгоритм поиска подстрок)
        │
        ▼
Индекс для быстрого поиска
```

**Aho-Corasick** — это алгоритм, который находит все вхождения множества слов в тексте за один проход. Пример:

```
Входной текст: "открой github через docker compose"
Hotwords: ["github", "docker compose"]

Aho-Corasick находит:
  - "github" на позиции 7-12
  - "docker compose" на позиции 19-32
```

#### Этап 2: Модификация beam search

Обычный **greedy search** (жадный поиск):
```
На каждом шаге выбирает символ с максимальной вероятностью.
Проблема: не учитывает контекст.
```

**Modified beam search** (модифицированный лучевой поиск):
```
На каждом шаге поддерживает N лучших вариантов (лучей).
Hotwords добавляют bonus к вероятности слов из списка.
```

Формула:
```
P_скорректированное = P_модели × (1 + hotwords_score × I(слово ∈ hotwords))

где I(условие) = 1 если условие истинно, 0 если ложно
```

Пример:
```
Слово "github" есть в hotwords с score = 3.0
Вероятность модели: P = 0.15

P_скорректированное = 0.15 × (1 + 3.0 × 1) = 0.15 × 4.0 = 0.60

Без hotwords: P = 0.15
С hotwords:   P = 0.60 (x4 буст!)
```

#### Этап 3: Декодирование

```
Аудио → Encoder → Decoder → Joiner → Beam Search (с hotwords) → Текст
```

**Encoder:** преобразует аудио в векторы признаков
**Decoder:** предсказывает следующий токен
**Joiner:** выбирает лучший токен из vocab
**Beam Search:** ищет лучшую последовательность токенов с учётом hotwords

#### Этап 4: Вывод

```
Лучший путь через граф: ["открой", "GitHub"]
        │
        ▼
Объединяется: "открой GitHub"
```

### Важные параметры

| Параметр | Описание | Значение по умолчанию |
|----------|----------|----------------------|
| `hotwords_file` | Путь к файлу hotwords | — |
| `hotwords_score` | Сила буста (множитель) | 1.5 |
| `decoding_method` | Метод декодирования | `modified_beam_search` |
| `beam` | Ширина луча | 4–16 |
| `max_active` | Макс. активных состояний | 32–128 |

---

## 2. Как данные текут от пользователя до модели

### Полный пайплайн (step-by-step)

#### Шаг 1: Запуск программы

```
main.py → __init__()
    │
    ├── Загрузка настроек (settings.json)
    │
    ├── Инициализация VocabularyManager
    │   └── Загрузка словарей из vocabularies/*.json
    │
    ├── Инициализация HotwordsGenerator
    │   └── Генерация hotwords_cache.txt (если нужно)
    │
    ├── Инициализация PostProcessor
    │   └── Загрузка правил замены
    │
    └── Инициализация Transcriber
        └── Загрузка GigaAM + hotwords файла
```

#### Шаг 2: Пользователь нажимает кнопку записи

```
main.py → _start_recording()
    │
    ├── Открытие потока микрофона
    │
    └── Начало записи аудио в буфер
```

#### Шаг 3: Пользователь говорит

```
Микрофон → Поток аудио (16kHz, 16-bit, mono)
    │
    ▼
Буфер аудио заполняется
    │
    ▼
Накоплено N секунд → готово к обработке
```

#### Шаг 4: Распознавание

```
transcriber.py → recognize(audio_data)
    │
    ├── 1. Нормализация аудио
    │   └── Приведение к 16kHz, float32
    │
    ├── 2. Передача в sherpa-onnx
    │   └── recognizer.accept_waveform(sample_rate, audio)
    │
    ├── 3. Ожидание результата
    │   └── recognizer.get_result()
    │
    └── 4. Получение текста
        └── "открой гитхаб"
```

#### Шаг 5: Пост-обработка

```
post_processor.process("открой гитхаб")
    │
    ├── Проверка прямых замен:
    │   "гитхаб" → "GitHub" ✓
    │
    ├── Проверка regex-паттернов:
    │   "контрол шифт эс" → "Ctrl + Shift + S" ✓
    │
    └── Результат: "открой GitHub"
```

#### Шаг 6: Вставка текста

```
main.py → _insert_text("открой GitHub")
    │
    ├── Определение активного окна
    │   └── GetForegroundWindow()
    │
    ├── Установка фокуса
    │   └── SetForegroundWindow()
    │
    └── Вставка текста
        └── SendInput() с клавишами
```

### Схема потока данных

```
┌─────────┐    ┌──────────┐    ┌────────────┐    ┌──────────┐
│ Микрофон │───▶│ Аудио    │───▶│ sherpa-onnx│───▶│ Текст    │
│          │    │ буфер    │    │ + hotwords │    │          │
└─────────┘    └──────────┘    └────────────┘    └──────────┘
                                                      │
                                                      ▼
┌─────────┐    ┌──────────┐    ┌────────────┐    ┌──────────┐
│ Активное │◀──│ SendInput│◀──│ Пост-      │◀──│ Финальный│
│ окно    │    │          │    │ обработка  │    │ текст    │
└─────────┘    └──────────┘    └────────────┘    └──────────┘
```

---

## 3. Как JSON-словарь превращается в hotwords файл

### Входные данные (JSON)

```json
{
  "categories": {
    "programming": {
      "words": {
        "пул реквест": {"target": "pull request", "score": 3.0},
        "коммит": {"target": "commit", "score": 2.5}
      }
    },
    "shortcuts": {
      "words": {
        "контрол шифт эс": {"target": "Ctrl + Shift + S", "score": 3.5}
      }
    }
  },
  "settings": {
    "active_categories": ["programming", "shortcuts"],
    "default_score": 2.0
  }
}
```

### Алгоритм конвертации

```python
def generate_hotwords_file(vocabulary, active_categories, output_path):
    """
    Шаг 1: Фильтрация по активным категориям
    Шаг 2: Извлечение слов и score
    Шаг 3: Сортировка по score (убывание)
    Шаг 4: Запись в файл
    """
    
    hotwords = []
    
    for category_name in active_categories:
        category = vocabulary["categories"][category_name]
        for word, data in category["words"].items():
            target = data["target"]      # "pull request"
            score = data.get("score",    # 3.0
                           vocabulary["settings"]["default_score"])
            hotwords.append((target, score))
    
    # Сортировка по score (убывание)
    hotwords.sort(key=lambda x: x[1], reverse=True)
    
    # Запись в файл
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# Talker Box Vocabulary — auto-generated\n")
        for target, score in hotwords:
            f.write(f"{target}:{score}\n")
```

### Выходные данные (hotwords файл)

```
# Talker Box Vocabulary — auto-generated
Ctrl + Shift + S:3.5
pull request:3.0
commit:2.5
```

### Формат строки

```
слово_или_фраза:числовой_балл
```

**Правила:**
- Одна строка = одно слово/фраза
- Разделитель `:` (двоеточие)
- Балл — число с плавающей точкой
- Пробелы в фразах допускаются: `Docker Compose:3.0`
- Комментарии начинаются с `#`

### Примеры

```
# Простые слова
GitHub:3.0
commit:2.5

# Фразы (с пробелами)
pull request:3.0
Docker Compose:3.0
Ctrl + Shift + S:3.5

# С специальными символами
Win + .:2.5
C++:3.0
```

---

## 4. Как авто-обучение определяет ошибки

### Алгоритм сравнения

#### Шаг 1: Сбор данных

```
ASR текст:    "открой гитхаб"
Финальный:    "открой GitHub"
```

#### Шаг 2: Нормализация

```python
def normalize(text):
    text = text.lower()           # "открой github"
    text = text.strip()           # убираем пробелы по краям
    text = re.sub(r'\s+', ' ', text)  # множественные пробелы → один
    return text

asr_normalized = "открой гитхаб"
final_normalized = "открой github"
```

#### Шаг 3: Токенизация

```python
asr_tokens = ["открой", "гитхаб"]
final_tokens = ["открой", "github"]
```

#### Шаг 4: Поиск最长公共子序列 (LCS)

```
ASR:    ["открой", "гитхаб"]
Final:  ["открой", "github"]

LCS:    ["открой"]  (длина 1)

Различия:
  ASR[1] = "гитхаб" ≠ Final[1] = "github"
```

#### Шаг 5: Группировка различий

```python
def find_differences(asr_tokens, final_tokens):
    """
    Находит группы замен.
    Возвращает список: [(original, replacement), ...]
    """
    differences = []
    
    # Алгоритм: скользящее окно
    i = 0  # индекс в ASR
    j = 0  # индекс в Final
    
    while i < len(asr_tokens) and j < len(final_tokens):
        if asr_tokens[i] == final_tokens[j]:
            # Совпадают — просто сдвигаем
            i += 1
            j += 1
        else:
            # Не совпадают — ищем замену
            original = asr_tokens[i]
            
            # Ищем, где появляется текущий ASR-токен в Final
            found = False
            for k in range(j, min(j + 3, len(final_tokens))):
                if final_tokens[k] == original:
                    # Нашли — значит это вставка, а не замена
                    i += 1
                    j += 1
                    found = True
                    break
            
            if not found:
                # Это замена — собираем группу
                replacement_tokens = []
                while j < len(final_tokens) and asr_tokens[i] != final_tokens[j]:
                    replacement_tokens.append(final_tokens[j])
                    j += 1
                
                replacement = " ".join(replacement_tokens)
                differences.append((original, replacement))
                i += 1
    
    return differences

# Результат:
differences = [("гитхаб", "github")]
```

#### Шаг 6: Предложение правила

```python
def suggest_rule(differences, vocabulary_manager):
    """
    Для каждой замены предлагает правило.
    """
    suggestions = []
    
    for original, replacement in differences:
        # Проверяем, нет ли уже такого правила
        existing = vocabulary_manager.find_word(original)
        
        if existing is None:
            suggestions.append({
                "original": original,
                "replacement": replacement,
                "category": "custom",
                "score": 2.0,
                "auto_generated": True,
                "confidence": calculate_confidence(original, replacement)
            })
    
    return suggestions
```

#### Шаг 7: Расчёт уверенности

```python
def calculate_confidence(original, replacement):
    """
    Определяет, насколько похожи слова.
    Высокая схожесть = скорее всего опечатка.
    Низкая схожесть = возможно, пользователь хочет другой термин.
    """
    # Расстояние Левенштейна
    distance = levenshtein_distance(original, replacement)
    max_len = max(len(original), len(replacement))
    
    similarity = 1 - (distance / max_len)
    
    if similarity > 0.7:
        return "high"    # "гитхаб" → "github" (похожи)
    elif similarity > 0.3:
        return "medium"  # "контрол" → "Ctrl" (средне)
    else:
        return "low"     # "гитхаб" → "GitHub Inc." (не похожи)
```

### Примеры определения ошибок

```
ASR: "гитхаб"
Финал: "GitHub"
Расстояние: 2 (h→H, добавить u, b)
Уверенность: high → предложение правила

ASR: "контрол шифт эс"
Финал: "Ctrl + Shift + S"
Расстояние: 10+ (очень разные)
Уверенность: low → предложение с осторожностью

ASR: "докер компоуз"
Финал: "Docker Compose"
Расстояние: 3 (d→D, о→o, к→c)
Уверенность: high → предложение правила
```

---

## 5. Интеграция с sherpa-onnx (детали)

### Конфигурация recognizer

```python
import sherpa_onnx

# Создание recognizer с hotwords
config = sherpa_onnx.OfflineRecognizerConfig()

# Модель
config.model.encoder_filename = "models/GigaAM/encoder.int8.onnx"
config.model.decoder_filename = "models/GigaAM/decoder.onnx"
config.model.joiner_filename = "models/GigaAM/joiner.onnx"
config.model.tokens_filename = "models/GigaAM/tokens.txt"
config.model.model_type = "nemo_transducer"

# Декодирование
config.decoding_method = "modified_beam_search"
config.max_active = 32
config.beam = 4

# Hotwords
config.hotwords_file = "hotwords_cache.txt"
config.hotwords_score = 2.0

# Создание recognizer
recognizer = sherpa_onnx.OfflineRecognizer(config)
```

### Процесс распознавания

```python
# 1. Создание stream
stream = recognizer.create_stream()

# 2. Передача аудио
sample_rate = 16000
audio_data = [...]  # float32 array
stream.accept_waveform(sample_rate, audio_data)

# 3. Декодирование
while recognizer.is_ready(stream):
    recognizer.decode(stream)

# 4. Получение результата
result = recognizer.get_result(stream)
text = result.text  # "открой GitHub"
```

### Формат hotwords файла (расширенный)

```
# Talker Box Vocabulary — auto-generated
# Version: 1.0
# Categories: programming, shortcuts
# Generated: 2026-09-08T12:00:00

# Программирование (15 слов)
pull request:3.0
commit:2.5
branch:2.5
repository:2.0
deploy:2.0
refactoring:2.0
debugging:2.0
frontend:2.0
backend:2.0
API:2.5
CI/CD:2.5
Docker:2.5
Kubernetes:2.0
microservice:2.0
repository:2.0

# Горячие клавиши (12 слов)
Ctrl + Shift + S:3.5
Ctrl + C:3.0
Alt + Tab:3.0
Win + .:2.5
Ctrl + Z:3.0
Ctrl + Y:3.0
Ctrl + A:3.0
Ctrl + S:3.0
Ctrl + V:3.0
Ctrl + X:3.0
F5:2.5
F12:2.5
```

### Важные замечания

1. **Modified beam search** обязателен для hotwords
2. **Score > 1.0** усиливает слово, **< 1.0** ослабляет
3. **Максимальный score** — khoảng 5.0 (выше не 효과но)
4. **Hotwords файл** перечитывается при каждом распознавании (если изменился)
5. **Память** — hotwords загружаются в оперативную память

---

## 6. Архитектура модуля (классы)

```
VocabularyManager
├── load_vocabulary(name) → dict
├── save_vocabulary(name, data)
├── get_active_words() → list
├── add_word(category, word, target, score)
├── remove_word(category, word)
└── get_categories() → list

HotwordsGenerator
├── __init__(vocabulary_manager)
├── generate(output_path) → str
├── update_score(word, new_score)
└── get_stats() → dict

PostProcessor
├── __init__(vocabulary_manager)
├── process(text) → str
├── add_replacement(original, replacement)
└── add_pattern(pattern, replacement)

AutoLearner
├── __init__(vocabulary_manager)
├── on_text_inserted(asr_text, final_text)
├── get_pending_suggestions() → list
├── accept_suggestion(index)
└── reject_suggestion(index)
```

---

## 7. Пример работы модуля (сценарий)

### Сценарий 1: Первый запуск

```
1. Программа стартует
2. VocabularyManager загружает:
   - programming.json (45 слов)
   - shortcuts.json (12 слов)
3. HotwordsGenerator создаёт hotwords_cache.txt
4. Transcriber загружает GigaAM + hotwords
5. Готово к работе
```

### Сценарий 2: Распознавание с hotwords

```
1. Пользователь: "Открой гит хаб"
2. Аудио → sherpa-onnx
3. Hotwords: "GitHub:3.0"
4. Модель видит буст → выбирает "GitHub"
5. Результат: "Открой GitHub"
6. PostProcessor: нет замен (hotwords уже справился)
7. Вставка: "Открой GitHub"
```

### Сценарий 3: Распознавание без hotwords

```
1. Пользователь: "Открой гит хаб"
2. Аудио → sherpa-onnx
3. Hotwords: нет (слово не в словаре)
4. Модель: "гитхаб" ( phonetically близко)
5. PostProcessor: правило "гитхаб" → "GitHub"
6. Вставка: "Открой GitHub"
```

### Сценарий 4: Авто-обучение

```
1. Пользователь: "Дай ссылку на гит лаб"
2. ASR: "Дай ссылку на гитлаб"
3. Пользователь исправляет вручную: "Дай ссылку на GitLab"
4. AutoLearner замечает разницу
5. Предложение: "гитлаб" → "GitLab"?
6. Пользователь: "Добавить"
7. Правило сохранено в vocabulary
```

---

## 8. Ограничения и особенности

### Ограничения sherpa-onnx hotwords

| Ограничение | Описание | Решение |
|-------------|----------|---------|
| **Точное совпадение** | Hotwords ищет точные фразы | Использовать пост-обработку для вариаций |
| **Длина фразы** | Макс. 3–5 слов в одной фразе | Разбивать длинные фразы |
| **Количество** | 1000–5000 слов (производительность) | Приоритизация, кэширование |
| **Cyrillic** | Поддерживается, но проверять | Тестировать на русском |

### Особенности GigaAM

| Особенность | Описание |
|-------------|----------|
| **NeMo transducer** | Требует `modified_beam_search` для hotwords |
| **INT8 квантизация** | Модель оптимизирована для CPU |
| **Русский язык** | Обучена на русской речи |
| **Формат аудио** | 16kHz, 16-bit, mono |

---

## 9. Чек-лист реализации

### Фаза 1: Ядро
- [ ] `vocabulary/manager.py` — загрузка/сохранение JSON
- [ ] `vocabulary/hotwords.py` — генерация hotwords файла
- [ ] Интеграция с `transcriber.py`
- [ ] Тесты на добавление/удаление слов

### Фаза 2: Пост-обработка
- [ ] `vocabulary/post_processor.py` — замены
- [ ] Regex-паттерны
- [ ] Интеграция с `main.py`

### Фаза 3: UI
- [ ] `ui/vocabulary_dialog.py` — главное окно
- [ ] Список категорий
- [ ] Список слов
- [ ] Добавление/удаление

### Фаза 4: Авто-обучение
- [ ] `vocabulary/auto_learner.py` — сравнение
- [ ] `ui/suggestion_dialog.py` — предложения
- [ ] Сохранение принятых правил

### Фаза 5: Словари
- [ ] `vocabularies/programming.json`
- [ ] `vocabularies/shortcuts.json`
- [ ] `vocabularies/software.json`
- [ ] Импорт/экспорт
