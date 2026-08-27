import os
import json
import numpy as np

class Transcriber:
    def __init__(self, model_config=None):
        self.model_config = model_config
        self.recognizer = None
        self.model_type = None
        if model_config:
            self.load_model(model_config)

    def load_model(self, config):
        self.model_config = config
        self.model_type = config.get("type", "sherpa-onnx")

        if self.model_type == "sherpa-onnx":
            self._load_sherpa_onnx(config)
        elif self.model_type == "whisper":
            self._load_whisper(config)
        elif self.model_type == "vosk":
            self._load_vosk(config)

    def _load_sherpa_onnx(self, config):
        try:
            import sherpa_onnx
            model_path = config.get("path", "")
            if not model_path or not os.path.exists(model_path):
                print(f"Model path not found: {model_path}")
                return

            model_file = os.path.join(model_path, "model.onnx")
            tokens_file = os.path.join(model_path, "tokens.txt")

            if not os.path.exists(model_file):
                print(f"model.onnx not found in {model_path}")
                return

            self.recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
                encoder=model_file,
                decoder=os.path.join(model_path, "decoder.onnx"),
                joiner=os.path.join(model_path, "joiner.onnx"),
                tokens=tokens_file,
                num_threads=4,
            )
            print(f"Loaded Sherpa-Onnx model: {config['name']}")
        except ImportError:
            print("sherpa-onnx not installed")
        except Exception as e:
            print(f"Error loading sherpa-onnx: {e}")

    def _load_whisper(self, config):
        print(f"Whisper model loading not implemented yet: {config['name']}")

    def _load_vosk(self, config):
        print(f"Vosk model loading not implemented yet: {config['name']}")

    def transcribe(self, audio_data, sample_rate=16000):
        if self.model_type == "sherpa-onnx":
            return self._transcribe_sherpa(audio_data, sample_rate)
        elif self.model_type == "whisper":
            return self._transcribe_whisper(audio_data, sample_rate)
        elif self.model_type == "vosk":
            return self._transcribe_vosk(audio_data, sample_rate)
        return ""

    def _transcribe_sherpa(self, audio_data, sample_rate):
        if not self.recognizer:
            return "[Model not loaded]"

        try:
            stream = self.recognizer.create_stream()
            audio_float = audio_data.astype(np.float32) / 32768.0
            stream.accept_waveform(sample_rate, audio_float)
            tail = np.zeros(sample_rate, dtype=np.float32)
            stream.accept_waveform(sample_rate, tail)
            stream.input_finished()

            result = []
            while self.recognizer.is_ready(stream):
                self.recognizer.decode_stream(stream)
            result = self.recognizer.get_result(stream)
            return result.strip()
        except Exception as e:
            return f"[Error: {e}]"

    def _transcribe_whisper(self, audio_data, sample_rate):
        return "[Whisper not implemented]"

    def _transcribe_vosk(self, audio_data, sample_rate):
        return "[Vosk not implemented]"
