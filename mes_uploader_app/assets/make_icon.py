# -*- coding: utf-8 -*-
"""Sinh icon ninja (flat style, full-body) cho ứng dụng: ninja.png + ninja.ico.

Vẽ bằng Pillow ở độ phân giải cao (supersampling) rồi thu nhỏ cho nét.
Chạy:  python assets/make_icon.py
(Yêu cầu: pip install Pillow — chỉ là công cụ dev, không phải dep chạy app.)
"""

import os

from PIL import Image, ImageChops, ImageDraw

S = 1024  # canvas lớn để vẽ rồi thu nhỏ (khử răng cưa)

SLATE = (88, 95, 107, 255)      # đầu / thân (xám đậm)
SLATE_D = (70, 76, 87, 255)     # bóng tối
RED = (226, 86, 107, 255)       # băng đô / dây chéo
RED_D = (197, 67, 89, 255)
PEACH = (246, 201, 177, 255)    # vùng da
EYE = (44, 48, 56, 255)
BLADE = (203, 208, 216, 255)    # lưỡi kiếm
GOLD = (244, 197, 66, 255)      # chuôi kiếm
GOLD_D = (198, 152, 42, 255)
OUT = (33, 37, 44, 255)         # viền đậm
WHITE = (245, 247, 250, 255)


def _line(d, p0, p1, color, w):
    d.line([p0, p1], fill=color, width=w, joint="curve")
    r = w / 2
    for (x, y) in (p0, p1):
        d.ellipse((x - r, y - r, x + r, y + r), fill=color)


def make_base():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # --- 2 thanh kiếm chéo phía sau (chuôi dưới góc, mũi trên góc) ---
    swords = [((120, 902), (904, 196)), ((904, 902), (120, 196))]
    for h, t in swords:
        _line(d, h, t, OUT, 66)
        _line(d, h, t, BLADE, 42)
    for h, t in swords:                      # chuôi vàng gần tay cầm
        mx, my = h[0] + (t[0] - h[0]) * 0.23, h[1] + (t[1] - h[1]) * 0.23
        _line(d, h, (mx, my), OUT, 66)
        _line(d, h, (mx, my), GOLD, 42)
        d.ellipse((h[0] - 28, h[1] - 28, h[0] + 28, h[1] + 28),
                  fill=GOLD, outline=OUT, width=8)

    # --- Thân ninja (vai tròn, loe xuống) — đè lên đáy đầu cho liền khối ---
    body = (196, 560, 828, 986)
    d.rounded_rectangle(body, radius=190, fill=SLATE, outline=OUT, width=22)

    # --- Dây chéo ngực (đỏ) ---
    sash = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sash)
    _line(sd, (332, 612), (660, 980), OUT, 112)
    _line(sd, (332, 612), (660, 980), RED, 88)
    bmask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(bmask).rounded_rectangle(body, radius=190, fill=255)
    sash.putalpha(ImageChops.multiply(sash.split()[3], bmask))
    img.alpha_composite(sash)

    # --- Đầu ninja (ellipse) đè lên thân ---
    head = (198, 92, 826, 616)
    hmask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(hmask).ellipse(head, fill=255)
    d.ellipse(head, fill=SLATE)

    # --- Băng đô đỏ (cắt theo hình đầu) ---
    band = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    bd = ImageDraw.Draw(band)
    by0, by1 = 236, 372
    bd.rectangle((0, by0, S, by1), fill=RED)
    bd.rectangle((0, by1 - 42, S, by1), fill=RED_D)
    bd.line((0, by0, S, by0), fill=OUT, width=10)
    bd.line((0, by1, S, by1), fill=OUT, width=10)
    band.putalpha(ImageChops.multiply(band.split()[3], hmask))
    img.alpha_composite(band)

    # đuôi băng đô bay sang phải
    d.polygon([(800, 300), (936, 262), (902, 360)], fill=RED, outline=OUT, width=10)
    d.polygon([(812, 336), (944, 392), (868, 412)], fill=RED_D, outline=OUT, width=10)

    # --- Vùng mặt (da) + mắt — mask có bậc nhô ở giữa (sống mũi) ---
    d.rounded_rectangle((328, 388, 696, 486), radius=58, fill=PEACH,
                        outline=OUT, width=14)
    d.polygon([(470, 480), (554, 480), (512, 548)], fill=PEACH,
              outline=OUT, width=14)
    d.rectangle((472, 470, 552, 492), fill=PEACH)     # nối liền, xoá viền trùng
    for ex in (400, 588):                              # 2 mắt
        d.rounded_rectangle((ex, 420, ex + 40, 470), radius=18, fill=EYE)

    # --- Viền đầu (vẽ sau cùng cho nét) ---
    d.ellipse(head, outline=OUT, width=22)
    return img


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    img = make_base()
    sizes = [16, 24, 32, 48, 64, 128, 256]
    img.resize((256, 256), Image.LANCZOS).save(os.path.join(here, "ninja.png"))
    img.resize((256, 256), Image.LANCZOS).save(
        os.path.join(here, "ninja.ico"), format="ICO",
        sizes=[(s, s) for s in sizes])
    print("Đã tạo ninja.png + ninja.ico")


if __name__ == "__main__":
    main()
