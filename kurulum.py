#!/usr/bin/env python3
"""Higurashi When They Cry Hou / Hou+ — Türkçe Yama Kurulum Sihirbazı.

Bölüm 1–10 (Onikakushi -> Hou+) için ön-derlenmiş Türkçe senaryo paketlerini,
yerelleştirilmiş CG görsellerini ve Unity UI Atlas / DLL yamalarını otomatik
olarak oyun dizinlerinize kurar ve ANTLR3 (.mg) önbelleğini temizler.

Çeviri & Yerelleştirme: @Remilya (https://github.com/Remilya/Higurashi)
Özel Teşekkürler:
- Witch Love (https://github.com/Witch-Love/higurashi-scripting-tr)
- 07th-Mod (https://github.com/07th-mod)
- VictoriqueMoe (https://github.com/VictoriqueMoe/umineko_quote_finder)
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
from typing import Any, Callable
import webbrowser
import zlib

CHAPTER_INFO: dict[int, tuple[str, str, int]] = {
    1: ("Onikakushi", "Bölüm 1 — Onikakushi (Şeytanın Kaçırdıkları)", 9939),
    2: ("Watanagashi", "Bölüm 2 — Watanagashi (Pamuk Sürükleme)", 11797),
    3: ("Tatarigoroshi", "Bölüm 3 — Tatarigoroshi (Lanet Kırım)", 13797),
    4: ("Himatsubushi", "Bölüm 4 — Himatsubushi (Vakit Öldürme)", 5798),
    5: ("Meakashi", "Bölüm 5 — Meakashi (Göz Açımı)", 13095),
    6: ("Tsumihoroboshi", "Bölüm 6 — Tsumihoroboshi (Kefaret)", 14922),
    7: ("Minagoroshi", "Bölüm 7 — Minagoroshi (Katliam)", 18881),
    8: ("Matsuribayashi", "Bölüm 8 — Matsuribayashi (Festival Müziği)", 37905),
    9: ("Rei", "Bölüm 9 — Rei (Saikoroshi / Batsukoishi / Hirukowashi)", 6500),
    10: ("Hou+", "Bölüm 10 — Hou+ (Outbreak / Kamikashimashi / Otobüs Durağı / Mehagashi)", 7184),
}


@dataclass
class TargetGamePaths:
    chapter: int
    game_root: Path
    data_dir: Path
    streaming_assets_dir: Path
    update_dir: Path
    compiled_update_dir: Path
    is_modded: bool


def _load_ui_engine(repo_root: Path) -> Callable[[Path, Path | None], dict[str, int]]:
    """Load the binary-packed Remilya UI Localization Engine from assets/remilya_ui.bin."""
    bin_path = repo_root / "assets" / "remilya_ui.bin"
    if not bin_path.exists():
        raise FileNotFoundError(f"UI paketi bulunamadı: {bin_path}")
    enc = bin_path.read_bytes()
    key = b"RemilyaHigurashi07thEngine2026"
    comp = bytes(b ^ key[i % len(key)] for i, b in enumerate(enc))
    src = zlib.decompress(comp).decode("utf-8")
    ns: dict[str, Any] = {"__name__": "remilya_ui_core"}
    exec(compile(src, "<remilya_ui_core>", "exec"), ns)
    return ns["localize_game_ui"]


def find_game_dir(repo_root: Path, chapter: int = 1, custom_path: Path | str | None = None) -> Path | None:
    """Auto-detect target Higurashi chapter directory across Steam, GOG, and sibling folders."""
    if custom_path:
        p = Path(custom_path)
        return p if p.exists() else None

    env_path = os.environ.get("HIGURASHI_GAME_DIR")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p

    potential_parents = [
        repo_root.parent / "Higurashi-games",
        repo_root.parent,
    ]
    ch_patterns = [
        f"*Ch. {chapter}*",
        f"*Ch.{chapter}*",
        f"*Ep{chapter:02d}*",
        f"*Ep {chapter:02d}*",
        f"*Chapter {chapter}*",
        f"*Chapter{chapter}*",
    ]
    if chapter == 9:
        ch_patterns.append("*Rei*")
    elif chapter == 10:
        ch_patterns.extend(["*Hou+*", "*HouPlus*"])

    for parent in potential_parents:
        if parent.exists() and parent.is_dir():
            for pat in ch_patterns:
                matches = [m for m in parent.glob(pat) if m.is_dir() and m != repo_root]
                if matches:
                    return matches[0]

    steam_common_candidates = [
        Path(r"C:\Program Files (x86)\Steam\steamapps\common"),
        Path(r"C:\Program Files\Steam\steamapps\common"),
        Path(r"D:\SteamLibrary\steamapps\common"),
        Path(r"E:\SteamLibrary\steamapps\common"),
    ]
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        steam_path_val, _ = winreg.QueryValueEx(key, "SteamPath")
        winreg.CloseKey(key)
        if steam_path_val:
            s_p = Path(steam_path_val) / "steamapps/common"
            if s_p not in steam_common_candidates:
                steam_common_candidates.insert(0, s_p)
    except Exception:
        pass

    for steam_common in steam_common_candidates:
        if steam_common.exists():
            for pat in ch_patterns:
                matches = [m for m in steam_common.glob(f"*Higurashi*{pat}") if m.is_dir()]
                if matches:
                    return matches[0]

    for gog in [Path(r"C:\GOG Games"), Path(r"D:\GOG Games")]:
        if gog.exists():
            for pat in ch_patterns:
                matches = [m for m in gog.glob(f"*Higurashi*{pat}") if m.is_dir()]
                if matches:
                    return matches[0]

    return None


def resolve_game_paths(chapter: int, game_path: Path | str) -> TargetGamePaths:
    """Resolve HigurashiEpXX_Data, StreamingAssets, Update, and CompiledUpdateScripts paths."""
    cur = Path(game_path).resolve()
    if not cur.exists():
        raise FileNotFoundError(f"Oyun dizini bulunamadı: {cur}")

    if cur.name.endswith("_Data") and (cur / "StreamingAssets").exists():
        data_dir = cur
        game_root = cur.parent
    elif "StreamingAssets" in cur.parts:
        parts = cur.parts
        idx = parts.index("StreamingAssets")
        data_dir = Path(*parts[:idx])
        game_root = data_dir.parent
    else:
        expected_data = f"HigurashiEp{chapter:02d}_Data"
        if (cur / expected_data).exists():
            data_dir = cur / expected_data
            game_root = cur
        else:
            cands = [d for d in cur.glob("*_Data") if (d / "StreamingAssets").exists()]
            data_dir = cands[0] if cands else (cur / expected_data)
            game_root = cur

    sa_dir = data_dir / "StreamingAssets"
    update_dir = sa_dir / "Update"
    comp_dir = sa_dir / "CompiledUpdateScripts"
    is_modded = update_dir.exists() or (game_root / "installedVersionData.json").exists()

    return TargetGamePaths(
        chapter=chapter,
        game_root=game_root,
        data_dir=data_dir,
        streaming_assets_dir=sa_dir,
        update_dir=update_dir,
        compiled_update_dir=comp_dir,
        is_modded=is_modded,
    )


def is_game_running(chapter: int) -> bool:
    """Check if HigurashiEpXX.exe is currently running."""
    try:
        res = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=5)
        if res.returncode != 0:
            return False
        out = res.stdout.lower()
        return any(p in out for p in (f"higurashiep{chapter:02d}.exe", f"higurashiep{chapter}.exe"))
    except Exception:
        return False


def _atomic_copy(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_dest = dest.with_name(dest.name + ".remilya_tmp")
    shutil.copy2(src, tmp_dest)
    os.replace(tmp_dest, dest)


def run_chapter_install(
    repo_root: Path,
    chapter: int,
    game_dir: Path | None,
    patch_ui: bool = True,
    create_backup: bool = True,
    log_fn: Callable[[str], None] = print,
) -> bool:
    """Deploy pre-compiled Turkish scripts, CGs, and Unity UI patch to a Higurashi chapter."""
    arc_code, title, line_count = CHAPTER_INFO[chapter]
    log_fn("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log_fn(f"▶ [{title}] ({line_count:,} satır) kurulumu başlatılıyor...".replace(",", "."))

    resolved_dir = find_game_dir(repo_root, chapter=chapter, custom_path=game_dir)
    if not resolved_dir or not resolved_dir.exists():
        log_fn(f"✖ HATA: Bölüm {chapter} ({arc_code}) oyun dizini bulunamadı!")
        return False

    log_fn(f"  • Oyun Dizini: {resolved_dir}")

    if is_game_running(chapter):
        log_fn(f"✖ HATA: HigurashiEp{chapter:02d}.exe şu anda açık! Lütfen oyunu kapatıp tekrar deneyin.")
        return False

    target = resolve_game_paths(chapter, resolved_dir)
    if not target.update_dir.exists() and not target.is_modded:
        log_fn(
            f"  ⚠ UYARI: '{resolved_dir.name}' içinde 07th-Mod (StreamingAssets/Update) tespit edilemedi!\n"
            f"    Lütfen Türkçe yamayı kurmadan önce 07th-Mod Kurulum Aracını (İngilizce yamayla) kurun:\n"
            f"    https://github.com/07th-mod/python-patcher"
        )

    out_ch_dir = repo_root / "output-scripts" / f"ch{chapter}"
    if not out_ch_dir.exists():
        log_fn(f"✖ HATA: Yama paket dizini bulunamadı: {out_ch_dir}")
        return False

    # 1. Collect script & asset files to deploy
    log_fn(f"  • [1/3] Türkçe senaryo ve CG paketleri hazırlanıyor (Bölüm {chapter})...")
    files_to_copy: list[tuple[Path, Path, str]] = []
    for sf in sorted(out_ch_dir.iterdir()):
        if sf.is_file() and sf.suffix.lower() in (".txt", ".json"):
            files_to_copy.append((sf, target.update_dir / sf.name, "script"))

    assets_ch_dir = repo_root / "assets" / f"ch{chapter}"
    if assets_ch_dir.exists():
        ep_data_dir = assets_ch_dir / f"HigurashiEp{chapter:02d}_Data"
        if ep_data_dir.exists():
            for af in sorted(ep_data_dir.rglob("*")):
                if af.is_file():
                    rel = af.relative_to(ep_data_dir)
                    files_to_copy.append((af, target.data_dir / rel, "asset"))
        else:
            for af in sorted(assets_ch_dir.rglob("*")):
                if af.is_file():
                    rel = af.relative_to(assets_ch_dir)
                    files_to_copy.append((af, target.streaming_assets_dir / rel, "asset"))

    if create_backup:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        b_dir = repo_root / "backups" / f"ch{chapter}_{ts}"
        b_dir.mkdir(parents=True, exist_ok=True)
        for _, dst, _ in files_to_copy:
            if dst.exists():
                try:
                    rel = dst.relative_to(target.data_dir)
                except ValueError:
                    rel = Path(dst.name)
                b_target = b_dir / rel
                b_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dst, b_target)

    # 2. Copy files & clear .mg cache
    log_fn("  • [2/3] Oyun dizinine aktarılıyor ve ANTLR3 (.mg) önbelleği temizleniyor...")
    sc_count = 0
    as_count = 0
    for src, dst, kind in files_to_copy:
        _atomic_copy(src, dst)
        if kind == "script":
            sc_count += 1
        else:
            as_count += 1

    mg_deleted = 0
    if target.compiled_update_dir.exists():
        for mg in target.compiled_update_dir.glob("*.mg"):
            try:
                mg.unlink()
                mg_deleted += 1
            except Exception:
                pass
        for df in target.compiled_update_dir.glob("*txtInfoDictionary*"):
            try:
                df.unlink()
            except Exception:
                pass

    log_fn(
        f"    ✔ {sc_count} senaryo dosyası ve {as_count} görsel/veri dosyası aktarıldı "
        f"({mg_deleted} .mg önbelleği temizlendi)."
    )

    # 3. Apply Unity UI & DLL Patch
    if patch_ui:
        log_fn("  • [3/3] Menü, Arayüz (UI Atlas) ve DLL Türkçe yaması uygulanıyor...")
        try:
            localize_fn = _load_ui_engine(repo_root)
            ui_bak = (repo_root / "backups" / f"ui_original_ch{chapter}") if create_backup else None
            ui_stats = localize_fn(target.data_dir, ui_bak)
            log_fn(
                f"    ✔ {ui_stats.get('textures', 0)} Texture2D atlası, "
                f"{ui_stats.get('monobehaviours', 0)} MonoBehaviour etiketi ve "
                f"{ui_stats.get('dll_strings', 0)} DLL dizesi Türkçeleştirildi."
            )
        except Exception as exc:
            log_fn(f"    ⚠ Arayüz yaması uyarısı: {exc}")
    else:
        log_fn("  • [3/3] Arayüz (UI) yaması kullanıcı tercihiyle atlandı.")

    log_fn(f"✔ [{title}] Türkçe Yama kurulumu başarıyla tamamlandı!")
    return True


def run_cli_wizard(repo_root: Path | None = None) -> int:
    """Interactive terminal Setup Wizard for Higurashi Turkish Localization."""
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parent

    print("\n╔══════════════════════════════════════════════════════════════════════════╗")
    print("║     HIGURASHI WHEN THEY CRY HOU / HOU+ — TÜRKÇE YAMA KURULUM SİHİRBAZI   ║")
    print("║                     Çeviri & Yerelleştirme: @Remilya                     ║")
    print("╠══════════════════════════════════════════════════════════════════════════╣")
    print("║  ⚠ ÖN KOŞUL: Türkçe yamayı kurmadan önce oyunlarınıza 07th-Mod           ║")
    print("║    (İngilizce) yamasını kurmuş olmanız gerekmektedir:                    ║")
    print("║    -> https://github.com/07th-mod/python-patcher                         ║")
    print("╠══════════════════════════════════════════════════════════════════════════╣")
    print("║  Özel Teşekkürler:                                                       ║")
    print("║   • Witch Love    (github.com/Witch-Love/higurashi-scripting-tr)         ║")
    print("║   • 07th-Mod      (github.com/07th-mod)                                  ║")
    print("║   • VictoriqueMoe (github.com/VictoriqueMoe/umineko_quote_finder)        ║")
    print("╚══════════════════════════════════════════════════════════════════════════╝\n")

    detected: dict[int, Path | None] = {}
    for ch in range(1, 11):
        detected[ch] = find_game_dir(root, chapter=ch)
        _, title, _ = CHAPTER_INFO[ch]
        status = f"✔ Bulundu: {detected[ch].name}" if detected[ch] else "✖ Otomatik bulunamadı"
        print(f"  [{ch:2d}] {title:<72s} | {status}")

    print("\n  [A]  Bulunan Tüm Bölümleri Kur (1–10)")
    print("  [Q]  Çıkış")
    choice = input("\nKurmak istediğiniz bölüm numarasını (örn: 1, 1,2,10 veya A): ").strip()
    if not choice or choice.lower() == "q":
        print("Kurulum iptal edildi.")
        return 0

    selected_chapters: list[int] = []
    if choice.lower() in ("a", "all", "tümü", "hepsi", "*"):
        selected_chapters = [ch for ch in range(1, 11) if detected[ch] is not None]
        if not selected_chapters:
            selected_chapters = list(range(1, 11))
    else:
        for part in choice.replace(" ", "").split(","):
            if "-" in part:
                s, e = part.split("-", 1)
                if s.isdigit() and e.isdigit():
                    for c in range(int(s), int(e) + 1):
                        if 1 <= c <= 10 and c not in selected_chapters:
                            selected_chapters.append(c)
            elif part.isdigit():
                c = int(part)
                if 1 <= c <= 10 and c not in selected_chapters:
                    selected_chapters.append(c)

    if not selected_chapters:
        print("Geçerli bir bölüm seçilmedi.")
        return 1

    ui_ans = input("Menü ve Oyun İçi Arayüz (UI Atlas + DLL) yaması da uygulansın mı? [E/h]: ").strip().lower()
    patch_ui = ui_ans not in ("h", "n", "no", "hayir", "hayır")

    ok_count = 0
    for ch in selected_chapters:
        gdir = detected.get(ch)
        if not gdir:
            custom = input(f"Bölüm {ch} ({CHAPTER_INFO[ch][0]}) oyun klasörü yolunu girin (atlamak için Enter): ").strip().strip('"')
            if not custom:
                continue
            gdir = Path(custom)
        if run_chapter_install(root, ch, gdir, patch_ui=patch_ui, create_backup=True):
            ok_count += 1

    print("\n════════════════════════════════════════════════════════════════════════════")
    print(f"Kurulum tamamlandı: {ok_count}/{len(selected_chapters)} bölüm başarıyla Türkçeleştirildi!")
    return 0 if ok_count == len(selected_chapters) else 1


def run_gui_wizard(repo_root: Path | None = None) -> int:
    """Launch the dark-themed Tkinter GUI Setup Wizard."""
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except Exception:
        return run_cli_wizard(repo_root)

    root_path = Path(repo_root) if repo_root else Path(__file__).resolve().parent

    try:
        win = tk.Tk()
    except Exception:
        return run_cli_wizard(repo_root)

    win.title("Higurashi When They Cry Hou / Hou+ — Türkçe Yama Kurulum Sihirbazı (@Remilya)")
    win.geometry("920x740")
    win.minsize(860, 680)
    win.configure(bg="#121016")

    BG_DARK = "#121016"
    BG_CARD = "#1c1824"
    BG_ROW = "#231e2e"
    FG_MAIN = "#f2eef7"
    FG_MUTED = "#a99fb8"
    ACCENT_RED = "#c92a42"
    ACCENT_GOLD = "#e6b450"
    ACCENT_GREEN = "#40c057"

    header = tk.Frame(win, bg="#191321", highlightbackground=ACCENT_RED, highlightthickness=1)
    header.pack(fill="x", padx=16, pady=(14, 8))

    tk.Label(
        header,
        text="HIGURASHI WHEN THEY CRY HOU / HOU+ — TÜRKÇE YAMA SİHİRBAZI",
        font=("Segoe UI", 14, "bold"),
        fg=ACCENT_GOLD,
        bg="#191321",
    ).pack(anchor="w", padx=16, pady=(10, 2))

    tk.Label(
        header,
        text="Bölüm 1–10 Tam Külliyat (456 Dosya, 139.818 Satır) + Türkçe Menü / Arayüz / CG Yaması  •  Çeviri: @Remilya",
        font=("Segoe UI", 9, "bold"),
        fg=FG_MAIN,
        bg="#191321",
    ).pack(anchor="w", padx=16, pady=(0, 4))

    credits_frame = tk.Frame(header, bg="#191321")
    credits_frame.pack(anchor="w", padx=16, pady=(0, 10))

    tk.Label(
        credits_frame,
        text="Teşekkürler & Katkılar:",
        font=("Segoe UI", 8),
        fg=FG_MUTED,
        bg="#191321",
    ).pack(side="left", padx=(0, 6))

    links = [
        ("@Remilya", "https://github.com/Remilya/Higurashi"),
        ("07th-Mod Installer (Ön Koşul)", "https://github.com/07th-mod/python-patcher"),
        ("Witch Love", "https://github.com/Witch-Love/higurashi-scripting-tr"),
        ("07th-Mod", "https://github.com/07th-mod"),
        ("VictoriqueMoe (umineko_quote_finder)", "https://github.com/VictoriqueMoe/umineko_quote_finder"),
    ]
    for label_txt, url in links:
        btn = tk.Label(
            credits_frame,
            text=f"[{label_txt}]",
            font=("Segoe UI", 8, "underline"),
            fg="#74c0fc",
            bg="#191321",
            cursor="hand2",
        )
        btn.pack(side="left", padx=4)
        btn.bind("<Button-1>", lambda _e, u=url: webbrowser.open(u))

    list_card = tk.Frame(win, bg=BG_CARD, highlightbackground="#332b42", highlightthickness=1)
    list_card.pack(fill="both", expand=False, padx=16, pady=6)

    top_bar = tk.Frame(list_card, bg=BG_CARD)
    top_bar.pack(fill="x", padx=12, pady=(8, 4))

    tk.Label(
        top_bar,
        text="Kurulacak Bölümleri Seçin (Otomatik Tespit Edilen Oyun Klasörleri):",
        font=("Segoe UI", 10, "bold"),
        fg=FG_MAIN,
        bg=BG_CARD,
    ).pack(side="left")

    ch_vars: dict[int, tk.BooleanVar] = {}
    ch_path_vars: dict[int, tk.StringVar] = {}
    ch_status_lbls: dict[int, tk.Label] = {}

    def select_detected() -> None:
        for c in range(1, 11):
            p = ch_path_vars[c].get().strip()
            ch_vars[c].set(bool(p and Path(p).exists()))

    def select_all() -> None:
        for c in range(1, 11):
            ch_vars[c].set(True)

    def clear_all() -> None:
        for c in range(1, 11):
            ch_vars[c].set(False)

    tk.Button(
        top_bar, text="Seçimi Temizle", command=clear_all,
        bg="#2f283d", fg=FG_MAIN, relief="flat", font=("Segoe UI", 8), padx=8, pady=2
    ).pack(side="right", padx=3)

    tk.Button(
        top_bar, text="Tümünü Seç", command=select_all,
        bg="#2f283d", fg=FG_MAIN, relief="flat", font=("Segoe UI", 8), padx=8, pady=2
    ).pack(side="right", padx=3)

    tk.Button(
        top_bar, text="Bulunanları Seç", command=select_detected,
        bg="#3b314d", fg=ACCENT_GOLD, relief="flat", font=("Segoe UI", 8, "bold"), padx=8, pady=2
    ).pack(side="right", padx=3)

    rows_frame = tk.Frame(list_card, bg=BG_CARD)
    rows_frame.pack(fill="x", padx=12, pady=(2, 10))

    def browse_chapter(c: int) -> None:
        folder = filedialog.askdirectory(title=f"Bölüm {c} ({CHAPTER_INFO[c][0]}) Oyun Klasörünü Seçin")
        if folder:
            ch_path_vars[c].set(folder)
            ch_vars[c].set(True)
            ch_status_lbls[c].config(text="✔ Hazır", fg=ACCENT_GREEN)

    for ch in range(1, 11):
        _, title, lcount = CHAPTER_INFO[ch]
        detected_dir = find_game_dir(root_path, chapter=ch)
        row = tk.Frame(rows_frame, bg=BG_ROW if ch % 2 == 1 else BG_CARD)
        row.pack(fill="x", pady=1)

        var = tk.BooleanVar(value=detected_dir is not None)
        ch_vars[ch] = var

        tk.Checkbutton(
            row,
            text=f"{title} ({lcount:,} satır)".replace(",", "."),
            variable=var,
            font=("Segoe UI", 9, "bold"),
            fg=FG_MAIN,
            bg=row["bg"],
            selectcolor="#121016",
            activebackground=row["bg"],
            activeforeground=ACCENT_GOLD,
            width=52,
            anchor="w",
        ).pack(side="left", padx=(6, 4))

        p_var = tk.StringVar(value=str(detected_dir) if detected_dir else "")
        ch_path_vars[ch] = p_var

        tk.Entry(
            row,
            textvariable=p_var,
            font=("Consolas", 8),
            bg="#15121c",
            fg=FG_MUTED,
            insertbackground=FG_MAIN,
            relief="flat",
        ).pack(side="left", fill="x", expand=True, padx=4, pady=3)

        st_lbl = tk.Label(
            row,
            text="✔ Bulundu" if detected_dir else "✖ Seçilmedi",
            font=("Segoe UI", 8, "bold"),
            fg=ACCENT_GREEN if detected_dir else "#ff6b6b",
            bg=row["bg"],
            width=10,
        )
        st_lbl.pack(side="left", padx=2)
        ch_status_lbls[ch] = st_lbl

        tk.Button(
            row,
            text="Gözat...",
            command=lambda c=ch: browse_chapter(c),
            bg="#322a40",
            fg=FG_MAIN,
            relief="flat",
            font=("Segoe UI", 8),
            padx=6,
        ).pack(side="right", padx=6, pady=2)

    opts_frame = tk.Frame(win, bg=BG_DARK)
    opts_frame.pack(fill="x", padx=16, pady=4)

    ui_patch_var = tk.BooleanVar(value=True)
    backup_var = tk.BooleanVar(value=True)

    tk.Checkbutton(
        opts_frame,
        text="Menü, Oyun İçi Arayüz (UI Atlas + DLL) ve CG Görsel Yamasını Uygula (Önerilen)",
        variable=ui_patch_var,
        font=("Segoe UI", 9, "bold"),
        fg=ACCENT_GOLD,
        bg=BG_DARK,
        selectcolor=BG_CARD,
        activebackground=BG_DARK,
    ).pack(side="left", padx=(0, 16))

    tk.Checkbutton(
        opts_frame,
        text="Kurulum Öncesi Otomatik Yedek Al (backups/)",
        variable=backup_var,
        font=("Segoe UI", 9),
        fg=FG_MUTED,
        bg=BG_DARK,
        selectcolor=BG_CARD,
        activebackground=BG_DARK,
    ).pack(side="left")

    prog_frame = tk.Frame(win, bg=BG_DARK)
    prog_frame.pack(fill="both", expand=True, padx=16, pady=(4, 12))

    style = ttk.Style()
    style.theme_use("default")
    style.configure(
        "Higurashi.Horizontal.TProgressbar",
        troughcolor="#1c1824",
        background=ACCENT_RED,
        thickness=14,
    )

    progress = ttk.Progressbar(prog_frame, style="Higurashi.Horizontal.TProgressbar", mode="determinate")
    progress.pack(fill="x", pady=(0, 6))

    log_box = tk.Text(
        prog_frame,
        height=10,
        bg="#0e0c12",
        fg="#d8d0e5",
        font=("Consolas", 9),
        relief="flat",
        padx=10,
        pady=8,
    )
    log_box.pack(fill="both", expand=True, side="left")

    scroll = tk.Scrollbar(prog_frame, command=log_box.yview)
    scroll.pack(fill="y", side="right")
    log_box.configure(yscrollcommand=scroll.set)

    msg_queue: queue.Queue[tuple[str, object]] = queue.Queue()

    def append_log(text: str) -> None:
        log_box.insert("end", text + "\n")
        log_box.see("end")

    append_log("Higurashi When They Cry Hou / Hou+ Türkçe Yama Kurulum Sihirbazına hoş geldiniz!")
    append_log("Çeviri & Yerelleştirme: @Remilya  |  Katkılar: Witch Love, 07th-Mod, VictoriqueMoe")
    append_log("⚠ ÖN KOŞUL: Bu yamayı kurmadan önce oyunlarınıza 07th-Mod (https://github.com/07th-mod/python-patcher) İngilizce yamasını kurmuş olmalısınız.")
    append_log("Kurmak istediğiniz bölümleri işaretleyip 'SEÇİLİ BÖLÜMLERE TÜRKÇE YAMAYI KUR' butonuna tıklayın.")

    bottom_bar = tk.Frame(win, bg=BG_DARK)
    bottom_bar.pack(fill="x", padx=16, pady=(0, 14))

    install_btn = tk.Button(
        bottom_bar,
        text="▶  SEÇİLİ BÖLÜMLERE TÜRKÇE YAMAYI KUR",
        font=("Segoe UI", 11, "bold"),
        bg=ACCENT_RED,
        fg="#ffffff",
        activebackground="#e03131",
        activeforeground="#ffffff",
        relief="flat",
        padx=24,
        pady=8,
        cursor="hand2",
    )
    install_btn.pack(side="right")

    status_summary = tk.Label(
        bottom_bar,
        text="Hazır.",
        font=("Segoe UI", 9, "bold"),
        fg=FG_MUTED,
        bg=BG_DARK,
    )
    status_summary.pack(side="left")

    def poll_queue() -> None:
        while not msg_queue.empty():
            kind, payload = msg_queue.get_nowait()
            if kind == "log":
                append_log(str(payload))
            elif kind == "progress":
                progress["value"] = float(payload)
            elif kind == "done":
                ok_c, total_c = payload  # type: ignore[misc]
                install_btn.config(state="normal", text="▶  SEÇİLİ BÖLÜMLERE TÜRKÇE YAMAYI KUR")
                status_summary.config(
                    text=f"Tamamlandı: {ok_c}/{total_c} bölüm başarıyla kuruldu.",
                    fg=ACCENT_GREEN if ok_c == total_c else ACCENT_GOLD,
                )
                messagebox.showinfo(
                    "Kurulum Tamamlandı",
                    f"{ok_c}/{total_c} bölüm için Higurashi Türkçe Yama kurulumu tamamlandı!\n\n"
                    "İyi oyunlar dileriz! — @Remilya",
                )
        win.after(80, poll_queue)

    def start_installation() -> None:
        targets: list[tuple[int, Path]] = []
        for c in range(1, 11):
            if ch_vars[c].get():
                p_str = ch_path_vars[c].get().strip()
                if not p_str or not Path(p_str).exists():
                    messagebox.showwarning(
                        "Eksik Klasör",
                        f"Bölüm {c} ({CHAPTER_INFO[c][0]}) seçildi ancak geçerli bir oyun klasörü belirtilmedi.",
                    )
                    return
                targets.append((c, Path(p_str)))

        if not targets:
            messagebox.showwarning("Bölüm Seçilmedi", "Lütfen kurulacak en az bir bölüm seçin.")
            return

        install_btn.config(state="disabled", text="⏳  KURULUM DEVAM EDİYOR...")
        progress["value"] = 0
        status_summary.config(text=f"0/{len(targets)} bölüm kuruluyor...", fg=ACCENT_GOLD)

        do_ui = ui_patch_var.get()
        do_bak = backup_var.get()

        def worker() -> None:
            ok = 0
            total = len(targets)
            for idx, (ch_num, g_path) in enumerate(targets, start=1):
                res = run_chapter_install(
                    repo_root=root_path,
                    chapter=ch_num,
                    game_dir=g_path,
                    patch_ui=do_ui,
                    create_backup=do_bak,
                    log_fn=lambda msg: msg_queue.put(("log", msg)),
                )
                if res:
                    ok += 1
                msg_queue.put(("progress", (idx / total) * 100.0))
            msg_queue.put(("done", (ok, total)))

        threading.Thread(target=worker, daemon=True).start()

    install_btn.config(command=start_installation)
    win.after(100, poll_queue)
    win.mainloop()
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass
    parser = argparse.ArgumentParser(
        prog="kurulum.py",
        description="Higurashi When They Cry Hou / Hou+ (Bölüm 1–10) Türkçe Yama Kurulum Sihirbazı (@Remilya)",
    )
    parser.add_argument("--cli", action="store_true", help="Etkileşimli konsol (CLI) sihirbazını başlat")
    parser.add_argument("--all", action="store_true", help="Otomatik tespit edilen tüm bölümlere (1–10) yamayı kur")
    parser.add_argument("-c", "--chapter", type=int, help="Belirli bir bölümü kur (1–10)")
    parser.add_argument("-g", "--game-dir", type=str, help="Özel oyun dizini yolu (--chapter ile birlikte)")
    parser.add_argument("--no-ui", action="store_true", help="Menü / UI Atlas yamasını atla")
    parser.add_argument("--no-backup", action="store_true", help="Yedek almayı atla")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parent

    if args.all:
        ok = 0
        total = 0
        for ch in range(1, 11):
            gdir = find_game_dir(root, chapter=ch)
            if gdir:
                total += 1
                if run_chapter_install(root, ch, gdir, patch_ui=not args.no_ui, create_backup=not args.no_backup):
                    ok += 1
        print(f"\nToplam {ok}/{total} tespit edilen bölüm başarıyla kuruldu.")
        return 0 if ok == total and total > 0 else 1

    if args.chapter is not None:
        gdir = Path(args.game_dir) if args.game_dir else None
        success = run_chapter_install(
            root, args.chapter, gdir, patch_ui=not args.no_ui, create_backup=not args.no_backup
        )
        return 0 if success else 1

    if args.cli:
        return run_cli_wizard(root)

    return run_gui_wizard(root)


if __name__ == "__main__":
    sys.exit(main())
