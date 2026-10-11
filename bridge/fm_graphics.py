"""Club badges from Football Manager 2024's own graphics, as SP Football Life 2026 crests.

FM24 ships licensed club logos in data/game/graphics.fmf: graphics/pictures/logos/normal/clubs/<country>/<name>.png,
mapped to FM's club unique ids by logos/normal/clubs/config.xml ("eng/oldham" -> graphics/pictures/club/694/logo).
A user logo pack (Documents/Sports Interactive/Football Manager 2024/graphics/**/config.xml with the same kind of
maps) wins over the shipped ones, as in FM. A club FM has no logo for gets a plain badge drawn here (FM draws a
default one too).

.fmf layout (FM24 24.4, read 2026-10-10):
  header   02 01 'fmf.' 08 00 00 | u64 index offset (from byte 0)
  data     an entry's bytes start at its offset + 25: a flag byte, then [u32 size][zstd frame] runs when
           compressed (128 KiB of output per frame), else the raw bytes
  index    at the index offset: 9 more header bytes, then [u32 size][zstd frame] runs; a tree of
           dir  = u32 len, name, u32 n files, files..., u32 n dirs, dirs...
           file = u32 len, name, u32 len, ext, u64 offset, u64 stored size, u64 size, u64 time, u64 time
SPFL26 crests: common/render/symbol/flag/e_<team id 6 digits>_<f|r>[_l|_ll].png at 128/256/512 px.
"""
from __future__ import annotations

import glob
import hashlib
import io
import os
import re
import struct

ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"
CREST_SIZES = (("", 128), ("_l", 256), ("_ll", 512))
_cache: dict[str, "Fmf"] = {}


def _frames(buf: bytes) -> bytes:
    import zstandard
    d = zstandard.ZstdDecompressor()
    out, pos = bytearray(), 0
    while pos + 4 <= len(buf):
        cs = struct.unpack_from("<I", buf, pos)[0]
        if cs == 0 or pos + 4 + cs > len(buf):
            break
        out += d.decompressobj().decompress(buf[pos + 4:pos + 4 + cs])
        pos += 4 + cs
    return bytes(out)


class Fmf:
    def __init__(self, path: str):
        self.path = path
        with open(path, "rb") as f:
            h = f.read(32)
            if h[2:6] != b"fmf.":
                raise ValueError(f"not an FM archive: {path}")
            f.seek(struct.unpack_from("<Q", h, 9)[0])
            tail = f.read()
        k = tail.find(b"\x02\x01fmf.")
        if k < 0:
            raise ValueError("archive index not found")
        self.files: dict[str, tuple[int, int, int]] = {}
        self._walk(_frames(tail[k + 9:]))

    def _walk(self, b: bytes):
        p = 0

        def u32():
            nonlocal p
            v = struct.unpack_from("<I", b, p)[0]
            p += 4
            return v

        def s():
            nonlocal p
            n = u32()
            v = b[p:p + n].decode("utf-8", "replace")
            p += n
            return v

        def walk(prefix):
            nonlocal p
            name = s()
            path = f"{prefix}/{name}" if prefix else name
            for _ in range(u32()):
                fn, ext = s(), s()
                off, stored, size = struct.unpack_from("<QQQ", b, p)
                p += 40
                self.files[f"{path}/{fn}{ext}".lower()] = (off, stored, size)
            for _ in range(u32()):
                walk(path)

        walk("")

    def read(self, name: str) -> bytes:
        off, stored, size = self.files[name.lower()]
        with open(self.path, "rb") as f:
            f.seek(off + 25)
            flag = f.read(1)[0]
            raw = f.read(stored)
        if flag == 3 or raw[4:8] == ZSTD_MAGIC:
            return _frames(raw)[:size]
        return raw[:size]


def archive(fm_dir: str) -> Fmf:
    path = os.path.join(fm_dir, "data", "game", "graphics.fmf")
    if path not in _cache:
        _cache[path] = Fmf(path)
    return _cache[path]


def _maps(xml: str) -> dict[int, str]:
    """{club id: picture path without extension} from a logos config.xml."""
    out = {}
    for frm, to in re.findall(r'<record\s+from="([^"]+)"\s+to="graphics/pictures/club/(\d+)/logo"', xml):
        out[int(to)] = frm
    return out


def user_graphics_dir() -> str | None:
    docs = os.path.join(os.environ.get("USERPROFILE", ""), "Documents")
    try:
        import ctypes.wintypes
        buf = ctypes.create_unicode_buffer(260)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0:
            docs = buf.value
    except (OSError, AttributeError):
        pass
    d = os.path.join(docs, "Sports Interactive", "Football Manager 2024", "graphics")
    return d if os.path.isdir(d) else None


