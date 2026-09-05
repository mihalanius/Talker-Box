import os
import sys

def get_assets_dir():
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, "assets")
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")

def get_models_dir():
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), "models")
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
