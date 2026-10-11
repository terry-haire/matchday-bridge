/* Matchday Bridge - XInput proxy for SP Football Life 2026.

   Installed as <game>\xinput1_3.dll by MatchdayBridge.exe (the game's own Microsoft copy is renamed
   xinput1_3_orig.dll and does all the real work; without one the system xinput1_3/1_4 is used). Buttons written
   by bridge\spfl_pad.py into the shared memory "Local\MatchdayBridgePad" are merged into controller slot 0 - the
   slot of the player's own pad, i.e. SPFL26 "User 1" - so the bridge can walk the menus to the pre-match screen
   (and the dev testkit can play) while the game window is in the background. A real pad in slot 0 keeps
   working (its input is OR-ed with ours); input the bridge did not refresh expires after a second.

   Build: python testkit\pad.py build   (clang, no CRT) */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>

typedef struct { WORD wButtons; BYTE bLeftTrigger, bRightTrigger; SHORT sThumbLX, sThumbLY, sThumbRX, sThumbRY; } PAD;
typedef struct { DWORD dwPacketNumber; PAD Gamepad; } XSTATE;
typedef struct { WORD wLeftMotorSpeed, wRightMotorSpeed; } XVIB;
typedef struct { BYTE Type, SubType; WORD Flags; PAD Gamepad; XVIB Vibration; } XCAPS;

#define MAGIC 0x3150424DL /* "MBP1" */
typedef struct {                 /* keep in sync with bridge\spfl_pad.py */
    volatile LONG magic, seq, slot, connect, reads, pid, real_ok, reserved;
    volatile ULONGLONG expires;  /* GetTickCount64(): test input is dropped after this (crashed test = no stuck button) */
    PAD pad;
} SHM;

typedef DWORD(WINAPI *GetState_t)(DWORD, XSTATE *);
typedef DWORD(WINAPI *SetState_t)(DWORD, XVIB *);
typedef DWORD(WINAPI *GetCaps_t)(DWORD, DWORD, XCAPS *);
typedef void(WINAPI *Enable_t)(BOOL);
typedef DWORD(WINAPI *Guids_t)(DWORD, GUID *, GUID *);
typedef DWORD(WINAPI *Battery_t)(DWORD, BYTE, void *);
typedef DWORD(WINAPI *Keystroke_t)(DWORD, DWORD, void *);
typedef DWORD(WINAPI *Wait_t)(DWORD, DWORD, void *);
typedef DWORD(WINAPI *Slot_t)(DWORD);

static INIT_ONCE g_once = INIT_ONCE_STATIC_INIT;
static GetState_t pGetState, pGetStateEx;
static SetState_t pSetState;
static GetCaps_t pGetCaps;
static Enable_t pEnable;
static Guids_t pGuids;
static Battery_t pBattery;
static Keystroke_t pKeystroke;
static Wait_t pWaitGuide;
static Slot_t pCancelGuide, pPowerOff;
static SHM *volatile g_shm;
static volatile ULONGLONG g_next_open;

static HMODULE load_real(void) {
    WCHAR path[MAX_PATH];
    const WCHAR *f = L"xinput1_3_orig.dll";
    HMODULE self = NULL, h;
    DWORD n;
    int i;
    GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                       (LPCWSTR)&load_real, &self);
    n = GetModuleFileNameW(self, path, MAX_PATH);
    while (n > 0 && path[n - 1] != L'\\') n--;
    if (n > 0 && n + 20 < MAX_PATH) {
        for (i = 0; f[i]; i++) path[n + i] = f[i];
        path[n + i] = 0;
        if ((h = LoadLibraryW(path))) return h;
    }
    if ((h = LoadLibraryExW(L"xinput1_3.dll", NULL, LOAD_LIBRARY_SEARCH_SYSTEM32)) && h != self) return h;
    return LoadLibraryExW(L"xinput1_4.dll", NULL, LOAD_LIBRARY_SEARCH_SYSTEM32);
}

