"""Chapter-agnostic In-Game UI, Menu, MonoBehaviour & Assembly-CSharp Localizer for Higurashi (Chapters 1-10).

Handles all 4 UI layers across all 10 Higurashi When They Cry Hou games (Ep01-Ep10):
1. sharedassets0.assets -> Texture2D NGUI Sprite Atlases & Backgrounds (matched by m_Name, not hardcoded path_id)
2. sharedassets0.assets -> MonoBehaviour (UILocalize & TextMeshPro dynamic button labels + Chapter Jump days)
3. Managed/Assembly-CSharp.dll -> #US User String Heap (Mod Menu F10 button & BGM Info overlay)
4. StreamingAssets/CG/scenario/ -> shortcuts.png & title.png
"""

from __future__ import annotations

import re
import shutil
import struct
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_BOLD = r"C:\Windows\Fonts\arialbd.ttf"
FONT_REG = r"C:\Windows\Fonts\arial.ttf"
FONT_SERIF_BOLD = r"C:\Windows\Fonts\georgiab.ttf"
FONT_SERIF_REG = r"C:\Windows\Fonts\georgia.ttf"
FONT_SERIF_ITALIC = r"C:\Windows\Fonts\georgiaz.ttf"

SCRIPT_TMP = 704374636544
SCRIPT_UILOCALIZE = 1382979469312

# Static UILabel / TextMeshPro / UILocalize dictionary across all 10 games
UI_LABEL_MAP: dict[str, str] = {
    "ON": "AÇIK",
    "OFF": "KAPALI",
    "Show Menu": "Menüyü Aç",
    "Hide Window": "Metni Gizle",
    "Remake": "Yenilenmiş",
    "Console": "Konsol",
    "Updated": "Güncel",
    "Original": "Orijinal",
    "English": "Türkçe",
    "Standard 1280x720": "Standart 1280x720",
    "Standard 640x480": "Standart 640x480",
    "Fullscreen": "Tam Ekran",
    "Continue\n": "Devam Et\n",
    "Continue": "Devam Et",
    "Back": "Geri",
    "Save & Load": "Kaydet & Yükle",
    "View All TIPS": "Tüm İpuçları",
    "View New TIPS": "Yeni İpuçları",
    "View TIPS": "İpuçlarını Gör",
    "All-Cast Review Session": "Kadro Değerlendirmesi",
    "Cast Review": "Kadro Değerlendirmesi",
    "Staff Room": "Yapımcı Odası",
    "Chapter Jump": "Bölüm Seçimi",
    "Chapter Jump!": "Bölüm Seçimi!",
    "Return to Extras Screen": "Ekstralara Dön",
    "Connecting Fragments": "Parçaları Birleştirmek",
    "2022 After Party": "2022 Kutlama Partisi",
    "Secret Staff Room": "Gizli Yapımcı Odası",
    "Scenario Unlock": "Senaryo Kilidi Aç",
    "Music Room": "Müzik Odası",
    "Music Room\n": "Müzik Odası\n",
    "Yes": "Evet",
    "Return": "Geri Dön",
    "Return\n": "Geri Dön\n",
    "Play": "Oynat",
    "Stop": "Durdur",
    "Repeat": "Tekrarla",
}

# Dynamic regex for "<ArcName> Day <N>", "<ArcName> <N>-<M>", "<ArcName> Epilogue <N>" across all chapters (Ep01-Ep10)
DAY_RE = re.compile(r"^([A-Za-z]+)\s+Day\s+(\d+)(?:-(\d+))?$")
BARE_DAY_RE = re.compile(r"^([A-Za-z]+)\s+(\d+)-(\d+)$")
BARE_PART_RE = re.compile(r"^([A-Za-z]+)\s+(\d+)$")
SUBCHAPTER_RE = re.compile(r"^([A-Za-z]+)\s+Part\s+(\d+)(?:-(\d+))?$")
EPILOGUE_RE = re.compile(r"^([A-Za-z]+)\s+Epilogue(?:\s+(\d+))?$")
PROLOGUE_RE = re.compile(r"^([A-Za-z]+)\s+Prologue(?:\s+(\d+))?$")


def translate_ui_label(text: str) -> str | None:
    """Translate a static or dynamic (Chapter Jump Day/Part/Epilogue) UI label into Turkish."""
    if text in UI_LABEL_MAP:
        return UI_LABEL_MAP[text]
    stripped = text.strip()
    m_day = DAY_RE.match(stripped)
    if m_day:
        arc, day, sub = m_day.group(1), m_day.group(2), m_day.group(3)
        return f"{arc} {day}. Gün - {sub}" if sub else f"{arc} {day}. Gün"
    m_bare = BARE_DAY_RE.match(stripped)
    if m_bare:
        arc, day, sub = m_bare.group(1), m_bare.group(2), m_bare.group(3)
        return f"{arc} {day}. Gün - {sub}"
    m_bpart = BARE_PART_RE.match(stripped)
    if m_bpart:
        arc, num = m_bpart.group(1), m_bpart.group(2)
        return f"{arc} {num}. Bölüm"
    m_part = SUBCHAPTER_RE.match(stripped)
    if m_part:
        arc, part, sub = m_part.group(1), m_part.group(2), m_part.group(3)
        return f"{arc} {part}. Bölüm - {sub}" if sub else f"{arc} {part}. Bölüm"
    m_ep = EPILOGUE_RE.match(stripped)
    if m_ep:
        arc, num = m_ep.group(1), m_ep.group(2)
        return f"{arc} Sonsöz {num}" if num else f"{arc} Sonsöz"
    m_pr = PROLOGUE_RE.match(stripped)
    if m_pr:
        arc, num = m_pr.group(1), m_pr.group(2)
        return f"{arc} Önsöz {num}" if num else f"{arc} Önsöz"
    return None


def pack_unity_str(s: str) -> bytes:
    b = s.encode("utf-8")
    pad = (4 - (len(b) % 4)) % 4
    return struct.pack("<I", len(b)) + b + (b"\x00" * pad)


def wipe_rect_from_row(arr: np.ndarray, x0: int, y0: int, x1: int, y1: int, ref_y: int) -> None:
    arr[y0:y1, x0:x1] = arr[ref_y : ref_y + 1, x0:x1]


def wipe_rect_from_col(arr: np.ndarray, x0: int, y0: int, x1: int, y1: int, ref_x: int) -> None:
    arr[y0:y1, x0:x1] = arr[y0:y1, ref_x : ref_x + 1]


def draw_styled_text(
    base_img: Image.Image,
    box: tuple[int, int, int, int],
    text: str,
    font_path: str,
    font_size: int,
    mode: str = "glow",
    align: str = "center",
    pad_x: int = 0,
    offset_y: int = 0,
    glow_radius: float = 2.0,
    stroke_width: int = 2,
) -> None:
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    font = ImageFont.truetype(font_path, font_size)
    while font_size > 8:
        bbox = font.getbbox(text)
        tw = bbox[2] - bbox[0]
        if tw <= w - 4 - pad_x:
            break
        font_size -= 1
        font = ImageFont.truetype(font_path, font_size)

    bbox = font.getbbox(text)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    if align == "center":
        tx = x0 + (w - tw) // 2 - bbox[0]
    elif align == "left":
        tx = x0 + pad_x - bbox[0]
    else:
        tx = x1 - pad_x - tw - bbox[0]
    ty = y0 + (h - th) // 2 - bbox[1] + offset_y

    overlay = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)

    if mode == "down_dark":
        odraw.text(
            (tx, ty),
            text,
            font=font,
            fill=(0, 0, 0, 255),
            stroke_width=stroke_width,
            stroke_fill=(0, 0, 0, 235),
        )
        overlay = overlay.filter(ImageFilter.GaussianBlur(radius=1.6))
        base_img.alpha_composite(overlay)
        return

    if mode == "dialog_header":
        glow_layer = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow_layer)
        gdraw.text(
            (tx, ty),
            text,
            font=font,
            fill=(255, 255, 255, 255),
            stroke_width=stroke_width + 3,
            stroke_fill=(255, 255, 255, 240),
        )
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=2.6))
        base_img.alpha_composite(glow_layer)
        odraw.text(
            (tx, ty),
            text,
            font=font,
            fill=(0, 0, 0, 255),
            stroke_width=stroke_width,
            stroke_fill=(255, 255, 255, 255),
        )
        base_img.alpha_composite(overlay)
        return

    if mode == "plain_white":
        odraw.text((tx, ty), text, font=font, fill=(255, 255, 255, 255))
        base_img.alpha_composite(overlay)
        return

    if mode == "glow":
        glow_layer = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow_layer)
        gdraw.text(
            (tx, ty),
            text,
            font=font,
            fill=(255, 255, 255, 210),
            stroke_width=stroke_width + 2,
            stroke_fill=(255, 255, 255, 180),
        )
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=glow_radius))
        base_img.alpha_composite(glow_layer)

    if mode == "red_first" and len(text) >= 2:
        glow_layer = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow_layer)
        gdraw.text(
            (tx, ty),
            text,
            font=font,
            fill=(255, 255, 255, 190),
            stroke_width=stroke_width + 1,
            stroke_fill=(255, 255, 255, 150),
        )
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=1.5))
        base_img.alpha_composite(glow_layer)
        odraw.text(
            (tx, ty),
            text,
            font=font,
            fill=(255, 255, 255, 255),
            stroke_width=stroke_width,
            stroke_fill=(0, 0, 0, 255),
        )
        odraw.text(
            (tx, ty),
            text[0],
            font=font,
            fill=(255, 30, 30, 255),
            stroke_width=stroke_width,
            stroke_fill=(0, 0, 0, 255),
        )
        base_img.alpha_composite(overlay)
        return

    odraw.text(
        (tx, ty),
        text,
        font=font,
        fill=(255, 255, 255, 255),
        stroke_width=stroke_width,
        stroke_fill=(0, 0, 0, 255),
    )
    base_img.alpha_composite(overlay)


