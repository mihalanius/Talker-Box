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
        self.frames = []
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
            self.stream.stop()
            self.stream.close()
            self.stream = None
        return self.get_audio()

    def get_audio(self):
        while not self.audio_queue.empty():
            self.frames.append(self.audio_queue.get())
        if self.frames:
            return np.concatenate(self.frames, axis=0)
        return np.array([], dtype=np.int16)

    def get_audio_bytes(self):
        audio = self.get_audio()
        return audio.tobytes()
