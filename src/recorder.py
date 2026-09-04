import sounddevice as sd
import numpy as np
import queue
import threading
from logger import log

class Recorder:
    def __init__(self, sample_rate=16000, channels=1):
        self.sample_rate = sample_rate
        self.channels = channels
        self.audio_queue = queue.Queue()
        self.frames = []
        self.is_recording = False
        self.stream = None

    def callback(self, indata, frames, time, status):
        if status:
            log("RECORDER_STATUS", str(status))
        self.audio_queue.put(indata.copy())

    def start(self):
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
        self.frames = []
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
        self.is_recording = True
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype='int16',
            callback=self.callback
        )
        self.stream.start()
        log("RECORDER_STARTED", f"rate={self.sample_rate}")

    def stop(self):
        self.is_recording = False
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
        audio = self.get_audio()
        log("RECORDER_STOPPED", f"frames={len(audio)}")
        return audio

    def get_level(self):
        items = []
        while not self.audio_queue.empty():
            try:
                items.append(self.audio_queue.get_nowait())
            except queue.Empty:
                break
        if items:
            audio = np.concatenate(items, axis=0)
            return float(np.abs(audio).mean()) / 32768.0
        return 0.0

    def get_audio(self):
        while not self.audio_queue.empty():
            try:
                self.frames.append(self.audio_queue.get_nowait())
            except queue.Empty:
                break
        if self.frames:
            return np.concatenate(self.frames, axis=0)
        return np.array([], dtype=np.int16)
