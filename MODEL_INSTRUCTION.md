## Подключение GigaAM v3 trans-punct модели с пунктуацией

### Модель
`sherpa-onnx-nemo-transducer-punct-giga-am-v3-russian-2025-12-16` (225 МБ)
Путь: `D:\OpenCode_Arhive\Voice models\sherpa-onnx-nemo-transducer-punct-giga-am-v3-russian-2025-12-16`
Файлы: `encoder.int8.onnx`, `decoder.onnx`, `joiner.onnx`, `tokens.txt`

### Что изменить в transcriber.py
В методе `_load_sherpa_onnx`, блок где есть `decoder_file` и `joiner_file` (трансdukтерная модель):

**Было (CTC загрузка — НЕ работает с трансdukтером):**
```python
self.recognizer = sherpa_onnx.OfflineRecognizer.from_nemo_ctc(
    model=model_file,
    tokens=tokens_file,
    num_threads=4,
)
```

**Стало (правильная загрузка трансdukтера):**
```python
self.recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
    encoder=model_file,
    decoder=decoder_file,
    joiner=joiner_file,
    tokens=tokens_file,
    model_type="nemo_transducer",
    feature_dim=64,
    num_threads=4,
)
```

### Что изменить в settings.json
```json
{
  "active_model": "GigaAM v3 trans-punct",
  "models": [
    {
      "name": "GigaAM v3 trans-punct",
      "path": "D:\\OpenCode_Arhive\\Voice models\\sherpa-onnx-nemo-transducer-punct-giga-am-v3-russian-2025-12-16",
      "type": "sherpa-onnx",
      "language": "ru",
      "size": "225 MB"
    }
  ]
}
```

### Почему это работает
- NeMo трансdukтерные модели НЕ загружаются через `from_nemo_ctc` — выдают мусор
- Ключевой параметр: `model_type="nemo_transducer"` + `feature_dim=64`
- Модель распознаёт русскую речь с пунктуацией (точки, запятые, вопросительные знаки)
- Статус: `is_offline = True` (offline распознавание)

### Тестовый скрипт для проверки
```python
import sherpa_onnx, numpy as np, wave, os

model_path = r'D:\OpenCode_Arhive\Voice models\sherpa-onnx-nemo-transducer-punct-giga-am-v3-russian-2025-12-16'
rec = sherpa_onnx.OfflineRecognizer.from_transducer(
    encoder=model_path + '/encoder.int8.onnx',
    decoder=model_path + '/decoder.onnx',
    joiner=model_path + '/joiner.onnx',
    tokens=model_path + '/tokens.txt',
    model_type="nemo_transducer",
    feature_dim=64,
    num_threads=4,
)
wavs = os.path.join(model_path, 'test_wavs')
for f in os.listdir(wavs):
    if f.endswith('.wav'):
        wf = wave.open(os.path.join(wavs, f), 'rb')
        data = np.frombuffer(wf.readframes(-1), dtype=np.int16).astype(np.float32) / 32768.0
        sr = wf.getframerate()
        wf.close()
        stream = rec.create_stream()
        stream.accept_waveform(sr, data)
        rec.decode_stream(stream)
        print(f'{f}: {stream.result.text}')
```
