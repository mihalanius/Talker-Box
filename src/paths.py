import os

def get_assets_dir():
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")

def get_models_dir():
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
