# -*- coding: utf-8 -*-
"""Иконки Talker Box: серый фон, зелёный куб (как в cube_logo.svg).
talker_box.ico — для рабочего стола/ярлыка/exe, с белым ободком 1 px по контуру.
talker_box.png — для трея и панели задач, без ободка."""
import os
import shutil
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.abspath(__file__))
BACKUP = os.path.join(ROOT, "icons_backup")
GRAY = (122, 122, 118, 255)
GREEN = (0, 194, 90)
SS = 4  # сглаживание: рисуем в 4 раза больше и уменьшаем

FACES = [
    ([(16, 2), (30, 9), (16, 16), (2, 9)], (0, 194, 90, 150)),
    ([(2, 9), (16, 16), (16, 30), (2, 23)], (0, 194, 90, 80)),
    ([(30, 9), (16, 16), (16, 30), (30, 23)], (0, 194, 90, 115)),
]


def render(size, outline):
    big = size * SS
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    radius = int(big * 0.18)
    d.rounded_rectangle([0, 0, big - 1, big - 1], radius=radius, fill=GRAY)
    cube = big * 0.70
    pad = big * 0.15
    k = cube / 32.0
    stroke = max(1, int(round(big * 0.035)))
    for pts, fill in FACES:
        poly = [(pad + x * k, pad + y * k) for x, y in pts]
        d.polygon(poly, fill=fill, outline=GREEN + (255,), width=stroke)
    if outline:
        w = SS  # ровно 1 px на итоговом размере
        d.rounded_rectangle([0, 0, big - 1, big - 1],
                            radius=radius, outline=(255, 255, 255, 255), width=w)
    return img.resize((size, size), Image.BOX)


def main():
    os.makedirs(BACKUP, exist_ok=True)
    for name in ("talker_box.png", "talker_box.ico"):
        src = os.path.join(ROOT, name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(BACKUP, name))
    ico_sizes = [16, 24, 32, 48, 64, 128, 256]
    png = render(256, outline=False)
    png.save(os.path.join(ROOT, "talker_box.png"))
    frames = [render(s, outline=True) for s in ico_sizes]
    frames[-1].save(os.path.join(ROOT, "talker_box.ico"), format="ICO",
                    sizes=[(s, s) for s in ico_sizes], append_images=frames[:-1])
    assets = os.path.join(ROOT, "installer", "assets")
    if os.path.isdir(assets):
        shutil.copy2(os.path.join(ROOT, "talker_box.ico"), os.path.join(assets, "talker_box.ico"))
    print("иконки обновлены")


if __name__ == "__main__":
    main()