def render_kai_title_label(text: str, w: int, h: int, letter_gap: int = 8) -> Image.Image:
    """Render a spaced-letter white label for the Kai (1024x1024) TitleHigurashi atlas."""
    scale = 2
    W, H = w * scale, h * scale
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    f = ImageFont.truetype(r"C:\Windows\Fonts\trebucbd.ttf", 17 * scale)
    cap_bbox = f.getbbox("A")
    cy = 1 * scale - cap_bbox[1]
    chars = list(text)
    advs: list[int] = []
    for ch in chars:
        if ch == " ":
            advs.append(6 * scale)
        else:
            bbox = f.getbbox(ch)
            advs.append(bbox[2] - bbox[0])
    total_w = sum(advs) + letter_gap * scale * (len(chars) - 1)
    cx = W - 2 - total_w
    for ch, cw in zip(chars, advs):
        if ch != " ":
            bbox = f.getbbox(ch)
            draw.text((cx - bbox[0], cy), ch, font=f, fill=(255, 255, 255, 255))
        cx += cw + letter_gap * scale
    return im.resize((w, h), Image.Resampling.LANCZOS)


def find_kai_title_sprites(env: Any) -> list[tuple[str, int, int, int, int, int, int, int]]:
    """Dynamically find Kai (1024x1024) TitleHigurashi normal & down sprite rects from UIAtlas."""
    default_items = [
        ("DEVAM ET", 324, 908, 198, 16, 966, 954, 9),
        ("AYARLAR",  524, 908, 143, 16, 986, 953, 8),
        ("EKSTRA",   669, 908, 116, 16, 1006, 954, 8),
        ("BAŞLA",    787, 908, 115, 16, 926, 955, 9),
        ("ÇIKIŞ",    904, 907,  89, 17, 946, 955, 8),
    ]
    spec = [
        ("continue", "DEVAM ET", 9),
        ("config",   "AYARLAR",  8),
        ("omake",    "EKSTRA",   8),
        ("start",    "BAŞLA",    9),
        ("quit",     "ÇIKIŞ",    8),
    ]
    for obj in env.objects:
        if obj.type.name == "MonoBehaviour":
            raw = bytes(obj.get_raw_data())
            if b"07copyright" in raw and b"start_normal" in raw and b"start_down" in raw:
                found: list[tuple[str, int, int, int, int, int, int, int]] = []
                for key, lbl, gap in spec:
                    sn = f"{key}_normal".encode("ascii")
                    sd = f"{key}_down".encode("ascii")
                    idx_n = raw.find(struct.pack("<I", len(sn)) + sn)
                    idx_d = raw.find(struct.pack("<I", len(sd)) + sd)
                    if idx_n != -1 and idx_d != -1:
                        off_n = idx_n + 4 + ((len(sn) + 3) & ~3)
                        off_d = idx_d + 4 + ((len(sd) + 3) & ~3)
                        vn = struct.unpack_from("<12i", raw, off_n)
                        vd = struct.unpack_from("<12i", raw, off_d)
                        xn, yn, wn, hn = vn[0], vn[1], vn[2], vn[3]
                        pad_l_n = vn[8]
                        yd = vd[1]
                        pad_l_d = vd[8]
                        xdr = (pad_l_n + wn) - pad_l_d
                        found.append((lbl, xn, yn, wn, hn, yd, xdr, gap))
                if len(found) == 5:
                    return found
    return default_items


def find_tips_exit_sprites(env: Any) -> list[tuple[int, int, str]]:
    """Dynamically find (x, y, mode) of exit_normal, exit_hover, exit_down in TipsPrefab UIAtlas."""
    default_coords = [
        (1440, 1518, "down_dark"),
        (480, 1367, "glow"),
        (1681, 1518, "glow"),
    ]
    for obj in env.objects:
        if obj.type.name == "MonoBehaviour":
            raw = obj.get_raw_data()
            if b"exit_normal" in raw and (b"tips000" in raw or b"tips_001" in raw or b"tipslocked" in raw):
                found: list[tuple[int, int, str]] = []
                for sname, mode in [("exit_down", "down_dark"), ("exit_hover", "glow"), ("exit_normal", "glow")]:
                    sb = sname.encode("ascii")
                    idx = raw.find(struct.pack("<I", len(sb)) + sb)
                    if idx != -1:
                        off = idx + 4 + ((len(sb) + 3) & ~3)
                        x, y, w, h = struct.unpack_from("<4i", raw, off)
                        if w == 240 and h == 77:
                            found.append((x, y, mode))
                if len(found) == 3:
                    return found
    return default_coords


def stamp_remilya_copyright(arr: np.ndarray, y0: int) -> None:
    """Replace 07copyright (322x24) at (0, y0) in TitleHigurashi with '(C) Ryukishi07 • TR: @Remilya'."""
    scale = 2
    w, h = 322, 24
    W, H = w * scale, h * scale
    f_bold = ImageFont.truetype(FONT_BOLD, 17 * scale)
    txt = "(C) Ryukishi07 • TR: @Remilya"
    b = f_bold.getbbox(txt)
    tx = (W - (b[2] - b[0])) // 2 - b[0]
    ty = (H - (b[3] - b[1])) // 2 - b[1]
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    draw.text((tx, ty), txt, font=f_bold, fill=(255, 255, 255, 255), stroke_width=4, stroke_fill=(255, 255, 255, 255))
    im = im.filter(ImageFilter.GaussianBlur(radius=1.2 * scale))
    fg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fdraw = ImageDraw.Draw(fg)
    fdraw.text((tx, ty), txt, font=f_bold, fill=(0, 0, 0, 255), stroke_width=1, stroke_fill=(0, 0, 0, 255))
    im.alpha_composite(fg)
    arr[y0 : y0 + h, 0:w] = np.array(im.resize((w, h), Image.Resampling.LANCZOS))


