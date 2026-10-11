"""Finds both games and installs/uninstalls the SPFL26 side of Matchday Bridge."""
from __future__ import annotations

import os
import re
import shutil
import sys
import winreg

SPFL_DEFAULT = r"C:\Program Files (x86)\SP Football Life 2026"
FM_APPID = "2252570"
MODULE_LINE = 'lua.module = "matchday.lua"'
ROOT_LINE = 'cpk.root = ".\\livecpk\\matchday"'
STATS_LINE = "match-stats.enabled = 1"  # Sider's match library (live score) is off by default


def resource(*parts) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, *parts)


def steam_dir() -> str | None:
    for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                      (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")):
        try:
            with winreg.OpenKey(hive, key) as k:
                for name in ("SteamPath", "InstallPath"):
                    try:
                        return winreg.QueryValueEx(k, name)[0].replace("/", "\\")
                    except OSError:
                        pass
        except OSError:
            pass
    return None


def find_fm24() -> str | None:
    sd = steam_dir()
    if not sd:
        return None
    vdf = os.path.join(sd, "steamapps", "libraryfolders.vdf")
    libs = [sd]
    if os.path.exists(vdf):
        libs += [p.replace("\\\\", "\\") for p in re.findall(r'"path"\s+"([^"]+)"', open(vdf, encoding="utf-8").read())]
    for lib in libs:
        acf = os.path.join(lib, "steamapps", f"appmanifest_{FM_APPID}.acf")
        if os.path.exists(acf):
            m = re.search(r'"installdir"\s+"([^"]+)"', open(acf, encoding="utf-8").read())
            d = os.path.join(lib, "steamapps", "common", m.group(1) if m else "Football Manager 2024")
            if os.path.exists(os.path.join(d, "fm.exe")):
                return d
    return None


def find_spfl26() -> str | None:
    cands = [SPFL_DEFAULT]
    for root in (r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
                 r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, root) as k:
                i = 0
                while True:
                    try:
                        sub = winreg.EnumKey(k, i)
                    except OSError:
                        break
                    i += 1
                    try:
                        with winreg.OpenKey(k, sub) as s:
                            name = winreg.QueryValueEx(s, "DisplayName")[0]
                            if "Football Life 2026" in name:
                                un = winreg.QueryValueEx(s, "UninstallString")[0].strip('"')
                                cands.append(os.path.dirname(un))
                    except OSError:
                        pass
        except OSError:
            pass
    for d in cands:
        if os.path.exists(os.path.join(d, "FL_2026.exe")) and os.path.exists(os.path.join(d, "SiderAddons", "sider.ini")):
            return d
    return None


def install_spfl(game: str) -> list[str]:
    """Copy the Sider module, add it and our LiveCPK root to sider.ini (backup first). Idempotent."""
    done = []
    sider = os.path.join(game, "SiderAddons")
    for f in ("matchday.lua",):
        shutil.copy2(resource("spfl", "modules", f), os.path.join(sider, "modules", f))
    done.append("copied matchday.lua")
    os.makedirs(os.path.join(sider, "livecpk", "matchday"), exist_ok=True)
    os.makedirs(os.path.join(sider, "matchday"), exist_ok=True)
    ini = os.path.join(sider, "sider.ini")
    text = open(ini, encoding="utf-8", errors="replace").read()
    stats_on = re.search(r"^\s*match-stats\.enabled\s*=\s*1", text, re.M)
    if MODULE_LINE in text and ROOT_LINE in text and stats_on:
        return done + ["sider.ini already set up"]
    bak = ini + ".matchday-backup"
    if not os.path.exists(bak):
        shutil.copy2(ini, bak)
        done.append(f"backed up sider.ini -> {bak}")
    lines = text.splitlines()
    if not stats_on:
        lines = [l for l in lines if not re.match(r"\s*;?\s*match-stats\.enabled", l)]
        idx = next((i for i, l in enumerate(lines) if l.strip().startswith("[")), -1)
        lines.insert(idx + 1, "\t" + STATS_LINE)
    if ROOT_LINE not in text:
        idx = next((i for i, l in enumerate(lines) if l.strip().startswith("cpk.root")), None)
        lines.insert(idx if idx is not None else 1, "\t" + ROOT_LINE)
    if MODULE_LINE not in text:
        idx = max(i for i, l in enumerate(lines) if l.strip().startswith(("lua.module", ";lua.module", "; lua.module")))
        lines.insert(idx + 1, "\t" + MODULE_LINE)
    open(ini, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    done.append("added matchday root + module to sider.ini")
    return done


def uninstall_spfl(game: str) -> list[str]:
    sider = os.path.join(game, "SiderAddons")
    ini = os.path.join(sider, "sider.ini")
    text = open(ini, encoding="utf-8", errors="replace").read()
    lines = [l for l in text.splitlines() if l.strip() not in (MODULE_LINE, ROOT_LINE)]
    open(ini, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    for f in ("matchday.lua",):
        p = os.path.join(sider, "modules", f)
        if os.path.exists(p):
            os.remove(p)
    shutil.rmtree(os.path.join(sider, "livecpk", "matchday"), ignore_errors=True)
    done = ["removed module, LiveCPK root and sider.ini lines"]
    try:
        import spfl_pad
        if spfl_pad.uninstall(game):
            done.append("restored the game's own xinput1_3.dll")
    except OSError as e:
        done.append(f"xinput1_3.dll not restored ({e}); close SP Football Life 2026 and run --uninstall again")
    return done


def clear_match_root(game: str):
    """The last match's database, crests and lent faces (SPFL26 shows its own data again)."""
    for d in ("common", "Asset"):
        shutil.rmtree(os.path.join(game, "SiderAddons", "livecpk", "matchday", d), ignore_errors=True)
