import os
import sys
import winsound

def _get_sounds_dir():
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, "sounds")
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "sounds")

SOUNDS_DIR = _get_sounds_dir()

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
