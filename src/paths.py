import os
import sys

def _get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(__file__))

def get_assets_dir():
    return os.path.join(_get_base_dir(), "assets")

def get_models_dir():
    return os.path.join(_get_base_dir(), "models")
