"""Finds the games and installs/uninstalls the game side of Matchday Bridge: the Sider module, its LiveCPK root and
the controller proxy. PES 2021 gets the official Sider 7.4.1 release (downloaded from GitHub on first use,
checksum-checked, never bundled) when it has no Sider of its own; SP Football Life 2026 ships with Sider."""
from __future__ import annotations

import hashlib
import io
import os
import re
import shutil
import sys
import winreg
import zipfile

SPFL_DEFAULT = r"C:\Program Files (x86)\SP Football Life 2026"
FM_APPID = "2252570"
PES_APPID = "1259970"         # eFootball PES 2021 SEASON UPDATE; the free LITE edition is the same app
SIDER_URL = "https://github.com/pes-modding/sider7/releases/download/v7.4.1/sider-7.4.1.zip"
SIDER_SHA256 = "67edb8fd3b188966cec990b0e50a222e0f88ba408ebb5db47526a33f24c6b390"
SIDER_MARK = "installed-by-matchday-bridge.txt"
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


def steam_libraries() -> list[str]:
    sd = steam_dir()
    if not sd:
        return []
    vdf = os.path.join(sd, "steamapps", "libraryfolders.vdf")
    libs = [sd]
    if os.path.exists(vdf):
        libs += [p.replace("\\\\", "\\") for p in re.findall(r'"path"\s+"([^"]+)"', open(vdf, encoding="utf-8").read())]
    return libs


def steam_app_dir(appid: str, default: str, exe: str) -> str | None:
    """Install folder of a Steam app (any library) that holds `exe`."""
    for lib in steam_libraries():
        acf = os.path.join(lib, "steamapps", f"appmanifest_{appid}.acf")
        if os.path.exists(acf):
            m = re.search(r'"installdir"\s+"([^"]+)"', open(acf, encoding="utf-8").read())
            d = os.path.join(lib, "steamapps", "common", m.group(1) if m else default)
            if os.path.exists(os.path.join(d, exe)):
                return d
    return None


def find_fm24() -> str | None:
    return steam_app_dir(FM_APPID, "Football Manager 2024", "fm.exe")


def find_pes2021() -> str | None:
    return steam_app_dir(PES_APPID, "eFootball PES 2021", "PES2021.exe")


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


