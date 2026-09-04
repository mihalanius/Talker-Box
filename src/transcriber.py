import os
import json
import numpy as np

class Transcriber:
    def __init__(self, model_config=None):
        self.model_config = model_config
        self.recognizer = None
        self.model_type = None
        self.is_offline = False
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

            files = os.listdir(model_path)
            files_lower = [f.lower() for f in files]

            tokens_file = None
            for f in files:
                if f.lower() == "tokens.txt":
                    tokens_file = os.path.join(model_path, f)
                    break
            if not tokens_file:
                for f in files:
                    if "tokens" in f.lower() and f.lower().endswith(".txt"):
                        tokens_file = os.path.join(model_path, f)
                        break

            if not tokens_file:
                for item in files:
                    sub_path = os.path.join(model_path, item)
                    if os.path.isdir(sub_path) and not item.startswith("."):
                        sub_files = os.listdir(sub_path)
                        for f in sub_files:
                            if f.lower() == "tokens.txt" or ("tokens" in f.lower() and f.lower().endswith(".txt")):
                                tokens_file = os.path.join(sub_path, f)
                                model_path = sub_path
                                files = sub_files
                                break
                        if tokens_file:
                            break

            if not tokens_file:
                print(f"No tokens file found in {model_path}")
                for f in files:
                    print(f"  {f}")
                return

            encoder_file = None
            decoder_file = None
            joiner_file = None
            for f in files:
                fl = f.lower()
                if "encoder" in fl and fl.endswith(".onnx"):
                    encoder_file = os.path.join(model_path, f)
                elif "decoder" in fl and fl.endswith(".onnx"):
                    decoder_file = os.path.join(model_path, f)
                elif ("joint" in fl or "joiner" in fl) and fl.endswith(".onnx"):
                    joiner_file = os.path.join(model_path, f)

            if encoder_file and decoder_file and joiner_file:
                try:
                    self.recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
                        encoder=encoder_file,
                        decoder=decoder_file,
                        joiner=joiner_file,
                        tokens=tokens_file,
                        model_type="nemo_transducer",
                        feature_dim=64,
                        num_threads=4,
                    )
                    self.is_offline = True
                    print(f"Loaded Transducer (NeMo) model: {config['name']}")
                    return
                except Exception:
                    pass

                self.recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
                    encoder=encoder_file,
                    decoder=decoder_file,
                    joiner=joiner_file,
                    tokens=tokens_file,
                    num_threads=4,
                )
                self.is_offline = True
                print(f"Loaded Transducer model: {config['name']}")
                return

            model_file = None
            for f in files:
                fl = f.lower()
                if fl.endswith(".onnx") and "encoder" not in fl and "decoder" not in fl and "joint" not in fl:
                    model_file = os.path.join(model_path, f)
                    break
            if model_file:
                self.recognizer = sherpa_onnx.OfflineRecognizer.from_nemo_ctc(
                    model=model_file,
                    tokens=tokens_file,
                    num_threads=4,
                )
                self.is_offline = True
                print(f"Loaded CTC model: {config['name']}")
                return

            print(f"No recognized model files found in {model_path}")
            for f in files:
                print(f"  {f}")
        except ImportError:
            print("sherpa-onnx not installed")
        except Exception as e:
            print(f"Error loading sherpa-onnx: {e}")

    def _load_whisper(self, config):
        try:
            import sherpa_onnx
            model_path = config.get("path", "")
            if not model_path or not os.path.exists(model_path):
                print(f"Whisper model path not found: {model_path}")
                return

            files = os.listdir(model_path)

            tokens_file = None
            for f in files:
                if f.lower().endswith("-tokens.txt") or f.lower() == "tokens.txt":
                    tokens_file = os.path.join(model_path, f)
                    break

            encoder_file = None
            decoder_file = None
            for f in files:
                fl = f.lower()
                if fl.endswith("-encoder.onnx") or fl.endswith("-encoder.int8.onnx"):
                    encoder_file = os.path.join(model_path, f)
                elif fl.endswith("-decoder.onnx") or fl.endswith("-decoder.int8.onnx"):
                    decoder_file = os.path.join(model_path, f)

            if not encoder_file:
                for f in files:
                    fl = f.lower()
                    if "encoder" in fl and fl.endswith(".onnx"):
                        encoder_file = os.path.join(model_path, f)
                    elif "decoder" in fl and fl.endswith(".onnx"):
                        decoder_file = os.path.join(model_path, f)

            if not all([encoder_file, decoder_file, tokens_file]):
                print(f"Required files not found in {model_path}")
                for f in files:
                    print(f"  {f}")
                return

            self.recognizer = sherpa_onnx.OfflineRecognizer.from_whisper(
                encoder=encoder_file,
                decoder=decoder_file,
                tokens=tokens_file,
                num_threads=4,
            )
            self.is_offline = True
            print(f"Loaded Whisper model: {config['name']}")
        except ImportError:
            print("sherpa-onnx not installed")
        except Exception as e:
            print(f"Error loading whisper: {e}")

    def _load_vosk(self, config):
        try:
            from vosk import Model, KaldiRecognizer
            model_path = config.get("path", "")
            if not model_path or not os.path.exists(model_path):
                print(f"Vosk model path not found: {model_path}")
                return
            self.recognizer = Model(model_path)
            self.sample_rate = 16000
            print(f"Loaded Vosk model: {config['name']}")
        except ImportError:
            print("vosk not installed")
        except Exception as e:
            print(f"Error loading vosk: {e}")

    def transcribe(self, audio_data, sample_rate=16000):
        text = ""
        if self.model_type == "sherpa-onnx":
            text = self._transcribe_sherpa(audio_data, sample_rate)
        elif self.model_type == "whisper":
            text = self._transcribe_whisper(audio_data, sample_rate)
        elif self.model_type == "vosk":
            text = self._transcribe_vosk(audio_data, sample_rate)
        
        text = text.strip()
        while text.startswith("{") or text.startswith("["):
            text = text[1:]
        while text.endswith("}") or text.endswith("]"):
            text = text[:-1]
        text = text.strip()

        if text and not text.startswith("[") and text[-1] not in ".!?":
            text += "."
        return text

    def _transcribe_sherpa(self, audio_data, sample_rate):
        if not self.recognizer:
            return "[Model not loaded]"

        try:
            audio_float = audio_data.astype(np.float32).flatten() / 32768.0

            if self.is_offline:
                stream = self.recognizer.create_stream()
                stream.accept_waveform(sample_rate, audio_float)
                self.recognizer.decode_stream(stream)
                result = stream.result
                return result.text.strip()
            else:
                stream = self.recognizer.create_stream()
                stream.accept_waveform(sample_rate, audio_float)
                tail = np.zeros(sample_rate, dtype=np.float32)
                stream.accept_waveform(sample_rate, tail)
                stream.input_finished()
                while self.recognizer.is_ready(stream):
                    self.recognizer.decode_stream(stream)
                result = self.recognizer.get_result(stream)
                return result.strip()
        except Exception as e:
            return f"[Error: {e}]"

    def _transcribe_whisper(self, audio_data, sample_rate):
        if not self.recognizer:
            return "[Model not loaded]"
        try:
            audio_float = audio_data.astype(np.float32).flatten() / 32768.0
            stream = self.recognizer.create_stream()
            stream.accept_waveform(sample_rate, audio_float)
            self.recognizer.decode_stream(stream)
            result = stream.result
            return result.text.strip()
        except Exception as e:
            return f"[Error: {e}]"

    def _transcribe_vosk(self, audio_data, sample_rate):
        if not self.recognizer:
            return "[Model not loaded]"

        try:
            from vosk import KaldiRecognizer
            rec = KaldiRecognizer(self.recognizer, sample_rate)
            rec.SetWords(True)

            audio_bytes = audio_data.tobytes()
            rec.AcceptWaveform(audio_bytes)
            result = rec.FinalResult()

            import json as json_mod
            parsed = json_mod.loads(result)
            return parsed.get("text", "").strip()
        except Exception as e:
            return f"[Error: {e}]"
