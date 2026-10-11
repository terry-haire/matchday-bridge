"""External process memory access (ReadProcessMemory/WriteProcessMemory) plus MSVC RTTI lookup.

Reads data only; never patches code. Used for FM24 (fm.exe), which has no anti-cheat.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import struct

import numpy as np

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_CREATE_THREAD = 0x0002
MEM_COMMIT = 0x1000
MEM_PRIVATE = 0x20000
PAGE_READWRITE = 0x04
PAGE_GUARD = 0x100
PAGE_NOACCESS = 0x01
TH32CS_SNAPPROCESS = 0x2


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", wt.DWORD), ("PartitionId", wt.WORD), ("RegionSize", ctypes.c_size_t),
                ("State", wt.DWORD), ("Protect", wt.DWORD), ("Type", wt.DWORD)]


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", wt.DWORD), ("cntThreads", wt.DWORD),
                ("th32ParentProcessID", wt.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
                ("szExeFile", ctypes.c_wchar * 260)]


class MODULEINFO(ctypes.Structure):
    _fields_ = [("lpBaseOfDll", ctypes.c_void_p), ("SizeOfImage", wt.DWORD), ("EntryPoint", ctypes.c_void_p)]


k32.OpenProcess.restype = wt.HANDLE
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                  ctypes.POINTER(ctypes.c_size_t)]
k32.WriteProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                   ctypes.POINTER(ctypes.c_size_t)]
k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.POINTER(MEMORY_BASIC_INFORMATION), ctypes.c_size_t]
k32.VirtualQueryEx.restype = ctypes.c_size_t
k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
psapi.EnumProcessModulesEx.argtypes = [wt.HANDLE, ctypes.POINTER(wt.HMODULE), wt.DWORD, ctypes.POINTER(wt.DWORD),
                                       wt.DWORD]
psapi.GetModuleBaseNameW.argtypes = [wt.HANDLE, wt.HMODULE, ctypes.c_wchar_p, wt.DWORD]
psapi.GetModuleInformation.argtypes = [wt.HANDLE, wt.HMODULE, ctypes.POINTER(MODULEINFO), wt.DWORD]


def find_pid(exe: str) -> int | None:
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    e = PROCESSENTRY32W()
    e.dwSize = ctypes.sizeof(e)
    ok = k32.Process32FirstW(snap, ctypes.byref(e))
    pid = None
    while ok:
        if e.szExeFile.lower() == exe.lower():
            pid = e.th32ProcessID
            break
        ok = k32.Process32NextW(snap, ctypes.byref(e))
    k32.CloseHandle(snap)
    return pid


class Proc:
    def __init__(self, exe: str, write: bool = False, call: bool = False):
        self.exe = exe
        self.pid = find_pid(exe)
        if not self.pid:
            raise ProcessLookupError(f"{exe} is not running")
        access = PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
        if write or call:
            access |= PROCESS_VM_WRITE | PROCESS_VM_OPERATION
        if call:
            access |= PROCESS_CREATE_THREAD
        self.h = k32.OpenProcess(access, False, self.pid)
        if not self.h:
            raise PermissionError(f"OpenProcess failed ({ctypes.get_last_error()})")
        self.base, self.size = self._module(exe)

    def close(self):
        if self.h:
            k32.CloseHandle(self.h)
            self.h = None

    def _module(self, name: str):
        mods = (wt.HMODULE * 2048)()
        need = wt.DWORD()
        psapi.EnumProcessModulesEx(self.h, mods, ctypes.sizeof(mods), ctypes.byref(need), 3)
        buf = ctypes.create_unicode_buffer(260)
        for i in range(need.value // ctypes.sizeof(wt.HMODULE)):
            psapi.GetModuleBaseNameW(self.h, mods[i], buf, 260)
            if buf.value.lower() == name.lower():
                mi = MODULEINFO()
                psapi.GetModuleInformation(self.h, mods[i], ctypes.byref(mi), ctypes.sizeof(mi))
                return mi.lpBaseOfDll, mi.SizeOfImage
        raise LookupError(name)

    # ---- calling into the process (only for FM's own heap: malloc/free) ----
    def export(self, module: str, name: str) -> int:
        """Address of `name` exported by `module` inside the target process (read from its loaded image)."""
        base, _ = self._module(module)
        hdr = self.read(base, 0x400)
        pe = struct.unpack_from("<I", hdr, 0x3C)[0]
        exp_rva, _ = struct.unpack_from("<II", hdr, pe + 0x88)
        d = self.read(base + exp_rva, 40)
        n_names, f_rva, n_rva, o_rva = struct.unpack_from("<I", d, 24)[0], *struct.unpack_from("<III", d, 28)
        names = self.read(base + n_rva, 4 * n_names)
        ords = self.read(base + o_rva, 2 * n_names)
        want = name.encode()
        for i in range(n_names):
            s = self.read(base + struct.unpack_from("<I", names, 4 * i)[0], len(want) + 1)
            if s == want + b"\0":
                ordinal = struct.unpack_from("<H", ords, 2 * i)[0]
                return base + self.u32(base + f_rva + 4 * ordinal)
        raise LookupError(f"{module}!{name}")

    def call(self, func: int, *args: int, timeout_ms: int = 5000) -> int:
        """Run func(args...) (up to 4 integer args, Windows x64 ABI) on a new thread in the target process and
        return its 64-bit result. A small stub is written to a private executable page, freed afterwards."""
        regs = (b"\x48\xB9", b"\x48\xBA", b"\x49\xB8", b"\x49\xB9")   # mov rcx/rdx/r8/r9, imm64
        k32.VirtualAllocEx.restype = ctypes.c_void_p
        k32.VirtualAllocEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wt.DWORD, wt.DWORD]
        page = k32.VirtualAllocEx(self.h, None, 0x1000, MEM_COMMIT | 0x2000, 0x40)   # RESERVE, RWX
        if not page:
            raise OSError(f"VirtualAllocEx failed ({ctypes.get_last_error()})")
        try:
            result = page + 0x800
            code = b"\x48\x83\xEC\x28"                                      # sub rsp, 0x28
            for reg, val in zip(regs, args):
                code += reg + struct.pack("<Q", val & 0xFFFFFFFFFFFFFFFF)
            code += b"\x48\xB8" + struct.pack("<Q", func) + b"\xFF\xD0"     # mov rax, func; call rax
            code += b"\x48\xB9" + struct.pack("<Q", result) + b"\x48\x89\x01"   # mov rcx, &result; mov [rcx], rax
            code += b"\x48\x83\xC4\x28\x31\xC0\xC3"                         # add rsp, 0x28; xor eax, eax; ret
            self.write(page, code)
            self.write(result, b"\0" * 8)
            k32.CreateRemoteThread.restype = wt.HANDLE
            k32.CreateRemoteThread.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p,
                                               ctypes.c_void_p, wt.DWORD, ctypes.c_void_p]
            th = k32.CreateRemoteThread(self.h, None, 0, page, None, 0, None)
            if not th:
                raise OSError(f"CreateRemoteThread failed ({ctypes.get_last_error()})")
            try:
                if k32.WaitForSingleObject(th, timeout_ms) != 0:
                    raise TimeoutError("remote call did not return")
            finally:
                k32.CloseHandle(th)
            return self.u64(result)
        finally:
            k32.VirtualFreeEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wt.DWORD]
            k32.VirtualFreeEx(self.h, ctypes.c_void_p(page), 0, 0x8000)          # MEM_RELEASE

    def malloc(self, n: int) -> int:
        """Memory from the target's own CRT heap (UCRT malloc), so the target may free or reallocate it."""
        p = self.call(self.export("ucrtbase.dll", "malloc"), n)
        if not p:
            raise MemoryError(f"remote malloc({n}) failed")
        return p

    def free(self, ptr: int):
        self.call(self.export("ucrtbase.dll", "free"), ptr)

    # ---- raw access -------------------------------------------------------
    def read(self, addr: int, n: int) -> bytes:
        buf = ctypes.create_string_buffer(n)
        got = ctypes.c_size_t()
        if not k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got)):
            raise OSError(f"read {addr:#x}+{n} failed ({ctypes.get_last_error()})")
        return buf.raw[:got.value]

    def try_read(self, addr: int, n: int) -> bytes | None:
        try:
            return self.read(addr, n)
        except OSError:
            return None

    def write(self, addr: int, data: bytes):
        got = ctypes.c_size_t()
        if not k32.WriteProcessMemory(self.h, ctypes.c_void_p(addr), data, len(data), ctypes.byref(got)):
            raise OSError(f"write {addr:#x}+{len(data)} failed ({ctypes.get_last_error()})")

    def u8(self, a): return self.read(a, 1)[0]
    def u16(self, a): return struct.unpack("<H", self.read(a, 2))[0]
    def i16(self, a): return struct.unpack("<h", self.read(a, 2))[0]
    def u32(self, a): return struct.unpack("<I", self.read(a, 4))[0]
    def i32(self, a): return struct.unpack("<i", self.read(a, 4))[0]
    def u64(self, a): return struct.unpack("<Q", self.read(a, 8))[0]

    def regions(self, private_rw_only: bool = True):
        addr = 0
        mbi = MEMORY_BASIC_INFORMATION()
        while k32.VirtualQueryEx(self.h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            base = mbi.BaseAddress or 0
            size = mbi.RegionSize
            ok = mbi.State == MEM_COMMIT and not (mbi.Protect & (PAGE_GUARD | PAGE_NOACCESS))
            if private_rw_only:
                ok = ok and mbi.Type == MEM_PRIVATE and (mbi.Protect & 0xFF) == PAGE_READWRITE
            if ok:
                yield base, size
            addr = base + size
            if addr >= 0x7FFFFFFF0000:
                break

    # ---- module image -----------------------------------------------------
    _image: bytes | None = None

    def image(self) -> bytes:
        if self._image is None:
            parts = []
            step = 1 << 20
            for off in range(0, self.size, step):
                parts.append(self.try_read(self.base + off, min(step, self.size - off)) or b"\0" * min(step, self.size - off))
            self._image = b"".join(parts)
        return self._image

    # ---- RTTI ---------------------------------------------------------------
    def vtables(self, mangled: str) -> list[int]:
        """Vtable addresses for an MSVC class, e.g. '.?AVACTUAL_PLAYER@db@@'. Primary vtable (offset 0) first."""
        img = self.image()
        name = mangled.encode()
        out = []
        start = 0
        while True:
            i = img.find(name, start)
            if i < 0:
                break
            start = i + 1
            td_rva = i - 0x10
            arr = np.frombuffer(img[: len(img) // 4 * 4], dtype=np.uint32)
            for col_idx in np.nonzero(arr == td_rva)[0]:
                col = int(col_idx) * 4 - 0xC
                if col < 0:
                    continue
                sig, off, cdoff, td, cd, self_rva = struct.unpack_from("<IIIIII", img, col)
                if sig != 1 or self_rva != col:
                    continue
                col_va = self.base + col
                q = np.frombuffer(img[: len(img) // 8 * 8], dtype=np.uint64)
                for j in np.nonzero(q == col_va)[0]:
                    out.append((off, self.base + int(j) * 8 + 8))
                # unaligned fallback
            break
        out.sort()
        return [v for _, v in out]

    def find_qword(self, value: int, limit: int = 0) -> list[int]:
        """All 8-aligned heap addresses holding `value`."""
        hits = []
        v = np.uint64(value)
        for base, size in self.regions():
            for off in range(0, size, 64 << 20):
                n = min(64 << 20, size - off)
                b = self.try_read(base + off, n)
                if not b:
                    continue
                arr = np.frombuffer(b[: len(b) // 8 * 8], dtype=np.uint64)
                for j in np.nonzero(arr == v)[0]:
                    hits.append(base + off + int(j) * 8)
                    if limit and len(hits) >= limit:
                        return hits
        return hits

    def find_qwords(self, values: dict[int, str]) -> dict[str, list[int]]:
        """One heap pass collecting addresses whose qword matches any key of `values`."""
        keys = np.array(sorted(values), dtype=np.uint64)
        out: dict[str, list[int]] = {n: [] for n in values.values()}
        for base, size in self.regions():
            for off in range(0, size, 64 << 20):
                n = min(64 << 20, size - off)
                b = self.try_read(base + off, n)
                if not b:
                    continue
                arr = np.frombuffer(b[: len(b) // 8 * 8], dtype=np.uint64)
                m = np.isin(arr, keys)
                for j in np.nonzero(m)[0]:
                    out[values[int(arr[j])]].append(base + off + int(j) * 8)
        return out

    def find_bytes(self, pat: bytes, limit: int = 50) -> list[int]:
        hits = []
        for base, size in self.regions():
            for off in range(0, size, 64 << 20):
                n = min((64 << 20) + len(pat), size - off)
                b = self.try_read(base + off, n)
                if not b:
                    continue
                s = 0
                while True:
                    i = b.find(pat, s)
                    if i < 0:
                        break
                    hits.append(base + off + i)
                    if len(hits) >= limit:
                        return hits
                    s = i + 1
        return hits
