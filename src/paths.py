import os
import sys


def get_base_dir():
    """Корневая директория проекта"""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(__file__))


def get_exe_dir():
    """Директория исполняемого файла"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(__file__))


def get_assets_dir():
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, "assets")
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")

def get_models_dir():
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), "models")
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