def setup_sider(sider: str) -> list[str]:
    """Copy the Sider module, add it and our LiveCPK root to sider.ini (backup first). Idempotent."""
    done = []
    shutil.copy2(resource("spfl", "modules", "matchday.lua"), os.path.join(sider, "modules", "matchday.lua"))
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
        mods = [i for i, l in enumerate(lines) if l.strip().startswith(("lua.module", ";lua.module", "; lua.module"))]
        lines.insert(max(mods) + 1 if mods else len(lines), "\t" + MODULE_LINE)
    open(ini, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    done.append("added matchday root + module to sider.ini")
    return done


def install_spfl(game: str) -> list[str]:
    return setup_sider(os.path.join(game, "SiderAddons"))


def install_pes2021(game: str) -> list[str]:
    """PES 2021: Sider in <game>\\sider (downloaded when missing, set up to start the game through Steam and to
    close with it), then the module as for SPFL26."""
    sider = os.path.join(game, "sider")
    done = []
    if not os.path.exists(os.path.join(sider, "sider.exe")):
        download_sider(sider)
        done.append(f"downloaded Sider 7.4.1 into {sider}")
    return done + setup_sider(sider)


def download_sider(dest: str, data: bytes | None = None):
    """The official Sider 7.4.1 zip (pes-modding/sider7 on GitHub), checked against its SHA-256, unpacked to `dest`;
    its sider.ini keeps start.game (Steam) and exe.name, closes with the game and loads only netblock.lua (no online
    or live-update checks) and matchday.lua instead of the demo modules."""
    if data is None:
        import urllib.request
        with urllib.request.urlopen(SIDER_URL, timeout=120) as r:
            data = r.read()
    if hashlib.sha256(data).hexdigest() != SIDER_SHA256:
        raise RuntimeError("the Sider download does not match Sider 7.4.1's checksum")
    tmp = dest + ".download"
    shutil.rmtree(tmp, ignore_errors=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        exe = next(n for n in z.namelist() if n.endswith("sider/sider.exe"))
        prefix = exe[:-len("sider.exe")]
        for n in z.namelist():
            if n.startswith(prefix) and not n.endswith("/"):
                target = os.path.join(tmp, *n[len(prefix):].split("/"))
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with z.open(n) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out)
    ini = os.path.join(tmp, "sider.ini")
    lines = []
    for l in open(ini, encoding="utf-8", errors="replace").read().splitlines():
        s = l.strip()
        if s.startswith("close.on.exit"):
            l = "close.on.exit = 1"
        elif s.startswith("cpk.root"):
            l = ROOT_LINE
        elif s.startswith("lua.module"):
            l = l if "netblock.lua" in s else ";" + l
        lines.append(l)
        if s.startswith("lua.module") and "netblock.lua" in s:
            lines.append(MODULE_LINE)
    open(ini, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    open(os.path.join(tmp, SIDER_MARK), "w", encoding="utf-8").write(
        f"Sider 7.4.1 from {SIDER_URL}, unpacked by Matchday Bridge; its uninstaller removes this folder.\n")
    if not os.path.exists(dest):
        os.replace(tmp, dest)
        return
    # An incomplete Sider (sider.exe quarantined or deleted, an uninstall that hit a file in use): the release files go
    # over it. An existing sider.ini (the player's own settings) is kept (setup_sider adds our lines), and a folder
    # that was not ours does not become ours (no marker), so --uninstall never deletes someone else's Sider.
    for top, _dirs, files in os.walk(tmp):
        rel = os.path.relpath(top, tmp)
        os.makedirs(os.path.join(dest, rel), exist_ok=True)
        for f in files:
            target = os.path.normpath(os.path.join(dest, rel, f))
            if rel == "." and (f == SIDER_MARK or (f == "sider.ini" and os.path.exists(target))):
                continue
            shutil.copy2(os.path.join(top, f), target)
    shutil.rmtree(tmp, ignore_errors=True)


def uninstall_sider(sider: str) -> list[str]:
    """Our lines, module and LiveCPK root out of a game's Sider; a Sider Matchday Bridge downloaded goes entirely (its
    marker file last, so a file in use leaves a folder the next --uninstall still recognizes and removes)."""
    mark = os.path.join(sider, SIDER_MARK)
    if os.path.exists(mark):
        for n in os.listdir(sider):
            p = os.path.join(sider, n)
            if n == SIDER_MARK:
                continue
            if os.path.isdir(p) and not os.path.islink(p):
                shutil.rmtree(p, ignore_errors=True)
            else:
                try:
                    os.remove(p)
                except OSError:
                    pass
        left = [n for n in os.listdir(sider) if n != SIDER_MARK]
        if left:
            return [f"Sider ({sider}) was not removed completely ({', '.join(left[:3])} in use): close the game and "
                    "run --uninstall again"]
        os.remove(mark)
        try:
            os.rmdir(sider)
        except OSError:
            pass
        return [f"removed Sider ({sider}), which Matchday Bridge had downloaded"]
    ini = os.path.join(sider, "sider.ini")
    if not os.path.exists(ini):
        return []
    text = open(ini, encoding="utf-8", errors="replace").read()
    lines = [l for l in text.splitlines() if l.strip() not in (MODULE_LINE, ROOT_LINE)]
    open(ini, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    p = os.path.join(sider, "modules", "matchday.lua")
    if os.path.exists(p):
        os.remove(p)
    shutil.rmtree(os.path.join(sider, "livecpk", "matchday"), ignore_errors=True)
    return ["removed module, LiveCPK root and sider.ini lines"]


def uninstall_game(game: str, sider: str, name: str) -> list[str]:
    done = uninstall_sider(sider)
    try:
        import spfl_pad
        if spfl_pad.uninstall(game):
            done.append("removed the controller proxy (xinput1_3.dll)")
    except OSError as e:
        done.append(f"xinput1_3.dll not restored ({e}); close {name} and run --uninstall again")
    return done


def clear_match_root(sider: str):
    """The last match's database, crests and lent faces (the game shows its own data again). `sider`: the game's
    Sider folder; a game folder works too (its SiderAddons or sider folder is used)."""
    if not os.path.exists(os.path.join(sider, "sider.ini")):
        for sub in ("SiderAddons", "sider"):
            if os.path.exists(os.path.join(sider, sub, "sider.ini")):
                sider = os.path.join(sider, sub)
                break
    for d in ("common", "Asset"):
        shutil.rmtree(os.path.join(sider, "livecpk", "matchday", d), ignore_errors=True)
