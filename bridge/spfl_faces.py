"""Player faces in SP Football Life 2026 (from the player's own install; nothing is shipped).

SPFL26 loads a player's real head by player id (Asset/model/character/face/real/<id>/) and his menu portrait from
common/render/symbol/player/<id>.dds; players without the face folder get a generic head. SPFL26 builds a club's squad
from the players registered at that club, so an FM24 player SPFL26 has at another club (or none) has to borrow one of
this club's records, which has its own real face. lend_faces() serves the right files for the borrowed id from the
LiveCPK match root: the FM24 player's own face and portrait when SPFL26 has him somewhere, else no portrait (a
transparent one) and, via matchday.lua, no real face for the borrowed id (generic head).
real_face_ids() lists the ids with a real face (table-of-contents scan, ~2 s, cached until a .cpk or root changes).
"""
from __future__ import annotations

import glob
import json
import os
import re
import struct

from fl26db import cpk_path, cpk_row_data, cpk_toc, wesys_pack

FACE = re.compile(r"character/face/real/(\d+)/", re.I)
PORTRAIT = re.compile(r"render/symbol/player/(\d+)\.dds$", re.I)
CACHE = os.path.join(os.environ.get("LOCALAPPDATA", "."), "MatchdayBridge", "real_faces.json")
PORTRAIT_DIR = "common/render/symbol/player"


def blank_portrait() -> bytes:
    """A fully transparent menu portrait in SPFL26's format (128x128 DXT5, one mip level, WESYS-packed like the
    game's own): all-zero DXT5 blocks have alpha 0, so the menu shows no face."""
    w = h = 128
    data = bytes((w // 4) * (h // 4) * 16)
    pf = struct.pack("<II4s5I", 32, 0x4, b"DXT5", 0, 0, 0, 0, 0)
    head = struct.pack("<4s7I", b"DDS ", 124, 0x81007, h, w, len(data), 0, 1) + bytes(44) + pf + \
        struct.pack("<5I", 0x1000, 0, 0, 0, 0)
    return wesys_pack(head + data, hdr=b"\x00\x01\x01")


def _sources(game_dir: str) -> tuple[list[str], list[str]]:
    cpks = sorted(p for d in ("Data", "download") for p in glob.glob(os.path.join(game_dir, d, "*.cpk")))
    sider = os.path.join(game_dir, "SiderAddons")
    roots = []
    try:
        ini = open(os.path.join(sider, "sider.ini"), encoding="utf-8", errors="replace").read()
        for m in re.finditer(r'^\s*cpk\.root\s*=\s*"([^"]+)"', ini, re.M):
            p = m.group(1)
            roots.append(os.path.normpath(p if os.path.isabs(p) else os.path.join(sider, p)))
    except OSError:
        pass
    return cpks, roots


def _signature(cpks: list[str], roots: list[str]) -> list:
    sig = []
    for p in cpks:
        st = os.stat(p)
        sig.append([p, st.st_size, int(st.st_mtime)])
    for r in roots:
        d = os.path.join(r, "Asset", "model", "character", "face", "real")
        sig.append([d, int(os.stat(d).st_mtime) if os.path.isdir(d) else 0])
    return sig


def real_face_ids(game_dir: str) -> set[int]:
    cpks, roots = _sources(game_dir)
    sig = _signature(cpks, roots)
    try:
        cached = json.load(open(CACHE, encoding="utf-8"))
        if cached.get("signature") == sig:
            return set(cached["ids"])
    except (OSError, ValueError, KeyError):
        pass
    ids: set[int] = set()
    for p in cpks:
        try:
            with open(p, "rb") as f:
                for row in cpk_toc(f)[1]:
                    m = FACE.search(cpk_path(row))
                    if m:
                        ids.add(int(m.group(1)))
        except (OSError, ValueError, KeyError):
            continue
    for r in roots:
        d = os.path.join(r, "Asset", "model", "character", "face", "real")
        if os.path.isdir(d):
            ids.update(int(n) for n in os.listdir(d) if n.isdigit())
    try:
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        with open(CACHE + ".tmp", "w", encoding="utf-8") as f:
            json.dump({"signature": sig, "ids": sorted(ids)}, f)
        os.replace(CACHE + ".tmp", CACHE)
    except OSError:
        pass
    return ids


def _cpks_by_priority(game_dir: str) -> list[str]:
    """The game's .cpk files, the one whose copy of a file wins first (as spfl_db.effective_table)."""
    from spfl_db import cpk_priority
    out = []
    try:
        out = [os.path.join(game_dir, "download", n) for n in cpk_priority(game_dir)]
    except OSError:
        pass
    data = os.path.join(game_dir, "Data")
    out += [os.path.join(data, n) for n in sorted(os.listdir(data), reverse=True) if n.endswith(".cpk")] \
        if os.path.isdir(data) else []
    seen, cpks = set(), []
    for p in out:
        if os.path.exists(p) and p.lower() not in seen:
            seen.add(p.lower())
            cpks.append(p)
    return cpks


def lend_faces(game_dir: str, root: str, faces: dict[int, int], portraits: dict[int, int],
               blank: set[int] | frozenset = frozenset()) -> int:
    """Serve other players' files for borrowed ids from the LiveCPK match root `root`.
    faces: {borrowed id: id whose real head and portrait it shows}; portraits: {borrowed id: id whose portrait only};
    blank: borrowed ids that show no portrait. Returns the number of files written."""
    want_face = {src: [dst for dst, s in faces.items() if s == src] for src in set(faces.values())}
    want_port = {}
    for dst, src in list(faces.items()) + list(portraits.items()):
        want_port.setdefault(src, []).append(dst)
    if not want_face and not want_port and not blank:
        return 0
    done: set[str] = set()
    written = 0

    def put(rel: str, data: bytes):
        nonlocal written
        p = os.path.join(root, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)
        written += 1

    if blank:
        empty = blank_portrait()
        for dst in blank:
            put(f"{PORTRAIT_DIR}/{dst}.dds", empty)
    if not want_face and not want_port:
        return written

    for cpk in _cpks_by_priority(game_dir):
        try:
            with open(cpk, "rb") as f:
                base, rows = cpk_toc(f)
                for r in rows:
                    path = cpk_path(r)
                    m = FACE.search(path)
                    if m and int(m.group(1)) in want_face:
                        src = m.group(1)
                        tail = path[m.end():]
                        if path.lower() in done:
                            continue
                        done.add(path.lower())
                        data = cpk_row_data(f, base, r)
                        for dst in want_face[int(src)]:
                            put(path[:m.start()] + f"character/face/real/{dst}/" + tail, data)
                        continue
                    m = PORTRAIT.search(path)
                    if m and int(m.group(1)) in want_port and path.lower() not in done:
                        done.add(path.lower())
                        data = cpk_row_data(f, base, r)
                        for dst in want_port[int(m.group(1))]:
                            put(path[:m.start()] + f"render/symbol/player/{dst}.dds", data)
        except (OSError, ValueError, KeyError):
            continue
    return written
