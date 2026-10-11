# Third-party notices

Matchday Bridge ships no game files. Everything it gives SP Football Life 2026 is rebuilt at play time
from your own SP Football Life 2026 install and your own Football Manager 2024 save.

## Matozanato/FootballLife-new-leagues — MIT License

`bridge/fl26db.py` (CPK reading, WESYS packing, FL26 pesdb record layouts) is adapted from
https://github.com/Matozanato/FootballLife-new-leagues (tools/cpkread.py, tools/pesdb.py,
tools/playeredit.py, docs/player-record.md).

```
MIT License

Copyright (c) 2026 Matozanato

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## References consulted (no code copied)

- Matozanato/FootballLife-new-leagues `tools/mkleague.py`, `tools/leaguebuilder.py`, `tools/mkkits.py` —
  Competition, CompetitionRegulation, CompetitionEntry and UniformParameter.bin layouts and the Team.bin
  "Other ..." group nibble (+0x4f), used to find each club in SPFL26's Select Team list and to pick spare
  clubs that only have plain kits.
- the4chancup/4cc-studio — PES 2021 database schema, used to cross-check table layouts.
- pes-modding/sider7 — Sider 7 scripting documentation (`doc/scripting.html`, `modules/mstats.lua`).

## Bundled in MatchdayBridge.exe

- CPython 3.11 and Tcl/Tk (tkinter) — Python Software Foundation License; Tcl/Tk license (BSD-style).
- NumPy — BSD 3-Clause License.
- windows-capture 2.0.1 (NiiightmareXD/windows-capture, native module only) — MIT License.
- PyWinRT (winrt-runtime and Windows.Media.Ocr / Graphics.Imaging / Storage.Streams / Globalization /
  Foundation projections) — MIT License.
- Pillow — MIT-CMU (HPND) License.
- python-zstandard — BSD 3-Clause License (reads FM24's .fmf graphics archive for club logos).
- PyInstaller bootloader — GPL 2.0 with the PyInstaller bootloader exception (allows distributing
  bundled applications under any license).