def localize_texture_by_name(
    name: str,
    img: Image.Image,
    tpl_90_norm_row: np.ndarray,
    tpl_90_hov_row: np.ndarray,
    tips_exit_coords: list[tuple[int, int, str]],
    kai_title_sprites: list[tuple[str, int, int, int, int, int, int, int]] | None = None,
) -> Image.Image | None:
    """Localize a single Texture2D image by its Unity m_Name."""
    arr = np.array(img)

    if name in ("SGMenu990000", "SGMenu990000_jp"):
        wipe_rect_from_row(arr, 12, 19, 245, 48, 19)
        wipe_rect_from_row(arr, 20, 130, 560, 530, 700)
        out = Image.fromarray(arr)
        draw_styled_text(out, (16, 18, 240, 48), "SİSTEM MENÜSÜ", FONT_BOLD, 22, mode="outline", align="left", pad_x=2, stroke_width=2)
        shortcuts = [
            (38, 144, "- Klavye Mod Kısayolları -", FONT_SERIF_ITALIC, 21),
            (38, 200, "F1 = NVL/ADV modunu değiştir", FONT_SERIF_ITALIC, 21),
            (38, 226, "F2 = Ses eşleştirme düzeyi (min 0, maks 5)", FONT_SERIF_ITALIC, 21),
            (94, 254, "Maks = Tam seslendirmeli PS3 metni (bazı yerler sansürlü olabilir)", FONT_SERIF_ITALIC, 13),
            (94, 270, "Min = Uygun yerlerde sesli orijinal PC metni (tamamen sansürsüz)", FONT_SERIF_ITALIC, 13),
            (94, 286, "Varsayılan seviye (2) en dengeli seçenektir", FONT_SERIF_ITALIC, 13),
            (38, 323, "F5 = Hızlı Kayıt", FONT_SERIF_ITALIC, 21),
            (38, 350, "F7 = Hızlı Yükle", FONT_SERIF_ITALIC, 21),
            (48, 399, "7 = Dudak senkronunu aç/kapat", FONT_SERIF_ITALIC, 21),
            (100, 426, "Yalnızca Nintendo Switch çizimleri için", FONT_SERIF_ITALIC, 13),
            (48, 448, "P = Çizim tarzı modunu değiştir", FONT_SERIF_ITALIC, 21),
            (100, 476, "Nintendo Switch, MangaGamer, 07th Expansion", FONT_SERIF_ITALIC, 13),
        ]
        draw = ImageDraw.Draw(out)
        for sx, sy, stext, sfont, ssize in shortcuts:
            f = ImageFont.truetype(sfont, ssize)
            draw.text((sx, sy), stext, font=f, fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 255))
        return out

    if name == "HigurashiMenu":
        buttons = [
            (0, 966, "AYARLAR", "down_dark"),
            (343, 966, "AYARLAR", "glow"),
            (0, 907, "AYARLAR", "glow"),
            (343, 907, "METNİ GİZLE", "down_dark"),
            (343, 848, "METNİ GİZLE", "glow"),
            (343, 789, "METNİ GİZLE", "glow"),
            (343, 730, "ANA MENÜYE DÖN", "down_dark"),
            (0, 612, "ANA MENÜYE DÖN", "glow"),
            (0, 494, "ANA MENÜYE DÖN", "glow"),
            (0, 376, "OYUNDAN ÇIK", "down_dark"),
            (0, 258, "OYUNDAN ÇIK", "glow"),
            (0, 140, "OYUNDAN ÇIK", "glow"),
            (0, 22, "KAYDET & YÜKLE", "down_dark"),
            (343, 671, "KAYDET & YÜKLE", "glow"),
            (343, 612, "KAYDET & YÜKLE", "glow"),
            (343, 553, "İPUÇLARINA DÖN", "down_dark"),
            (343, 435, "İPUÇLARINA DÖN", "glow"),
            (343, 317, "İPUÇLARINA DÖN", "glow"),
        ]
        for bx, by, label, mode in buttons:
            wipe_rect_from_row(arr, bx + 74, by + 7, bx + 324, by + 51, by + 7)
            wipe_rect_from_col(arr, bx + 320, by + 13, bx + 334, by + 45, bx + 318)
        out = Image.fromarray(arr)
        for bx, by, label, mode in buttons:
            draw_styled_text(out, (bx + 76, by + 6, bx + 324, by + 52), label, FONT_BOLD, 22, mode=mode, align="center", stroke_width=2)
        return out

    if name == "TitleHigurashi":
        if img.size == (1024, 256):
            # Rei (Ep09) 1024x256 TitleHigurashi atlas
            arr[7:31, 0:350] = 0
            arr[32:56, 0:200] = 0
            arr[57:81, 0:200] = 0
            arr[82:106, 0:200] = 0
            arr[232:256, 957:1024] = 0
            rei_items = [
                ("BAŞLA",    0,   7, 110, 24, 207),
                ("EKSTRA",   0,  32, 115, 24, 132),
                ("AYARLAR",  0,  57, 130, 24, 157),
                ("DEVAM ET", 0,  82, 145, 24, 182),
                ("ÇIKIŞ",  200,   7, 100, 24, 232),
            ]
            scale = 2
            f_rei = ImageFont.truetype(r"C:\Windows\Fonts\timesbd.ttf", 20 * scale)
            cap_b = f_rei.getbbox("A")
            for lbl, xn, yn, w, h, yd in rei_items:
                W, H = w * scale, h * scale
                bbox = f_rei.getbbox(lbl)
                tw = bbox[2] - bbox[0]
                tx = W - 5 * scale - tw - bbox[0]
                ty = 3 * scale - cap_b[1]
                sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                sdraw = ImageDraw.Draw(sh)
                sdraw.text((tx, ty + 1), lbl, font=f_rei, fill=(0, 0, 0, 255), stroke_width=3, stroke_fill=(0, 0, 0, 255))
                sh = sh.filter(ImageFilter.GaussianBlur(radius=2.6 * scale))
                fg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                fdraw = ImageDraw.Draw(fg)
                fdraw.text((tx, ty), lbl, font=f_rei, fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 220))
                sh.alpha_composite(fg)
                patch = np.array(sh.resize((w, h), Image.Resampling.LANCZOS))
                arr[yn : yn + h, xn : xn + w] = patch
                arr[yd : yd + h, 750:956] = [255, 0, 0, 255]
                sub = arr[yd : yd + h, 956 - w : 956].astype(float)
                alpha = patch[:, :, 3:4].astype(float) / 255.0
                comp = sub * (1.0 - alpha) + patch.astype(float) * alpha
                comp[:, :, 3] = 255.0
                arr[yd : yd + h, 956 - w : 956] = np.clip(comp, 0, 255).astype(np.uint8)
            stamp_remilya_copyright(arr, 107)
            return Image.fromarray(arr)

        if img.size == (1024, 1024):
            items = kai_title_sprites or [
                ("DEVAM ET", 324, 908, 198, 16, 966, 954, 9),
                ("AYARLAR",  524, 908, 143, 16, 986, 953, 8),
                ("EKSTRA",   669, 908, 116, 16, 1006, 954, 8),
                ("BAŞLA",    787, 908, 115, 16, 926, 955, 9),
                ("ÇIKIŞ",    904, 907,  89, 17, 946, 955, 8),
            ]
            for lbl, xn, yn, w, h, yd, xdr, gap in items:
                patch = np.array(render_kai_title_label(lbl, w, h, gap))
                arr[yn : yn + h, xn : xn + w] = patch
                arr[yd : yd + 18, 700:956] = [255, 0, 0, 255]
                sub = arr[yd + 1 : yd + 1 + h, xdr - w : xdr].astype(float)
                alpha = (patch[:, :, 3:4].astype(float)) / 255.0
                comp = sub * (1.0 - alpha) + patch.astype(float) * alpha
                arr[yd + 1 : yd + 1 + h, xdr - w : xdr] = np.clip(comp, 0, 255).astype(np.uint8)
            copy_y = 905 if (items and items[0][2] > 910) else 900
            stamp_remilya_copyright(arr, copy_y)
            return Image.fromarray(arr)

        if img.size == (512, 512) and arr[105, 15, 0] > 200 and arr[105, 15, 1] < 40:
            # Hou+ (Ep10) 512x512 left-aligned TitleHigurashi atlas
            arr[95:325, 336:512] = 0
            hou_items = [
                ("BAŞLA",    95),
                ("ÇIKIŞ",   140),
                ("EKSTRA",  185),
                ("YÜKLE",   230),
                ("AYARLAR", 275),
            ]
            scale = 2
            w, h = 140, 30
            f_hou = ImageFont.truetype(r"C:\Windows\Fonts\timesbd.ttf", 22 * scale)
            cap_b = f_hou.getbbox("A")
            for lbl, yd in hou_items:
                W, H = w * scale, h * scale
                bbox = f_hou.getbbox(lbl)
                tx = 7 * scale - bbox[0]
                ty = 6 * scale - cap_b[1]
                sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                sdraw = ImageDraw.Draw(sh)
                sdraw.text((tx, ty + 1), lbl, font=f_hou, fill=(0, 0, 0, 255), stroke_width=4, stroke_fill=(0, 0, 0, 255))
                sh = sh.filter(ImageFilter.GaussianBlur(radius=2.2 * scale))
                fg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                fdraw = ImageDraw.Draw(fg)
                fdraw.text((tx, ty), lbl, font=f_hou, fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 235))
                sh.alpha_composite(fg)
                patch = np.array(sh.resize((w, h), Image.Resampling.LANCZOS))
                arr[yd : yd + h, 337 : 337 + w] = patch
                wipe_rect_from_col(arr, 35, yd + 4, 210, yd + 40, 20)
                sub = arr[yd + 6 : yd + 6 + h, 43 : 43 + w].astype(float)
                alpha = patch[:, :, 3:4].astype(float) / 255.0
                comp = sub * (1.0 - alpha) + patch.astype(float) * alpha
                comp[:, :, 3] = 255.0
                arr[yd + 6 : yd + 6 + h, 43 : 43 + w] = np.clip(comp, 0, 255).astype(np.uint8)
            stamp_remilya_copyright(arr, 70)
            return Image.fromarray(arr)

        buttons = [
            (0, 869, "AYARLAR", "down_dark"),
            (0, 349, "AYARLAR", "glow"),
            (0, 921, "AYARLAR", "glow"),
            (0, 453, "DEVAM ET", "down_dark"),
            (0, 609, "DEVAM ET", "glow"),
            (0, 245, "DEVAM ET", "glow"),
            (0, 661, "ÇIKIŞ", "down_dark"),
            (0, 817, "ÇIKIŞ", "glow"),
            (0, 713, "ÇIKIŞ", "glow"),
            (0, 297, "EKSTRALAR", "down_dark"),
            (0, 765, "EKSTRALAR", "glow"),
            (0, 973, "EKSTRALAR", "glow"),
            (0, 505, "BAŞLA", "down_dark"),
            (0, 401, "BAŞLA", "glow"),
            (0, 557, "BAŞLA", "glow"),
        ]
        for bx, by, label, mode in buttons:
            wipe_rect_from_row(arr, bx + 20, by + 8, bx + 274, by + 43, by + 8)
        stamp_remilya_copyright(arr, 220)
        out = Image.fromarray(arr)
        for bx, by, label, mode in buttons:
            spaced = " ".join(list(label))
            draw_styled_text(out, (bx + 20, by + 6, bx + 274, by + 45), spaced, FONT_SERIF_BOLD, 21, mode=mode, align="center", stroke_width=2)
        return out

    if name in ("configbg", "configbg_jp"):
        # Distinguish red 07th-Mod configbg vs blue legacy configbg by sampling pixel (300, 30)
        r_sample, _, b_sample, _ = arr[30, 300]
        if r_sample > b_sample:
            labels = [
                "METİN KUTUSU SAYDAMLIĞI",
                "SESLENDİRME DÜZEYİ",
                "MÜZİK DÜZEYİ",
                "SES EFEKTLERİ DÜZEYİ",
                "METİN HIZI",
                "OTOMATİK MOD HIZI",
                "OKUNMAMIŞ METNİ ATLA",
                "ARAYÜZÜ GİZLE",
                "SAĞ TIK MENÜSÜ",
                "ONAY KUTULARINI GÖSTER",
                "KARAKTER ÇİZİMLERİ",
                "DİL",
                "EKRAN / EN-BOY ORANI",
            ]
            bars = [(17, 53), (68, 104), (119, 155), (171, 207), (222, 258), (273, 309), (324, 360), (375, 411), (426, 462), (477, 513), (528, 564), (579, 615), (630, 666)]
            wipe_rect_from_row(arr, 10, 36, 190, 94, 34)
            for y0, y1 in bars:
                wipe_rect_from_row(arr, 250, y0 + 4, 600, y1 - 3, y0 + 4)
            wipe_rect_from_row(arr, 440, 670, 1020, 696, 710)
            out = Image.fromarray(arr)
            draw_styled_text(out, (14, 34, 185, 76), "AYARLAR", FONT_REG, 30, mode="outline", align="left", pad_x=4, stroke_width=2)
            draw_styled_text(out, (14, 72, 185, 94), "SİSTEM AYARLARI", FONT_REG, 14, mode="outline", align="left", pad_x=4, stroke_width=2)
            for (y0, y1), lbl in zip(bars, labels):
                draw_styled_text(out, (256, y0 + 2, 600, y1 - 2), lbl, FONT_REG, 21, mode="outline", align="left", pad_x=2, stroke_width=2)
            draw_styled_text(out, (440, 670, 1015, 695), "* Standart üstü ekran modlarında bazı oyun öğeleri ölçeklendirilir.", FONT_REG, 15, mode="outline", align="right", pad_x=4, stroke_width=2)
            draw_styled_text(out, (380, 698, 1015, 722), "Türkçe Çeviri & Yerelleştirme: @Remilya  •  github.com/Remilya/Higurashi", FONT_BOLD, 14, mode="outline", align="right", pad_x=4, stroke_width=2)
            return out
        else:
            labels = [
                "METİN HIZI",
                "OTOMATİK MOD METİN HIZI",
                "OTOMATİK MOD İLERLEME HIZI",
                "METİN KUTUSU SAYDAMLIĞI",
                "MÜZİK DÜZEYİ",
                "SES DÜZEYİ",
                "OKUNMAMIŞ METNİ ATLA",
                "ARAYÜZÜ OTOMATİK GİZLE",
                "SAĞ TIK İŞLEVİ",
                "ONAY KUTULARINI GÖSTER",
                "KARAKTER ÇİZİMLERİ",
                "DİL",
                "EKRAN MODU",
            ]
            bars = [(20, 50), (71, 101), (122, 152), (173, 203), (225, 254), (276, 305), (327, 356), (378, 407), (429, 458), (480, 509), (531, 560), (582, 611), (633, 663)]
            wipe_rect_from_row(arr, 10, 36, 190, 94, 34)
            for y0, y1 in bars:
                wipe_rect_from_row(arr, 250, y0 + 2, 630, y1 - 2, y0 + 2)
            wipe_rect_from_row(arr, 440, 670, 1024, 696, 710)
            out = Image.fromarray(arr)
            draw_styled_text(out, (14, 34, 185, 76), "AYARLAR", FONT_SERIF_REG, 30, mode="plain_white", align="left", pad_x=4)
            draw_styled_text(out, (14, 72, 185, 94), "SİSTEM AYARLARI", FONT_SERIF_REG, 13, mode="plain_white", align="left", pad_x=4)
            for (y0, y1), lbl in zip(bars, labels):
                draw_styled_text(out, (256, y0 + 1, 630, y1 - 1), lbl, FONT_SERIF_REG, 21, mode="plain_white", align="left", pad_x=2)
            draw_styled_text(out, (440, 670, 1015, 695), "* Standart üstü ekran modlarında bazı oyun öğeleri ölçeklendirilir.", FONT_SERIF_REG, 15, mode="plain_white", align="right", pad_x=4)
            draw_styled_text(out, (380, 698, 1015, 722), "Türkçe Çeviri & Yerelleştirme: @Remilya  •  github.com/Remilya/Higurashi", FONT_SERIF_BOLD, 14, mode="plain_white", align="right", pad_x=4)
            return out

    if name == "saveloadbg":
        wipe_rect_from_row(arr, 12, 16, 245, 45, 17)
        qbars = [(643, 670, "Hızlı Kayıt 1"), (679, 706, "Hızlı Kayıt 2"), (714, 741, "Hızlı Kayıt 3")]
        for y0, y1, _ in qbars:
            wipe_rect_from_row(arr, 40, y0 + 2, 230, y1 - 2, y0 + 2)
        out = Image.fromarray(arr)
        draw_styled_text(out, (16, 15, 240, 45), "KAYDET & YÜKLE", FONT_BOLD, 22, mode="outline", align="left", pad_x=2, stroke_width=2)
        draw_styled_text(out, (16, 48, 245, 68), "TR Yama: @Remilya", FONT_BOLD, 13, mode="outline", align="left", pad_x=2, stroke_width=2)
        for y0, y1, lbl in qbars:
            draw_styled_text(out, (42, y0, 230, y1), lbl, FONT_REG, 20, mode="outline", align="left", pad_x=2, stroke_width=2)
        return out

    if name == "ConfigHigurashi":
        btns = [(0, 249, "glow"), (0, 425, "glow"), (0, 381, "down_dark")]
        for bx, by, _ in btns:
            wipe_rect_from_col(arr, bx + 25, by + 0, bx + 183, by + 10, bx + 25)
            wipe_rect_from_row(arr, bx + 18, by + 10, bx + 190, by + 39, by + 38)
        out = Image.fromarray(arr)
        for bx, by, mode in btns:
            draw_styled_text(out, (bx + 20, by + 6, bx + 188, by + 40), "KAPAT", FONT_BOLD, 25, mode=mode, align="center", stroke_width=2)
        return out

    if name == "Backlog":
        btns = [(0, 469, "glow"), (0, 381, "glow"), (0, 293, "down_dark")]
        for bx, by, _ in btns:
            wipe_rect_from_col(arr, bx + 25, by + 0, bx + 183, by + 10, bx + 25)
            wipe_rect_from_row(arr, bx + 18, by + 10, bx + 190, by + 39, by + 38)
        out = Image.fromarray(arr)
        for bx, by, mode in btns:
            draw_styled_text(out, (bx + 20, by + 6, bx + 188, by + 40), "KAPAT", FONT_BOLD, 25, mode=mode, align="center", stroke_width=2)
        return out

    if name == "saveloadhigurashi":
        close_btns = [(0, 937, "glow"), (209, 981, "glow"), (0, 893, "down_dark")]
        for bx, by, _ in close_btns:
            wipe_rect_from_col(arr, bx + 25, by + 0, bx + 183, by + 10, bx + 25)
            wipe_rect_from_row(arr, bx + 18, by + 10, bx + 190, by + 39, by + 38)
        big_btns = [
            (0, 787, 88, 52, "YÜKLE", "red_first"),
            (0, 734, 88, 52, "YÜKLE", "red_first"),
            (356, 787, 88, 52, "YÜKLE", "down_dark"),
            (267, 734, 88, 52, "KAYDET", "red_first"),
            (280, 840, 92, 52, "KAYDET", "red_first"),
            (94, 840, 92, 52, "KAYDET", "down_dark"),
            (373, 840, 88, 52, "SİL", "red_first"),
            (0, 840, 93, 52, "SİL", "red_first"),
            (187, 840, 92, 52, "SİL", "down_dark"),
            (356, 734, 88, 52, "SİL", "red_first"),
            (267, 787, 88, 52, "SİL", "red_first"),
            (0, 681, 88, 52, "SİL", "down_dark"),
        ]
        for bx, by, bw, bh, lbl, mode in big_btns:
            wipe_rect_from_row(arr, bx + 2, by + 11, bx + bw - 2, by + 41, by + 8)
        small_btns = [
            (171, 573, "YÜKLE", "glow", False),
            (171, 553, "YÜKLE", "glow", True),
            (262, 573, "YÜKLE", "down_dark", True),
            (353, 553, "KAYDET", "glow", False),
            (353, 573, "KAYDET", "glow", True),
            (262, 553, "KAYDET", "down_dark", True),
        ]
        for bx, by, lbl, mode, is_hov in small_btns:
            ref_row = tpl_90_hov_row if is_hov else tpl_90_norm_row
            arr[by + 2 : by + 17, bx + 5 : bx + 85] = ref_row[5:85]
        edit_btns = [(142, 526, "DÜZENLE", "glow"), (0, 526, "DÜZENLE", "glow"), (284, 526, "DÜZENLE", "down_dark")]
        for bx, by, lbl, mode in edit_btns:
            wipe_rect_from_row(arr, bx + 8, by + 2, bx + 62, by + 19, by + 19)
        out = Image.fromarray(arr)
        for bx, by, mode in close_btns:
            draw_styled_text(out, (bx + 20, by + 6, bx + 188, by + 40), "KAPAT", FONT_BOLD, 25, mode=mode, align="center", stroke_width=2)
        for bx, by, bw, bh, lbl, mode in big_btns:
            draw_styled_text(out, (bx + 4, by + 10, bx + bw - 4, by + 42), lbl, FONT_BOLD, 17, mode=mode, align="center", stroke_width=2)
        for bx, by, lbl, mode, _ in small_btns:
            draw_styled_text(out, (bx + 8, by + 1, bx + 82, by + 18), lbl, FONT_BOLD, 12, mode=mode, align="center", glow_radius=1.4, stroke_width=1)
        for bx, by, lbl, mode in edit_btns:
            draw_styled_text(out, (bx + 6, by + 1, bx + 64, by + 20), lbl, FONT_BOLD, 11, mode=mode, align="center", glow_radius=1.4, stroke_width=1)
        return out

    if name == "PromptHigurashi":
        prompt_btns = [
            (91, 282, "ORİJİNAL", "glow", False),
            (91, 366, "ORİJİNAL", "glow", True),
            (0, 261, "ORİJİNAL", "down_dark", True),
            (91, 324, "GÜNCEL", "glow", False),
            (91, 261, "GÜNCEL", "glow", True),
            (0, 366, "GÜNCEL", "down_dark", True),
            (0, 345, "TÜRKÇE", "glow", False),
            (91, 303, "TÜRKÇE", "glow", True),
            (0, 219, "TÜRKÇE", "down_dark", True),
            (0, 282, "HAYIR", "glow", False),
            (0, 492, "HAYIR", "glow", True),
            (0, 303, "HAYIR", "down_dark", True),
            (91, 387, "TAMAM", "glow", False),
            (91, 471, "TAMAM", "glow", True),
            (0, 450, "TAMAM", "down_dark", True),
            (91, 240, "EVET", "glow", False),
            (0, 324, "EVET", "glow", True),
            (91, 408, "EVET", "down_dark", True),
        ]
        for bx, by, lbl, mode, is_hov in prompt_btns:
            ref_row = tpl_90_hov_row if is_hov else tpl_90_norm_row
            arr[by + 1 : by + 19, bx + 5 : bx + 85] = ref_row[5:85]
        out = Image.fromarray(arr)
        for bx, by, lbl, mode, _ in prompt_btns:
            draw_styled_text(out, (bx + 6, by + 1, bx + 84, by + 19), lbl, FONT_BOLD, 12, mode=mode, align="center", glow_radius=1.5, stroke_width=1)
        return out

    if name == "MainUI":
        sq_norm_row = arr[112 + 6, 129 + 3 : 129 + 39].copy()
        sq_hov_row = arr[69 + 3, 0 + 3 : 0 + 39].copy()
        sq_btns = [
            (43, 26, "OTO", "glow", False),
            (43, 112, "OTO", "glow", True),
            (86, 26, "OTO", "down_dark", True),
            (86, 69, "GEÇMİŞ", "glow", False),
            (86, 112, "GEÇMİŞ", "glow", True),
            (0, 112, "GEÇMİŞ", "down_dark", True),
            (129, 112, "MENÜ", "glow", False),
            (0, 69, "MENÜ", "glow", True),
            (43, 69, "MENÜ", "down_dark", True),
            (129, 69, "ATLA", "glow", False),
            (172, 112, "ATLA", "glow", True),
            (0, 26, "ATLA", "down_dark", True),
        ]
        for bx, by, lbl, mode, is_hov in sq_btns:
            arr[by + 26 : by + 39, bx + 3 : bx + 39] = sq_hov_row if is_hov else sq_norm_row
        qs_btns = [
            (0, 189, "HIZLI YÜKLE", "glow"),
            (119, 223, "HIZLI YÜKLE", "glow"),
            (119, 189, "HIZLI YÜKLE", "down_dark"),
            (0, 155, "HIZLI KAYIT", "glow"),
            (119, 155, "HIZLI KAYIT", "glow"),
            (0, 223, "HIZLI KAYIT", "down_dark"),
        ]
        for bx, by, lbl, mode in qs_btns:
            wipe_rect_from_col(arr, bx + 10, by + 0, bx + 108, by + 17, bx + 10)
            wipe_rect_from_row(arr, bx + 8, by + 17, bx + 110, by + 29, by + 28)
        out = Image.fromarray(arr)
        for bx, by, lbl, mode, _ in sq_btns:
            draw_styled_text(out, (bx + 2, by + 25, bx + 40, by + 40), lbl, FONT_BOLD, 10, mode=mode, align="center", glow_radius=1.2, stroke_width=1)
        for bx, by, lbl, mode in qs_btns:
            draw_styled_text(out, (bx + 6, by + 4, bx + 112, by + 29), lbl, FONT_BOLD, 14, mode=mode, align="center", glow_radius=1.6, stroke_width=2)
        return out

    if name in ("chapterbanner", "chapterbanner_j") and img.size == (1024, 78):
        sub = arr[0:78, 0:847].copy()
        ref_row = sub[4].copy()
        ref_row[:, :3] = ref_row[10, :3]
        sub[5:74, 132:847] = ref_row[132:847]
        scale = 2
        txt_im = Image.new("RGBA", (847 * scale, 78 * scale), (0, 0, 0, 0))
        draw = ImageDraw.Draw(txt_im)
        f = ImageFont.truetype(r"C:\Windows\Fonts\trebuc.ttf", 54 * scale)
        cap_b = f.getbbox("A")
        draw.text((138 * scale - cap_b[0], 57 * scale - cap_b[3]), "Senaryo Seçimi", font=f, fill=(255, 255, 255, 255))
        t_arr = np.array(txt_im.resize((847, 78), Image.Resampling.LANCZOS)).astype(float)
        dst = sub.astype(float)
        sa = t_arr[:, :, 3:4] / 255.0
        da = dst[:, :, 3:4] / 255.0
        out_a = sa + da * (1.0 - sa)
        safe_a = np.where(out_a > 1e-5, out_a, 1.0)
        out_rgb = (t_arr[:, :, :3] * sa + dst[:, :, :3] * da * (1.0 - sa)) / safe_a
        sub[:, :, :3] = np.clip(out_rgb, 0, 255).astype(np.uint8)
        sub[:, :, 3:4] = np.clip(out_a * 255.0, 0, 255).astype(np.uint8)
        arr[0:78, 0:847] = sub
        return Image.fromarray(arr)

    if name in ("chapterdesc0", "chapterdesc0_j", "chapterdesc1", "chapterdesc1_j", "chapterdesc2", "chapterdesc2_j", "chapterdesc3", "chapterdesc3_j", "chapterlock", "chapterlock_j") and img.size == (475, 303):
        key = name[:-2] if name.endswith("_j") else name
        if key == "chapterlock":
            arr[5:298, 5:470] = [0, 0, 0, 128]
        else:
            arr[5:298, 35:470] = [0, 0, 0, 128]
            arr[35:298, 10:470] = [0, 0, 0, 128]
        scale = 2
        W, H = 475 * scale, 303 * scale
        txt_im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(txt_im)
        if key == "chapterlock":
            f_title = ImageFont.truetype(FONT_SERIF_REG, 25 * scale)
            title_txt = "Bu senaryo şu anda kilitli."
            tb = f_title.getbbox(title_txt)
            tx = (W - (tb[2] - tb[0])) // 2 - tb[0]
            ty = 128 * scale - f_title.getbbox("A")[1]
            draw.text((tx, ty), title_txt, font=f_title, fill=(255, 255, 255, 255))
            f_red = ImageFont.truetype(FONT_SERIF_REG, 15 * scale)
            cap_r = f_red.getbbox("A")[1]
            red_lines = [
                (178, "Outbreak bölümünü bitirerek kilidini açabilirsiniz."),
                (198, "*Ayrıca Ana Menü'deki Ekstra ekranından da senaryo"),
                (218, "kilidini kaldırabilirsiniz. Hou'yu daha önce bitirmiş"),
                (238, "olanlar için tasarlanmıştır."),
            ]
            for ry, rtxt in red_lines:
                draw.text((17 * scale, ry * scale - cap_r), rtxt, font=f_red, fill=(240, 10, 10, 235))
            f_sig = ImageFont.truetype(FONT_BOLD, 12 * scale)
            draw.text((17 * scale, 276 * scale - f_sig.getbbox("A")[1]), "TR Çeviri: @Remilya  •  github.com/Remilya/Higurashi", font=f_sig, fill=(200, 200, 200, 230))
        else:
            f_sans = r"C:\Windows\Fonts\trebucbd.ttf"
            spec_map: dict[str, list[tuple[int, int, int, str]]] = {
                "chapterdesc0": [
                    (38, 14, 20, "Higurashi When They Cry Outbreak"),
                    (17, 64, 18, "Keiichi ve diğerleri yepyeni bir trajediyle"),
                    (17, 94, 18, "yüzleşiyor. Gizemli virüs ve yarattığı panik"),
                    (17, 124, 18, "gerçekten gülünç bir manzara sunuyor."),
                    (17, 162, 18, "Zorluk seviyesi: Ortalama."),
                    (17, 192, 18, "Bu, sonun başlangıcı mı?"),
                    (17, 222, 18, "Yoksa çoktan sonuna ulaştı mı?"),
                    (17, 252, 18, "Buna tanıklık etmek sizin göreviniz."),
                ],
                "chapterdesc1": [
                    (38, 13, 20, "Higurashi When They Cry"),
                    (205, 38, 19, "Kamikashimashi Bölümü"),
                    (17, 80, 18, "Trajedi görünürde hiçbir son olmadan"),
                    (17, 108, 18, "Okinomiya'ya yayılıyor. Tüm bunların ardında"),
                    (17, 136, 18, "kim ve hangi amaçla var? Durdurulabilir mi?"),
                    (17, 164, 18, "Higurashi Outbreak hikâyesi burada son buluyor."),
                    (17, 198, 18, "Zorluk seviyesi: İnsanüstü."),
                    (17, 226, 18, "Lütfen kulüp üyelerinin son savaşına"),
                    (17, 254, 18, "tanıklık edin."),
                ],
                "chapterdesc2": [
                    (38, 13, 20, "Hinamizawa Otobüs Durağı:"),
                    (150, 38, 18, "Higurashi When They Cry Köken"),
                    (17, 84, 18, "Hinamizawa'ya hoş geldiniz."),
                    (17, 114, 18, "Bu, biraz sıra dışı bir parça."),
                    (17, 144, 18, "İleride büyüyüp Higurashi When They Cry'a"),
                    (17, 174, 18, "dönüşecek olan ilk orijinal parça."),
                    (17, 208, 18, "Zorluk seviyesi: 'Yaratılış'."),
                    (17, 238, 18, "Her şey buradan başladı."),
                ],
                "chapterdesc3": [
                    (38, 13, 19, "Higurashi When They Cry Mehagashi Bölümü"),
                    (205, 37, 18, "(Hou+ Ek Senaryosu)"),
                    (17, 74, 17, "Yalnızca insanlığı değil, tüm galaksiyi yok"),
                    (17, 99, 17, "edebilecek bir trajedi yaklaşıyor... Maebara"),
                    (17, 124, 17, "Keiichi! Evreni korumak için kızların mayolarını"),
                    (17, 149, 17, "çıkar! Peki Keiichi kulüp üyelerine karşı tek"),
                    (17, 174, 17, "başına kazanabilir mi...?"),
                    (17, 206, 17, "Zorluk seviyesi: 'Mutlak Tehlike'."),
                    (17, 231, 17, "Keiichi'nin korkunç bir sondan kurtulmasının"),
                    (17, 256, 17, "hiçbir yolu yok gibi görünüyor."),
                ],
            }
            for lx, ly, lsz, ltxt in spec_map[key]:
                f_line = ImageFont.truetype(f_sans, lsz * scale)
                cap_y = f_line.getbbox("A")[1]
                draw.text((lx * scale, ly * scale - cap_y), ltxt, font=f_line, fill=(255, 255, 255, 255))
            f_sig = ImageFont.truetype(f_sans, 12 * scale)
            draw.text((17 * scale, 281 * scale - f_sig.getbbox("A")[1]), "TR Çeviri: @Remilya  •  github.com/Remilya/Higurashi", font=f_sig, fill=(200, 200, 200, 230))
        t_arr = np.array(txt_im.resize((475, 303), Image.Resampling.LANCZOS)).astype(float)
        dst = arr.astype(float)
        sa = t_arr[:, :, 3:4] / 255.0
        da = dst[:, :, 3:4] / 255.0
        out_a = sa + da * (1.0 - sa)
        safe_a = np.where(out_a > 1e-5, out_a, 1.0)
        out_rgb = (t_arr[:, :, :3] * sa + dst[:, :, :3] * da * (1.0 - sa)) / safe_a
        arr[:, :, :3] = np.clip(out_rgb, 0, 255).astype(np.uint8)
        arr[:, :, 3:4] = np.clip(out_a * 255.0, 0, 255).astype(np.uint8)
        return Image.fromarray(arr)

    if name == "ChapterPreview":
        if img.size == (2048, 1024):
            # Distinguish Hou+ (Ep10) 2048x1024 ChapterPreview vs Rei (Ep09) 2048x1024 ChapterPreview
            if arr[869 + 38, 1442 + 120, 0] == 255 and arr[425, 10, 3] == 128:
                lock_patch = np.array(
                    localize_texture_by_name(
                        "chapterlock",
                        Image.fromarray(arr[417 : 417 + 303, 0:475].copy()),
                        tpl_90_norm_row,
                        tpl_90_hov_row,
                        tips_exit_coords,
                        kai_title_sprites,
                    )
                )
                arr[417 : 417 + 303, 0:475] = lock_patch
                arr[721 : 721 + 303, 0:475] = lock_patch
                for bx, by, bg_rgb, fg_rgb in [
                    (1442, 869, (255, 255, 255, 255), (180, 29, 10, 255)),
                    (1330, 755, (255, 246, 137, 255), (59, 0, 137, 255)),
                    (1442, 947, (255, 246, 137, 255), (59, 0, 137, 255)),
                ]:
                    arr[by + 14 : by + 63, bx + 14 : bx + 226] = bg_rgb
                    scale = 2
                    bw, bh = 212, 49
                    btn_im = Image.new("RGBA", (bw * scale, bh * scale), bg_rgb)
                    bdraw = ImageDraw.Draw(btn_im)
                    f_exit = ImageFont.truetype(FONT_SERIF_REG, 34 * scale)
                    eb = f_exit.getbbox("ÇIKIŞ")
                    ex = (bw * scale - (eb[2] - eb[0])) // 2 - eb[0]
                    ey = (bh * scale - (eb[3] - eb[1])) // 2 - eb[1]
                    bdraw.text((ex, ey), "ÇIKIŞ", font=f_exit, fill=fg_rgb)
                    arr[by + 14 : by + 63, bx + 14 : bx + 226] = np.array(
                        btn_im.resize((bw, bh), Image.Resampling.LANCZOS)
                    )
                return Image.fromarray(arr)

            emo_patch = arr[676 + 78 : 676 + 106, 362:436].copy()
            font_sans_reg = r"C:\Windows\Fonts\trebuc.ttf"
            font_sans_bold = r"C:\Windows\Fonts\trebucbd.ttf"

            def _draw_bar(bx: int, by: int, bw: int, bh: int, wipe_x0: int, text: str, tx: int, baseline_y: int, fp: str, fsz: int) -> None:
                sub = arr[by : by + bh, bx : bx + bw].copy()
                ref_row = sub[4].copy()
                ref_row[:, :3] = ref_row[10, :3]
                sub[5 : bh - 4, wipe_x0:bw] = ref_row[wipe_x0:bw]
                scale = 2
                txt_im = Image.new("RGBA", (bw * scale, bh * scale), (0, 0, 0, 0))
                draw = ImageDraw.Draw(txt_im)
                f = ImageFont.truetype(fp, fsz * scale)
                cap_b = f.getbbox("A")
                draw.text((tx * scale - cap_b[0], baseline_y * scale - cap_b[3]), text, font=f, fill=(255, 255, 255, 255))
                t_arr = np.array(txt_im.resize((bw, bh), Image.Resampling.LANCZOS)).astype(float)
                dst = sub.astype(float)
                sa = t_arr[:, :, 3:4] / 255.0
                da = dst[:, :, 3:4] / 255.0
                out_a = sa + da * (1.0 - sa)
                safe_a = np.where(out_a > 1e-5, out_a, 1.0)
                out_rgb = (t_arr[:, :, :3] * sa + dst[:, :, :3] * da * (1.0 - sa)) / safe_a
                sub[:, :, :3] = np.clip(out_rgb, 0, 255).astype(np.uint8)
                sub[:, :, 3:4] = np.clip(out_a * 255.0, 0, 255).astype(np.uint8)
                arr[by : by + bh, bx : bx + bw] = sub

            # 1. chapterbanner & chapterbanner_j
            _draw_bar(598, 790, 847, 78, 132, "Senaryo Seçimi", 138, 57, font_sans_reg, 54)
            arr[711 : 711 + 78, 598 : 598 + 847] = arr[790 : 790 + 78, 598 : 598 + 847]

            # 2. chapterbutton0/1/2 (normal & down) + _j copies
            btn_specs = [
                (1446, 805, 600, 63, 315, 321, "~En Kötü Seçenek~", 0, 172, 565),
                (1446, 726, 600, 63, 315, 321, "~En Kötü Seçenek~", 0, 108, 565),
                (598,  647, 758, 63, 364, 371, "~Aşkın En Güçlü Takipçisi~", 0, 300, 595),
                (598,  583, 758, 63, 364, 371, "~Aşkın En Güçlü Takipçisi~", 0, 236, 595),
                (598,  519, 719, 63, 350, 361, "~En Korkunç Gündüz Düşü~", 0, 44, 565),
                (598,  455, 719, 63, 350, 361, "~En Korkunç Gündüz Düşü~", 598, 391, 565),
            ]
            for bx, by, bw, bh, wx0, tx, lbl, jx, jy, jw in btn_specs:
                _draw_bar(bx, by, bw, bh, wx0, lbl, tx, 47, font_sans_bold, 22)
                arr[jy : jy + bh, jx : jx + jw] = arr[by : by + bh, bx : bx + jw]

            # 3. start & exit normal/hover/jp
            for bx, by, bw, bh in [(1357, 599, 534, 55), (1357, 655, 534, 55), (598, 279, 535, 55), (598, 335, 535, 55)]:
                _draw_bar(bx, by, bw, bh, 35, "Başla", 43, 37, font_sans_reg, 33)
            for bx, by, bw, bh in [(598, 111, 534, 55), (598, 223, 534, 55), (598, 55, 534, 55), (598, 167, 534, 55)]:
                _draw_bar(bx, by, bw, bh, 35, "Çıkış", 44, 37, font_sans_reg, 33)

            # 4. chapterdesc0, chapterdesc1, chapterdesc2
            def _render_desc(w: int, h: int, lines: list[tuple[int, str]], emo_idx: int | None = None) -> np.ndarray:
                scale = 2
                W, H = w * scale, h * scale
                f = ImageFont.truetype(font_sans_bold, 18 * scale)
                sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                sdraw = ImageDraw.Draw(sh)
                fg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                fdraw = ImageDraw.Draw(fg)
                emo_x = 0
                for idx, (ly, ltxt) in enumerate(lines):
                    cur_f = f
                    cur_sz = 18 * scale
                    while cur_sz > 14 * scale:
                        b = cur_f.getbbox(ltxt)
                        if (b[2] - b[0]) <= (w - 12) * scale:
                            break
                        cur_sz -= 1
                        cur_f = ImageFont.truetype(font_sans_bold, cur_sz)
                    ty = ly * scale - cur_f.getbbox("A")[1]
                    tx = 6 * scale - cur_f.getbbox(ltxt)[0]
                    sdraw.text((tx, ty + 1), ltxt, font=cur_f, fill=(0, 0, 0, 255), stroke_width=5, stroke_fill=(0, 0, 0, 255))
                    fdraw.text((tx, ty), ltxt, font=cur_f, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 255))
                    if emo_idx == idx:
                        b = cur_f.getbbox(ltxt)
                        emo_x = (6 * scale + (b[2] - b[0])) // scale + 4
                sh = sh.filter(ImageFilter.GaussianBlur(radius=1.8 * scale))
                sh.alpha_composite(fg)
                out_arr = np.array(sh.resize((w, h), Image.Resampling.LANCZOS))
                if emo_idx is not None and emo_x + emo_patch.shape[1] <= w:
                    eh, ew = emo_patch.shape[:2]
                    out_arr[78 : 78 + eh, emo_x : emo_x + ew] = emo_patch
                return out_arr

            desc0 = _render_desc(592, 160, [
                (6,   "Bu, 1983 yazına ulaşan Furude Rika’nın hikâyesidir."),
                (32,  "Gücü ona pek çok dünyadan birini seçme imkânı tanır;"),
                (58,  "peki bu dünya onun için gerçekten en iyisi midir?"),
                (110, "Buradaki zorluk seviyesi oldukça acımasızdır. Böylesini"),
                (136, "tercih eden tüm değerli erbabın beğenisine sunulur."),
            ])
            desc1 = _render_desc(597, 160, [
                (6,   "Bu, karşılıklı aşk bahşedebilen değerli mücevherler olan"),
                (32,  "Fuwarazu Magataması uğruna kulüp üyelerinin karıştığı"),
                (58,  "tuhaf bir çekişmenin hikâyesidir. Higurashi Daybreak’i"),
                (84,  "oynamamış olanlar da keyifle oynayabilir."),
                (136, "Diğer eşleşmeler için lütfen Higurashi Daybreak’in tadını çıkarın~!"),
            ], emo_idx=3)
            desc2 = _render_desc(597, 187, [
                (6,   "Bu sayfaların arasında, günümüzün ilgisiz gençleri için"),
                (32,  "alev alev yanan bir tutku kutsal kitabı yatıyor! Meakashi-hen"),
                (58,  "sonrası bir kutlama olarak tasarlanmış olsa da o bölümün"),
                (84,  "etkisini tamamen yerle bir ediyor! Tüketilmesi fazla tehlikeli"),
                (110, "bulunan bu efsanevi senaryo mühürlenerek kaldırılmıştı!"),
                (162, "Yalnızca gerçekten yozlaşmış olduğunuza ant içerseniz devam edin."),
            ])
            arr[515 : 515 + 160, 0:592] = desc0
            arr[676 : 676 + 160, 0:597] = desc1
            arr[837 : 837 + 187, 0:597] = desc2
            return Image.fromarray(arr)

        bars: list[tuple[int, int, str]] = []
        for by in (577, 689, 745, 801):
            sub = arr[by + 10 : by + 42, 15:160]
            white = (sub[:, :, 0] > 200) & (sub[:, :, 1] > 200) & (sub[:, :, 2] > 200)
            cols = np.where(white.any(axis=0))[0]
            w = int(cols.max() - cols.min() + 1) if len(cols) else 0
            bars.append((0, by, "Başla" if w > 72 else "Çıkış"))
        for bx, by, lbl in bars:
            wipe_rect_from_row(arr, bx + 10, by + 11, bx + 160, by + 40, by + 11)
        out = Image.fromarray(arr)
        for bx, by, lbl in bars:
            draw_styled_text(out, (bx + 18, by + 10, bx + 200, by + 42), lbl, FONT_REG, 22, mode="outline", align="left", pad_x=2, stroke_width=1)
        return out

    if name == "TipsPrefab":
        for bx, by, mode in tips_exit_coords:
            wipe_rect_from_col(arr, bx + 35, by + 0, bx + 205, by + 23, bx + 35)
            wipe_rect_from_row(arr, bx + 25, by + 23, bx + 215, by + 74, by + 72)
        out = Image.fromarray(arr)
        for bx, by, mode in tips_exit_coords:
            draw_styled_text(out, (bx + 20, by + 12, bx + 220, by + 68), "ÇIKIŞ", FONT_BOLD, 30, mode=mode, align="center", stroke_width=2)
        return out

    small_dialog_map = {
        "dialog_areyousure": "EMİN MİSİNİZ?",
        "dialog_areyousure_jp": "EMİN MİSİNİZ?",
        "dialog_delete": "VERİ SİLİNSİN Mİ?",
        "dialog_delete_jp": "VERİ SİLİNSİN Mİ?",
        "dialog_exit": "SENARYODAN ÇIKILSIN MI?",
        "dialog_exit_jp": "SENARYODAN ÇIKILSIN MI?",
    }
    if name in small_dialog_map and img.size == (349, 74):
        wipe_rect_from_col(arr, 35, 0, 302, 42, 35)
        out = Image.fromarray(arr)
        draw_styled_text(out, (20, 2, 329, 40), small_dialog_map[name], FONT_BOLD, 22, mode="dialog_header", align="center", stroke_width=2)
        return out

    med_dialog_map = {
        "dialog_edit": "VERİ DÜZENLENSİN Mİ?",
        "dialog_edit_jp": "VERİ DÜZENLENSİN Mİ?",
        "dialog_load": "VERİ YÜKLENSİN Mİ?",
        "dialog_load_jp": "VERİ YÜKLENSİN Mİ?",
        "dialog_save": "VERİ KAYDEDİLSİN Mİ?",
        "dialog_save_jp": "VERİ KAYDEDİLSİN Mİ?",
    }
    if name in med_dialog_map and img.size == (486, 195):
        wipe_rect_from_col(arr, 150, 0, 355, 40, 150)
        out = Image.fromarray(arr)
        draw_styled_text(out, (130, 2, 365, 38), med_dialog_map[name], FONT_BOLD, 22, mode="dialog_header", align="center", stroke_width=2)
        return out

    if name == "dialog_language" and img.size == (349, 173):
        arr[62:105, 48:302] = [0, 0, 0, 255]
        out = Image.fromarray(arr)
        draw_styled_text(out, (45, 64, 304, 102), "LÜTFEN BİR DİL SEÇİN.", FONT_BOLD, 20, mode="dialog_header", align="center", stroke_width=2)
        return out

    return None


