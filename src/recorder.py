import sounddevice as sd
import numpy as np
import queue
import threading

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
            print(f"Status: {status}")
        self.audio_queue.put(indata.copy())

    def start(self):
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except:
                pass
            self.stream = None
        self.frames = []
        self.audio_queue = queue.Queue()
        self.is_recording = True
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype='int16',
            callback=self.callback
        )
        self.stream.start()

    def stop(self):
        self.is_recording = False
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except:
                pass
            self.stream = None
        return self.get_audio()

    def get_level(self):
        items = []
        while not self.audio_queue.empty():
            items.append(self.audio_queue.get())
        for item in items:
            self.audio_queue.put(item)
        if items:
            audio = np.concatenate(items, axis=0)
            return float(np.abs(audio).mean()) / 32768.0
        return 0.0

    def get_audio(self):
        while not self.audio_queue.empty():
            self.frames.append(self.audio_queue.get())
        if self.frames:
            return np.concatenate(self.frames, axis=0)
        return np.array([], dtype=np.int16)