def club_logo(fm_dir: str | None, club_id: int | None) -> bytes | None:
    """PNG bytes of FM's logo for the club (a user logo pack first, then FM's own), or None."""
    if not club_id:
        return None
    gdir = user_graphics_dir()
    if gdir:                                        # logo packs: <dir>/config.xml maps "<file>" -> club/<id>/logo
        for cfg in glob.glob(os.path.join(gdir, "**", "config.xml"), recursive=True):
            try:
                m = _maps(open(cfg, encoding="utf-8", errors="replace").read())
            except OSError:
                continue
            if club_id in m and "small" not in cfg.lower():
                for ext in (".png", ".jpg"):
                    p = os.path.join(os.path.dirname(cfg), m[club_id] + ext)
                    if os.path.exists(p):
                        return open(p, "rb").read()
    if not fm_dir:
        return None
    try:
        a = archive(fm_dir)
        base = "graphics/pictures/logos/normal/clubs"
        m = _maps(a.read(f"{base}/config.xml").decode("utf-8", "replace"))
        if club_id in m and f"{base}/{m[club_id]}.png".lower() in a.files:
            return a.read(f"{base}/{m[club_id]}.png")
    except (OSError, ValueError, KeyError, struct.error):
        return None
    return None


PALETTE = ["#c8102e", "#0033a0", "#006a4e", "#ffb81c", "#6d2077", "#00843d", "#e35205", "#1d428a", "#7a1f3d",
           "#00a3e0"]


def drawn_badge(name: str, abbr: str = "", size: int = 512):
    """A plain shield in a colour picked from the name, with the club's initials (FM draws a default too)."""
    from PIL import Image, ImageDraw, ImageFont
    col = PALETTE[int(hashlib.md5(name.encode("utf-8")).hexdigest(), 16) % len(PALETTE)]
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 512
    shield = [(96, 64), (416, 64), (416, 260), (380, 360), (256, 456), (132, 360), (96, 260)]
    d.polygon([(x * s, y * s) for x, y in shield], fill="#ffffff")
    inner = [(116, 84), (396, 84), (396, 256), (364, 346), (256, 430), (148, 346), (116, 256)]
    d.polygon([(x * s, y * s) for x, y in inner], fill=col)
    text = (abbr or "".join(w[0] for w in re.findall(r"[A-Za-z]+", name) if w.upper() not in ("FC", "AFC", "CF"))[:3]
            or name[:3]).upper()
    font = None
    for f in ("segoeuib.ttf", "arialbd.ttf"):
        try:
            font = ImageFont.truetype(f, int(150 * s / max(1, len(text) - 1) ** 0.35))
            break
        except OSError:
            continue
    font = font or ImageFont.load_default()
    box = d.textbbox((0, 0), text, font=font)
    d.text((256 * s - (box[2] - box[0]) / 2 - box[0], 250 * s - (box[3] - box[1]) / 2 - box[1]), text,
           font=font, fill="#ffffff")
    return img


def crest_images(png: bytes | None, name: str, abbr: str = "") -> dict[str, bytes]:
    """{suffix: PNG bytes} for SPFL26's three crest sizes: the logo centred on a transparent square."""
    from PIL import Image
    if png:
        src = Image.open(io.BytesIO(png)).convert("RGBA")
        bbox = src.getbbox()
        if bbox:
            src = src.crop(bbox)
    else:
        src = drawn_badge(name, abbr)
    out = {}
    for suffix, n in CREST_SIZES:
        pad = round(n * 0.04)
        k = min((n - 2 * pad) / src.width, (n - 2 * pad) / src.height)
        im = src.resize((max(1, round(src.width * k)), max(1, round(src.height * k))), Image.LANCZOS)
        canvas = Image.new("RGBA", (n, n), (0, 0, 0, 0))
        canvas.paste(im, ((n - im.width) // 2, (n - im.height) // 2), im)
        b = io.BytesIO()
        canvas.save(b, "PNG")
        out[suffix] = b.getvalue()
    return out


def write_crests(root: str, team_id: int, images: dict[str, bytes]) -> list[str]:
    """Both the licensed (_r) and generic (_f) names: which one SPFL26 asks for depends on the slot."""
    d = os.path.join(root, "common", "render", "symbol", "flag")
    os.makedirs(d, exist_ok=True)
    written = []
    for kind in ("f", "r"):
        for suffix, data in images.items():
            p = os.path.join(d, f"e_{team_id:06d}_{kind}{suffix}.png")
            with open(p, "wb") as f:
                f.write(data)
            written.append(p)
    return written