static BOOL CALLBACK init(PINIT_ONCE o, PVOID p, PVOID *c) {
    HMODULE h = load_real();
    (void)o; (void)p; (void)c;
    if (!h) return TRUE;
    pGetState = (GetState_t)GetProcAddress(h, "XInputGetState");
    pSetState = (SetState_t)GetProcAddress(h, "XInputSetState");
    pGetCaps = (GetCaps_t)GetProcAddress(h, "XInputGetCapabilities");
    pEnable = (Enable_t)GetProcAddress(h, "XInputEnable");
    pGuids = (Guids_t)GetProcAddress(h, "XInputGetDSoundAudioDeviceGuids");
    pBattery = (Battery_t)GetProcAddress(h, "XInputGetBatteryInformation");
    pKeystroke = (Keystroke_t)GetProcAddress(h, "XInputGetKeystroke");
    pGetStateEx = (GetState_t)GetProcAddress(h, MAKEINTRESOURCEA(100));
    pWaitGuide = (Wait_t)GetProcAddress(h, MAKEINTRESOURCEA(101));
    pCancelGuide = (Slot_t)GetProcAddress(h, MAKEINTRESOURCEA(102));
    pPowerOff = (Slot_t)GetProcAddress(h, MAKEINTRESOURCEA(103));
    return TRUE;
}

static void ready(void) { InitOnceExecuteOnce(&g_once, init, NULL, NULL); }

/* spfl_pad.py creates the mapping (with an everyone-access DACL); retry opening it at most twice a second. */
static SHM *shm(void) {
    SHM *p = g_shm;
    ULONGLONG now;
    HANDLE h;
    if (p) return p->magic == MAGIC ? p : NULL;
    now = GetTickCount64();
    if (now < g_next_open) return NULL;
    g_next_open = now + 500;
    h = OpenFileMappingW(FILE_MAP_READ | FILE_MAP_WRITE, FALSE, L"Local\\MatchdayBridgePad");
    if (!h) return NULL;
    p = (SHM *)MapViewOfFile(h, FILE_MAP_READ | FILE_MAP_WRITE, 0, 0, sizeof(SHM));
    if (!p) { CloseHandle(h); return NULL; }
    if (InterlockedCompareExchangePointer((PVOID volatile *)&g_shm, p, NULL) != NULL) {
        UnmapViewOfFile(p);      /* another thread won the race */
        CloseHandle(h);
        p = g_shm;
    } else {
        p->pid = (LONG)GetCurrentProcessId();   /* handle stays open: the mapping lives as long as the game */
    }
    return p->magic == MAGIC ? p : NULL;
}

static SHM *target(DWORD slot) {
    SHM *m = shm();
    return (m && (DWORD)m->slot == slot) ? m : NULL;
}

static DWORD merge(DWORD slot, XSTATE *s, DWORD r) {
    SHM *m = target(slot);
    BOOL live;
    PAD p;
    if (!m || !s) return r;
    m->real_ok = (r == ERROR_SUCCESS);
    InterlockedIncrement(&m->reads);
    if (r != ERROR_SUCCESS) {
        if (!m->connect) return r;
        s->dwPacketNumber = 0;
        s->Gamepad.wButtons = 0;
        s->Gamepad.bLeftTrigger = s->Gamepad.bRightTrigger = 0;
        s->Gamepad.sThumbLX = s->Gamepad.sThumbLY = s->Gamepad.sThumbRX = s->Gamepad.sThumbRY = 0;
        r = ERROR_SUCCESS;
    }
    live = GetTickCount64() <= m->expires;
    if (live) {
        p = m->pad;
        s->Gamepad.wButtons |= p.wButtons;
        if (p.bLeftTrigger > s->Gamepad.bLeftTrigger) s->Gamepad.bLeftTrigger = p.bLeftTrigger;
        if (p.bRightTrigger > s->Gamepad.bRightTrigger) s->Gamepad.bRightTrigger = p.bRightTrigger;
        if (p.sThumbLX || p.sThumbLY) { s->Gamepad.sThumbLX = p.sThumbLX; s->Gamepad.sThumbLY = p.sThumbLY; }
        if (p.sThumbRX || p.sThumbRY) { s->Gamepad.sThumbRX = p.sThumbRX; s->Gamepad.sThumbRY = p.sThumbRY; }
    }
    /* games only look at a pad again when its packet number changes */
    s->dwPacketNumber += 2u * (DWORD)m->seq + (live ? 0u : 1u);
    return r;
}