def localize_game_ui(data_dir: Path, backup_dir: Path | None = None) -> dict[str, int]:
    """Localize sharedassets0.assets, Assembly-CSharp.dll, and StreamingAssets/CG/scenario in any HigurashiEpXX_Data folder."""
    class _ObjType:
        def __init__(self, cid: int) -> None:
            self.name = "Texture2D" if cid == 28 else ("MonoBehaviour" if cid == 114 else "Other")

    class _Tex2DView:
        def __init__(self, obj: "_PureObj", ver: int) -> None:
            self._obj = obj
            raw = obj._raw
            nlen = struct.unpack_from("<I", raw, 0)[0]
            self.m_Name = raw[4 : 4 + nlen].decode("utf-8", errors="replace")
            off = 4 + ((nlen + 3) & ~3)
            if ver >= 20:
                off += 8
            self.m_Width, self.m_Height = struct.unpack_from("<II", raw, off)
            self._img: Image.Image | None = None
            self._off = off

        @property
        def image(self) -> Image.Image:
            if self._img is None:
                raw = self._obj._raw
                plen = self.m_Width * self.m_Height * 4
                idx1 = raw.find(struct.pack("<I", plen), self._off)
                idx2 = raw.find(struct.pack("<I", plen), idx1 + 4)
                self._img = Image.frombytes("RGBA", (self.m_Width, self.m_Height), raw[idx2 + 4 : idx2 + 4 + plen]).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            return self._img

        @image.setter
        def image(self, val: Image.Image) -> None:
            self._img = val

        def save(self) -> None:
            if self._img is None:
                return
            raw = self._obj._raw
            plen = self.m_Width * self.m_Height * 4
            idx1 = raw.find(struct.pack("<I", plen), self._off)
            idx2 = raw.find(struct.pack("<I", plen), idx1 + 4)
            flipped = self._img.convert("RGBA").transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes()
            self._obj._raw = raw[: idx2 + 4] + flipped + raw[idx2 + 4 + plen :]

    class _PureObj:
        def __init__(self, pid: int, cid: int, tail: bytes, raw: bytes, ver: int) -> None:
            self.path_id = pid
            self.type = _ObjType(cid)
            self._tail = tail
            self._raw = raw
            self._ver = ver

        def get_raw_data(self) -> bytes:
            return self._raw

        def set_raw_data(self, data: bytes) -> None:
            self._raw = bytes(data)

        def read(self, check_read: bool = False) -> _Tex2DView:
            return _Tex2DView(self, self._ver)

    class _PureEnv:
        def __init__(self, path: Path) -> None:
            raw = path.read_bytes()
            meta_sz, file_sz, ver, data_off = struct.unpack(">IIII", raw[:16])
            self._ver = ver
            self._endian_bytes = raw[16:20]
            pos = raw.index(b"\x00", 20) + 1 + 4
            enable_tt = raw[pos] != 0
            pos += 1
            type_count = struct.unpack_from("<i", raw, pos)[0]
            pos += 4
            type_class_ids: list[int] = []
            for _ in range(type_count):
                cid = struct.unpack_from("<i", raw, pos)[0]
                pos += 4
                type_class_ids.append(cid)
                if ver >= 16:
                    pos += 1
                if ver >= 17:
                    pos += 2
                if (ver < 16 and cid < 0) or (ver >= 16 and cid == 114):
                    pos += 16
                pos += 16
                if enable_tt:
                    n_nodes, str_sz = struct.unpack_from("<II", raw, pos)
                    pos += 8 + n_nodes * (24 if ver < 19 else 32) + str_sz
                    if ver >= 21:
                        dep_cnt = struct.unpack_from("<i", raw, pos)[0]
                        pos += 4 + dep_cnt * 4
            self._pre_meta = raw[20 : pos + 4]
            obj_count = struct.unpack_from("<i", raw, pos)[0]
            pos += 4
            self.objects: list[_PureObj] = []
            for _ in range(obj_count):
                rel = pos - 20
                if rel % 4:
                    pos += 4 - (rel % 4)
                pid, bstart, bsize = struct.unpack_from("<qII", raw, pos)
                if ver < 16:
                    cid = struct.unpack_from("<H", raw, pos + 20)[0]
                    tail = raw[pos + 16 : pos + 25]
                    pos += 25
                else:
                    tid = struct.unpack_from("<i", raw, pos + 16)[0]
                    cid = type_class_ids[tid]
                    tail = raw[pos + 16 : pos + 20]
                    pos += 20
                oraw = raw[data_off + bstart : data_off + bstart + bsize]
                self.objects.append(_PureObj(pid, cid, tail, oraw, ver))
            self._post_meta = raw[pos : 20 + meta_sz]
            self.file = self

        def save(self) -> bytes:
            sorted_objs = sorted(self.objects, key=lambda x: x.path_id)
            meta_out = bytearray(self._pre_meta)
            data_chunks: list[bytes] = []
            cur_data_off = 0
            for obj in sorted_objs:
                if len(meta_out) % 4:
                    meta_out.extend(b"\x00" * (4 - (len(meta_out) % 4)))
                oraw = obj._raw
                meta_out.extend(struct.pack("<qII", obj.path_id, cur_data_off, len(oraw)))
                meta_out.extend(obj._tail)
                data_chunks.append(oraw)
                cur_data_off += len(oraw)
                if cur_data_off % 8:
                    pad = 8 - (cur_data_off % 8)
                    data_chunks.append(b"\x00" * pad)
                    cur_data_off += pad
            meta_out.extend(self._post_meta)
            new_meta_sz = len(meta_out)
            new_data_off = 20 + new_meta_sz
            if new_data_off % 16:
                new_data_off += 16 - (new_data_off % 16)
            pad_hdr = b"\x00" * (new_data_off - (20 + new_meta_sz))
            new_file_sz = new_data_off + cur_data_off
            hdr = struct.pack(">IIII", new_meta_sz, new_file_sz, self._ver, new_data_off) + self._endian_bytes
            return hdr + bytes(meta_out) + pad_hdr + b"".join(data_chunks)

    sa_path = data_dir / "sharedassets0.assets"
    dll_path = data_dir / "Managed" / "Assembly-CSharp.dll"
    if not sa_path.exists():
        raise FileNotFoundError(f"sharedassets0.assets not found at {sa_path}")

    if backup_dir is None:
        backup_dir = data_dir.parent / "backups_ui_original"
    backup_dir.mkdir(parents=True, exist_ok=True)

    sa_backup = backup_dir / "sharedassets0.assets"
    dll_backup = backup_dir / "Assembly-CSharp.dll"
    if not sa_backup.exists():
        shutil.copy2(sa_path, sa_backup)
    for ext in (".assets.resS", ".resource"):
        res_src = data_dir / f"sharedassets0{ext}"
        res_dst = backup_dir / f"sharedassets0{ext}"
        if res_src.exists() and not res_dst.exists():
            shutil.copy2(res_src, res_dst)
    if dll_path.exists() and not dll_backup.exists():
        shutil.copy2(dll_path, dll_backup)

    env = _PureEnv(sa_backup)

    # 1. Extract 90x19 blank pill rows from ConfigHigurashi
    tpl_90_norm_row = np.zeros((90, 4), dtype=np.uint8)
    tpl_90_hov_row = np.zeros((90, 4), dtype=np.uint8)
    for obj in env.objects:
        if obj.type.name == "Texture2D":
            d = obj.read(check_read=False)
            if d.m_Name == "ConfigHigurashi":
                arr23 = np.array(d.image.convert("RGBA"))
                tpl_90_norm_row = arr23[229 + 9, 91 : 91 + 90].copy()
                tpl_90_hov_row = arr23[229 + 9, 0 : 90].copy()
                break

    tips_exit_coords = find_tips_exit_sprites(env)
    kai_title_sprites = find_kai_title_sprites(env)

    # For _jp dialogs that originally have Japanese text on the top border, use the clean English dialog base
    clean_dialog_bases: dict[str, Image.Image] = {}
    for obj in env.objects:
        if obj.type.name == "Texture2D":
            d = obj.read(check_read=False)
            if d.m_Name in ("dialog_areyousure", "dialog_delete", "dialog_exit", "dialog_edit", "dialog_load", "dialog_save", "configbg", "SGMenu990000"):
                if d.m_Name == "configbg":
                    arr_c = np.array(d.image.convert("RGBA"))
                    if arr_c[30, 300, 0] > arr_c[30, 300, 2]:
                        clean_dialog_bases["configbg_jp"] = d.image.convert("RGBA")
                else:
                    clean_dialog_bases[f"{d.m_Name}_jp"] = d.image.convert("RGBA")
            elif d.m_Name in ("chapterdesc0", "chapterdesc1", "chapterdesc2", "chapterdesc3", "chapterlock"):
                clean_dialog_bases[f"{d.m_Name}_j"] = d.image.convert("RGBA")

    tex_count = 0
    mb_count = 0

    # Find msgothic_0 SDF, msgothic_2 SDF, and LiberationSans SDF path_ids dynamically
    msgothic_0_pid: int | None = None
    msgothic_2_pid: int | None = None
    lib_sdf_pid: int | None = None
    for obj in env.objects:
        if obj.type.name == "MonoBehaviour":
            raw = bytes(obj.get_raw_data())
            if b"msgothic_0 SDF" in raw:
                msgothic_0_pid = obj.path_id
            elif b"msgothic_2 SDF" in raw:
                msgothic_2_pid = obj.path_id
            elif b"LiberationSans SDF" in raw and b"Fallback" not in raw:
                lib_sdf_pid = obj.path_id

    for obj in env.objects:
        if obj.type.name == "Texture2D":
            d = obj.read(check_read=False)
            try:
                base_img = clean_dialog_bases.get(d.m_Name) or d.image.convert("RGBA")
            except Exception:
                continue
            loc_img = localize_texture_by_name(d.m_Name, base_img, tpl_90_norm_row, tpl_90_hov_row, tips_exit_coords, kai_title_sprites)
            if loc_img is not None and loc_img.size == (d.m_Width, d.m_Height):
                d.image = loc_img
                d.save()
                tex_count += 1

        elif obj.type.name == "MonoBehaviour":
            raw = bytes(obj.get_raw_data())
            # Update Rei 1024x256 or Hou+ 512x512 TitleHigurashi UIAtlas sprite rects so widened Turkish buttons do not clip
            if b"07copyright" in raw and b"start_normal" in raw and b"quit_normal" in raw:
                idx_sn = raw.find(struct.pack("<I", 12) + b"start_normal")
                if idx_sn != -1 and struct.unpack_from("<12i", raw, idx_sn + 16)[3] == 24:
                    mut_raw = bytearray(raw)
                    for sname, nx, ny, nw, nh in [
                        (b"start_normal",      0,  7, 110, 24),
                        (b"omake_normal",      0, 32, 115, 24),
                        (b"config_normal",     0, 57, 130, 24),
                        (b"continue_normal",   0, 82, 145, 24),
                        (b"quit_normal",     200,  7, 100, 24),
                    ]:
                        idx_s = mut_raw.find(struct.pack("<I", len(sname)) + sname)
                        if idx_s != -1:
                            off_s = idx_s + 4 + ((len(sname) + 3) & ~3)
                            struct.pack_into("<12i", mut_raw, off_s, nx, ny, nw, nh, 0, 0, 0, 0, 962 - nw, 0, 0, 0)
                    obj.set_raw_data(bytes(mut_raw))
                    mb_count += 1
                    continue
                elif idx_sn != -1 and struct.unpack_from("<12i", raw, idx_sn + 16)[3] == 30:
                    mut_raw = bytearray(raw)
                    for sname, ny in [
                        (b"start_normal",     95),
                        (b"quit_normal",     140),
                        (b"omake_normal",    185),
                        (b"continue_normal", 230),
                        (b"config_normal",   275),
                    ]:
                        idx_s = mut_raw.find(struct.pack("<I", len(sname)) + sname)
                        if idx_s != -1:
                            off_s = idx_s + 4 + ((len(sname) + 3) & ~3)
                            struct.pack_into("<12i", mut_raw, off_s, 337, ny, 140, 30, 0, 0, 0, 0, 43, 267, 7, 8)
                    obj.set_raw_data(bytes(mut_raw))
                    mb_count += 1
                    continue

            if len(raw) >= 36 and struct.unpack_from("<I", raw, 28)[0] == 0:
                len1 = struct.unpack_from("<I", raw, 32)[0]
                if 0 < len1 <= 80 and 36 + len1 <= len(raw):
                    s1 = raw[36 : 36 + len1].decode("utf-8", errors="replace")
                    new_s1 = translate_ui_label(s1)
                    if new_s1 is not None:
                        off_tail = 36 + ((len1 + 3) & ~3)
                        tail = bytearray(raw[off_tail:])
                        # Check if tail starts with a TMP font pointer to msgothic_0_pid or a UILocalize second string
                        if len(tail) >= 12 and msgothic_2_pid is not None:
                            fid, pid = struct.unpack_from("<Iq", tail, 0)
                            if fid == 0 and pid in (msgothic_0_pid, lib_sdf_pid):
                                struct.pack_into("<Iq", tail, 0, 0, msgothic_2_pid)
                        if len(tail) >= 4:
                            len2 = struct.unpack_from("<I", tail, 0)[0]
                            if 0 < len2 <= 80 and 4 + len2 <= len(tail):
                                s2 = bytes(tail[4 : 4 + len2]).decode("utf-8", errors="replace")
                                new_s2 = translate_ui_label(s2)
                                if new_s2 is not None:
                                    off_tail2 = 4 + ((len2 + 3) & ~3)
                                    tail = bytearray(pack_unity_str(new_s2)) + tail[off_tail2:]
                        new_raw = raw[:32] + pack_unity_str(new_s1) + bytes(tail)
                        obj.set_raw_data(new_raw)
                        mb_count += 1
                        continue

                # Also check ChapterJumpButton at offset 68
                if len(raw) >= 76 and len1 == 0:
                    len68 = struct.unpack_from("<I", raw, 68)[0]
                    if 0 < len68 <= 80 and 72 + len68 <= len(raw):
                        s68 = raw[72 : 72 + len68].decode("utf-8", errors="replace")
                        new_s68 = translate_ui_label(s68)
                        if new_s68 is not None:
                            off_tail68 = 72 + ((len68 + 3) & ~3)
                            new_raw = raw[:68] + pack_unity_str(new_s68) + raw[off_tail68:]
                            obj.set_raw_data(new_raw)
                            mb_count += 1
                            continue

                # Also check UIWidget+TMP/UILabel at offset 72 (used in Rei Ep09 and Hou+ Ep10)
                if len(raw) >= 84 and len1 == 0 and struct.unpack_from("<I", raw, 44)[0] == 1065353216:
                    len72 = struct.unpack_from("<I", raw, 72)[0]
                    if 0 < len72 <= 80 and 76 + len72 <= len(raw):
                        s72 = raw[76 : 76 + len72].decode("utf-8", errors="replace")
                        new_s72 = translate_ui_label(s72)
                        if new_s72 is not None:
                            off_tail72 = 76 + ((len72 + 3) & ~3)
                            tail72 = bytearray(raw[off_tail72:])
                            if len(tail72) >= 16 and msgothic_2_pid is not None:
                                fid, pid = struct.unpack_from("<Iq", tail72, 4)
                                if fid == 0 and pid in (msgothic_0_pid, lib_sdf_pid):
                                    struct.pack_into("<Iq", tail72, 4, 0, msgothic_2_pid)
                            new_raw = raw[:72] + pack_unity_str(new_s72) + bytes(tail72)
                            obj.set_raw_data(new_raw)
                            mb_count += 1

    sa_path.write_bytes(env.file.save())

    # 2. Patch Assembly-CSharp.dll #US strings
    dll_patched = 0
    if dll_backup.exists():
        raw_dll = bytearray(dll_backup.read_bytes())
        pairs = [
            ("Mod Menu\n(Hotkey: F10)", "TR Yama: @Remilya(F10)"),
            ("BGM Info",                "BGM Adı "),
            ("Copy BGM Name",           "Adını Kopyala"),
            ("Show File",               "Dosya Aç "),
            ("Open In Youtube",         "YouTube'da Aç  "),
            ("Close the Mod menu",      "Mod menüsünü kapat"),
            ("No new tips available",   "Yeni bir ipucu yoktur"),
            ("- Nothing playing",       "- Çalan parça yok"),
        ]
        for old_s, new_s in pairs:
            old_b = old_s.encode("utf-16le")
            new_b = new_s.encode("utf-16le")
            idx = raw_dll.find(old_b)
            if idx != -1:
                raw_dll[idx : idx + len(old_b)] = new_b
                if any(ord(ch) > 0x7F for ch in new_s):
                    raw_dll[idx + len(new_b)] = 0x01
                dll_patched += 1
        dll_path.write_bytes(raw_dll)

    # 3. Localize StreamingAssets/Data/musicroom.txt if present (Hou+ Ep10 Music Room headings)
    mr_path = data_dir / "StreamingAssets" / "Data" / "musicroom.txt"
    if mr_path.exists():
        mr_backup = backup_dir / "musicroom.txt"
        if not mr_backup.exists():
            shutil.copy2(mr_path, mr_backup)
        mr_text = mr_backup.read_text(encoding="utf-8")
        for old_h, new_h in [
            ('"Artist"', '"Sanatçı"'),
            ('"Lyrics & Vocals"', '"Söz ve Vokal"'),
            ('"Composition"', '"Beste"'),
            ('"Vocals"', '"Vokal"'),
            ('"Guitar"', '"Gitar"'),
        ]:
            mr_text = mr_text.replace(old_h, new_h)
        mr_path.write_text(mr_text, encoding="utf-8", newline="\n")

    return {
        "textures": tex_count,
        "monobehaviours": mb_count,
        "dll_strings": dll_patched,
    }
