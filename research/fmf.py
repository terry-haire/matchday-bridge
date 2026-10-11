"""Read Football Manager 2024 .fmf archives (research; the bridge copy lives in bridge/fm_graphics.py).

Layout (FM24 24.4, worked out 2026-10-10):
  header   02 01 'fmf.' 08 00 00 | u64 index offset | ...
  data     runs of [u32 compressed size][zstd frame], 128 KiB of output per frame
  index    at the index offset: 9 bytes, 02 01 'fmf.' 08 00 00, then the same [u32][zstd] runs
  tree     dir  = u32 len, name, u32 n files, files..., u32 n dirs, dirs...
           file = u32 len, name, u32 len, ext, u64 offset, u64 stored size, u64 size, u64 time, u64 time
"""
import io
import os
import struct
import sys

import zstandard

D = zstandard.ZstdDecompressor()


def chunks(buf: bytes, pos: int = 0, limit: int | None = None) -> bytes:
    out = bytearray()
    end = len(buf) if limit is None else min(len(buf), pos + limit)
    while pos + 4 <= end:
        cs = struct.unpack_from("<I", buf, pos)[0]
        if cs == 0 or pos + 4 + cs > len(buf):
            break
        out += D.decompressobj().decompress(buf[pos + 4:pos + 4 + cs])
        pos += 4 + cs
    return bytes(out)


class Fmf:
    def __init__(self, path: str):
        self.path = path
        with open(path, "rb") as f:
            h = f.read(32)
            assert h[2:6] == b"fmf.", h[:8]
            self.index_off = struct.unpack_from("<Q", h, 9)[0]
            f.seek(self.index_off)
            tail = f.read()
        k = tail.find(b"\x02\x01fmf.")
        self.index = chunks(tail, k + 9)
        self.files: dict[str, tuple[int, int, int]] = {}
        self._parse()

    def _parse(self):
        b, p = self.index, 0

        def s():
            nonlocal p
            n = struct.unpack_from("<I", b, p)[0]
            p += 4
            v = b[p:p + n].decode("utf-8", "replace")
            p += n
            return v

        def u32():
            nonlocal p
            v = struct.unpack_from("<I", b, p)[0]
            p += 4
            return v

        def walk(prefix):
            nonlocal p
            name = s()
            path = f"{prefix}/{name}" if prefix else name
            for _ in range(u32()):
                fn, ext = s(), s()
                off, stored, size = struct.unpack_from("<QQQ", b, p)
                p += 40
                self.files[f"{path}/{fn}{ext}"] = (off, stored, size)
            for _ in range(u32()):
                walk(path)

        walk("")

    def read(self, name: str) -> bytes:
        """Entry offsets count from byte 25 of the archive: a flag byte (3 = zstd frames follow), then the
        stored bytes ([u32 size][zstd frame] runs when compressed)."""
        off, stored, size = self.files[name]
        with open(self.path, "rb") as f:
            f.seek(off + 25)
            flag = f.read(1)[0]
            raw = f.read(stored)
        if flag == 3 or raw[4:8] == b"\x28\xb5\x2f\xfd":
            return chunks(raw)[:size]
        return raw[:size]


if __name__ == "__main__":
    root = sys.argv[1]
    want = [w.lower() for w in sys.argv[2:]]
    for dp, _, fs in os.walk(root):
        for fn in fs:
            if not fn.endswith(".fmf"):
                continue
            path = os.path.join(dp, fn)
            try:
                a = Fmf(path)
            except Exception as e:  # noqa: BLE001
                print("ERR", path, e)
                continue
            hits = [n for n in a.files if any(w in n.lower() for w in want)]
            print(f"{path[len(root):]}: {len(a.files)} files, {len(hits)} hits")
            for n in hits[:15]:
                print("   ", n, a.files[n])
