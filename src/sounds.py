import os
import struct
import wave
import tempfile

def generate_beep(frequency, duration_ms, volume=0.3):
    sample_rate = 44100
    num_samples = int(sample_rate * duration_ms / 1000)
    
    samples = []
    for i in range(num_samples):
        t = i / sample_rate
        envelope = 1.0 - (i / num_samples)
        value = volume * envelope * (1 if (t * frequency * 2 * 3.14159) % (2 * 3.14159) < 3.14159 else -1)
        samples.append(int(value * 32767))
    
    return samples, sample_rate

def save_wav(samples, sample_rate, filename):
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(struct.pack('<' + 'h' * len(samples), *samples))

def play_start_sound():
    try:
        import winsound
        samples, sr = generate_beep(800, 100, 0.2)
        temp_file = os.path.join(tempfile.gettempdir(), "talker_start.wav")
        save_wav(samples, sr, temp_file)
        winsound.PlaySound(temp_file, winsound.SND_FILENAME | winsound.SND_ASYNC)
    except:
        pass

def play_stop_sound():
    try:
        import winsound
        samples, sr = generate_beep(500, 150, 0.2)
        temp_file = os.path.join(tempfile.gettempdir(), "talker_stop.wav")
        save_wav(samples, sr, temp_file)
        winsound.PlaySound(temp_file, winsound.SND_FILENAME | winsound.SND_ASYNC)
    except:
        pass