DWORD WINAPI XInputGetState(DWORD i, XSTATE *s) {
    ready();
    return merge(i, s, pGetState ? pGetState(i, s) : ERROR_DEVICE_NOT_CONNECTED);
}

DWORD WINAPI XInputGetStateEx(DWORD i, XSTATE *s) {
    ready();
    return merge(i, s, pGetStateEx ? pGetStateEx(i, s) : (pGetState ? pGetState(i, s) : ERROR_DEVICE_NOT_CONNECTED));
}

DWORD WINAPI XInputSetState(DWORD i, XVIB *v) {
    DWORD r;
    SHM *m;
    ready();
    r = pSetState ? pSetState(i, v) : ERROR_DEVICE_NOT_CONNECTED;
    if (r != ERROR_SUCCESS && (m = target(i)) && m->connect) r = ERROR_SUCCESS;
    return r;
}

DWORD WINAPI XInputGetCapabilities(DWORD i, DWORD flags, XCAPS *c) {
    DWORD r;
    SHM *m;
    ready();
    r = pGetCaps ? pGetCaps(i, flags, c) : ERROR_DEVICE_NOT_CONNECTED;
    if (r != ERROR_SUCCESS && c && (m = target(i)) && m->connect) {
        c->Type = 1;             /* XINPUT_DEVTYPE_GAMEPAD */
        c->SubType = 1;          /* XINPUT_DEVSUBTYPE_GAMEPAD */
        c->Flags = 0;
        c->Gamepad.wButtons = 0xF3FF;
        c->Gamepad.bLeftTrigger = c->Gamepad.bRightTrigger = 0xFF;
        c->Gamepad.sThumbLX = c->Gamepad.sThumbLY = c->Gamepad.sThumbRX = c->Gamepad.sThumbRY = (SHORT)0xFFC0;
        c->Vibration.wLeftMotorSpeed = c->Vibration.wRightMotorSpeed = 0xFF;
        r = ERROR_SUCCESS;
    }
    return r;
}

void WINAPI XInputEnable(BOOL on) { ready(); if (pEnable) pEnable(on); }

DWORD WINAPI XInputGetDSoundAudioDeviceGuids(DWORD i, GUID *r, GUID *c) {
    ready();
    return pGuids ? pGuids(i, r, c) : ERROR_DEVICE_NOT_CONNECTED;
}

DWORD WINAPI XInputGetBatteryInformation(DWORD i, BYTE t, void *b) {
    ready();
    return pBattery ? pBattery(i, t, b) : ERROR_DEVICE_NOT_CONNECTED;
}

DWORD WINAPI XInputGetKeystroke(DWORD i, DWORD res, void *k) {
    ready();
    return pKeystroke ? pKeystroke(i, res, k) : ERROR_EMPTY;
}

DWORD WINAPI XInputWaitForGuideButton(DWORD i, DWORD f, void *l) {
    ready();
    return pWaitGuide ? pWaitGuide(i, f, l) : ERROR_DEVICE_NOT_CONNECTED;
}

DWORD WINAPI XInputCancelGuideButtonWait(DWORD i) {
    ready();
    return pCancelGuide ? pCancelGuide(i) : ERROR_DEVICE_NOT_CONNECTED;
}

DWORD WINAPI XInputPowerOffController(DWORD i) {
    ready();
    return pPowerOff ? pPowerOff(i) : ERROR_DEVICE_NOT_CONNECTED;
}
