# DiskDoctor

Safety-aware disk space analyzer for Windows. Scans a directory, classifies every
folder by deletion safety, and lets you send junk to the Recycle Bin without
risking your Windows install.

## Run

```
run.bat
```

(Or `py main.py`. Requires Python 3.10+. No pip dependencies — pure stdlib + ctypes.)

## How it differs from WizTree / WinDirStat / TreeSize

| Tool        | Speed | Safety guidance | Recycle Bin delete | Free |
|-------------|-------|-----------------|--------------------|------|
| WizTree     | ★★★★★ | None            | Manual             | Yes  |
| WinDirStat  | ★★    | None            | Yes (no warnings)  | Yes  |
| TreeSize Free | ★★★ | None            | Limited (paywall)  | Free tier |
| **DiskDoctor** | ★★★ | **4-tier classifier** | Always Recycle Bin, blocks system paths | Yes |

## Safety model

Every path gets one of four tags:

- 🟢 **SAFE** — caches, temps, browser caches, Windows.old, package manager caches. Deletion is fine.
- 🟡 **REVIEW** — your documents, downloads, media. You decide.
- 🟠 **RISKY** — installed apps, AppData. Uninstall via Settings → Apps; don't delete files.
- 🔴 **NEVER** — Windows, System32, WinSxS, drivers, registry hives, pagefile.sys, etc. **Hard-blocked from deletion** even if you click delete.

## Hard safety rails

1. Deletion always goes through Windows Recycle Bin (`SHFileOperationW` with `FOF_ALLOWUNDO`). Never permanent.
2. `safety.is_deletion_blocked()` is checked twice — once when enabling the button, once before the API call.
3. Drive roots and the user-profile root are refused regardless of category.
4. Symlinks/junctions are not followed (avoids loops and double-counts of `WindowsApps` etc.).
5. Permission errors are caught silently — the scan never crashes mid-tree.

## Files

- `main.py` — Tkinter GUI
- `scanner.py` — threaded directory walker
- `safety.py` — classification rules (the value layer)
- `recycle.py` — `SHFileOperationW` wrapper
- `run.bat` — launcher
