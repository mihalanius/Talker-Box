import os
import winsound

SOUNDS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sounds")

def play_start_sound():
    try:
        wav = os.path.join(SOUNDS_DIR, "tap_01.wav")
        if os.path.exists(wav):
            winsound.PlaySound(wav, winsound.SND_FILENAME | winsound.SND_ASYNC)
    except:
        pass

def play_stop_sound():
    try:
        wav = os.path.join(SOUNDS_DIR, "tap_02.wav")
        if os.path.exists(wav):
            winsound.PlaySound(wav, winsound.SND_FILENAME | winsound.SND_ASYNC)
    except:
        pass

def play_hover_sound():
    try:
        wav = os.path.join(SOUNDS_DIR, "transition_up.wav")
        if os.path.exists(wav):
            winsound.PlaySound(wav, winsound.SND_FILENAME | winsound.SND_ASYNC)
    except:
        pass
