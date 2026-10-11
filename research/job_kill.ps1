foreach ($p in 38340, 9196) { try { Stop-Process -Id $p -Force -ErrorAction Stop; "killed $p" } catch { "fail $p $_" } }
