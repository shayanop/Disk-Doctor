"""Classification rules for disk content safety.

Four categories:
  NEVER  - touching this can break Windows. Hard-blocked from deletion.
  RISKY  - apps/program data. Uninstall via Apps & Features, not by deleting files.
  REVIEW - user data. User decides.
  SAFE   - caches, temps, logs. Safe to send to Recycle Bin.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

NEVER = "NEVER"
RISKY = "RISKY"
REVIEW = "REVIEW"
SAFE = "SAFE"

CATEGORY_ORDER = {SAFE: 0, REVIEW: 1, RISKY: 2, NEVER: 3}
CATEGORY_COLOR = {
    NEVER: "#c62828",   # red
    RISKY: "#ef6c00",   # orange
    REVIEW: "#f9a825",  # yellow
    SAFE: "#2e7d32",    # green
}


def _norm(p: str) -> str:
    return os.path.normcase(os.path.normpath(p))


_USER = os.environ.get("USERPROFILE", "C:\\Users\\Default")
_LOCAL = os.environ.get("LOCALAPPDATA", os.path.join(_USER, "AppData", "Local"))
_ROAMING = os.environ.get("APPDATA", os.path.join(_USER, "AppData", "Roaming"))
_PROGRAMDATA = os.environ.get("PROGRAMDATA", "C:\\ProgramData")
_WINDIR = os.environ.get("WINDIR", "C:\\Windows")
_PROGS = os.environ.get("PROGRAMFILES", "C:\\Program Files")
_PROGS86 = os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")


# Order matters: first matching prefix wins. Put specific subpaths before parents.
_RULES: list[tuple[str, str, str]] = [
    # ---- NEVER (system-critical) ----
    (_norm(_WINDIR + "\\System32"), NEVER, "Core Windows system files"),
    (_norm(_WINDIR + "\\SysWOW64"), NEVER, "32-bit system files"),
    (_norm(_WINDIR + "\\WinSxS"), NEVER, "Component store (looks huge but critical — use DISM to clean)"),
    (_norm(_WINDIR + "\\Boot"), NEVER, "Boot files"),
    (_norm(_WINDIR + "\\Fonts"), NEVER, "System fonts"),
    (_norm(_WINDIR + "\\inf"), NEVER, "Driver INF database"),
    (_norm(_WINDIR + "\\System32\\drivers"), NEVER, "Drivers"),
    (_norm(_WINDIR + "\\System32\\config"), NEVER, "Registry hives"),
    (_norm(_WINDIR + "\\Microsoft.NET"), NEVER, ".NET runtime"),
    (_norm("C:\\Boot"), NEVER, "Boot loader"),
    (_norm("C:\\Recovery"), NEVER, "Recovery partition data"),
    (_norm("C:\\System Volume Information"), NEVER, "System restore / shadow copies"),
    (_norm("C:\\$Recycle.Bin"), NEVER, "Recycle Bin (empty via Recycle Bin, not by deleting folder)"),
    (_norm("C:\\PerfLogs"), NEVER, "Performance logs"),
    (_norm(_PROGS + "\\WindowsApps"), NEVER, "UWP/Store apps — uninstall via Settings"),
    (_norm(_PROGS + "\\Common Files"), NEVER, "Shared component files"),
    (_norm(_PROGS86 + "\\Common Files"), NEVER, "Shared component files"),
    (_norm(_PROGRAMDATA + "\\Microsoft\\Windows"), NEVER, "Windows system data"),
    (_norm(_PROGRAMDATA + "\\Microsoft\\Crypto"), NEVER, "Cryptographic keys"),
    (_norm(_PROGRAMDATA + "\\Microsoft\\Windows Defender"), NEVER, "Defender — manage via Security app"),
    (_norm(_PROGRAMDATA + "\\Packages"), NEVER, "Store app data"),

    # ---- SAFE (caches / temp / logs) ----
    (_norm(_WINDIR + "\\Temp"), SAFE, "Windows temp files"),
    (_norm(_WINDIR + "\\Logs"), SAFE, "Windows logs (regenerate)"),
    (_norm(_WINDIR + "\\Prefetch"), SAFE, "Prefetch cache (regenerates)"),
    (_norm(_WINDIR + "\\SoftwareDistribution\\Download"), SAFE, "Windows Update download cache"),
    (_norm(_WINDIR + "\\Downloaded Program Files"), SAFE, "Old IE downloads"),
    (_norm("C:\\Windows.old"), SAFE, "Previous Windows install (after upgrade)"),
    (_norm("C:\\$WINDOWS.~BT"), SAFE, "Windows upgrade leftovers"),
    (_norm("C:\\$WINDOWS.~WS"), SAFE, "Windows upgrade leftovers"),
    (_norm(_LOCAL + "\\Temp"), SAFE, "User temp files"),
    (_norm(_LOCAL + "\\Microsoft\\Windows\\INetCache"), SAFE, "IE/Edge web cache"),
    (_norm(_LOCAL + "\\Microsoft\\Windows\\WebCache"), SAFE, "Web cache database"),
    (_norm(_LOCAL + "\\Microsoft\\Windows\\Explorer"), SAFE, "Thumbnail cache"),
    (_norm(_LOCAL + "\\Microsoft\\Edge\\User Data\\Default\\Cache"), SAFE, "Edge browser cache"),
    (_norm(_LOCAL + "\\Google\\Chrome\\User Data\\Default\\Cache"), SAFE, "Chrome browser cache"),
    (_norm(_LOCAL + "\\Mozilla\\Firefox\\Profiles"), SAFE, "Firefox profile cache (review first)"),
    (_norm(_LOCAL + "\\Packages\\Microsoft.WindowsStore_8wekyb3d8bbwe\\LocalCache"), SAFE, "Store cache"),
    (_norm(_LOCAL + "\\CrashDumps"), SAFE, "Application crash dumps"),
    (_norm(_LOCAL + "\\Microsoft\\Windows\\WER"), SAFE, "Windows Error Reporting"),
    (_norm(_LOCAL + "\\npm-cache"), SAFE, "npm cache"),
    (_norm(_LOCAL + "\\pip\\Cache"), SAFE, "pip cache"),
    (_norm(_LOCAL + "\\Yarn\\Cache"), SAFE, "Yarn cache"),
    (_norm(_USER + "\\.cargo\\registry\\cache"), SAFE, "Cargo cache"),
    (_norm(_USER + "\\.gradle\\caches"), SAFE, "Gradle cache"),
    (_norm(_USER + "\\.nuget\\packages"), SAFE, "NuGet cache (will re-download)"),
    (_norm(_USER + "\\AppData\\Local\\Discord\\Cache"), SAFE, "Discord cache"),
    (_norm(_USER + "\\AppData\\Roaming\\Discord\\Cache"), SAFE, "Discord cache"),
    (_norm(_LOCAL + "\\Microsoft\\Teams\\Cache"), SAFE, "Teams cache"),
    (_norm(_LOCAL + "\\slack\\Cache"), SAFE, "Slack cache"),
    (_norm(_LOCAL + "\\Spotify\\Storage"), SAFE, "Spotify offline cache"),
    (_norm(_LOCAL + "\\Spotify\\Data"), SAFE, "Spotify cache"),
    (_norm("C:\\Windows\\Memory.dmp"), SAFE, "Memory dump (post-crash)"),
    (_norm("C:\\Windows\\Minidump"), SAFE, "Crash mini-dumps"),

    # ---- RISKY (apps — uninstall properly, don't just delete) ----
    (_norm(_PROGS), RISKY, "Installed apps — uninstall via Settings → Apps"),
    (_norm(_PROGS86), RISKY, "Installed apps (32-bit) — uninstall via Settings → Apps"),
    (_norm(_PROGRAMDATA), RISKY, "App-shared data — managed by installers"),
    (_norm(_ROAMING), RISKY, "App settings & user data — review per-app"),
    (_norm(_LOCAL), RISKY, "App data & state — review per-app"),
    (_norm(_WINDIR), NEVER, "Windows directory"),  # catch-all for anything else under Windows
]


# Files that are off-limits even by name (anywhere they appear in C:\ root region)
_ROOT_NEVER_FILES = {
    _norm("C:\\pagefile.sys"),
    _norm("C:\\hiberfil.sys"),
    _norm("C:\\swapfile.sys"),
    _norm("C:\\bootmgr"),
    _norm("C:\\BOOTNXT"),
    _norm("C:\\DumpStack.log.tmp"),
}


@dataclass
class Verdict:
    category: str
    reason: str


def classify(path: str) -> Verdict:
    """Return safety verdict for a path. Conservative: unknown -> REVIEW, system path -> NEVER."""
    n = _norm(path)

    if n in _ROOT_NEVER_FILES:
        return Verdict(NEVER, "Critical Windows file")

    for prefix, cat, reason in _RULES:
        if n == prefix or n.startswith(prefix + os.sep):
            return Verdict(cat, reason)

    # User profile heuristics
    if n.startswith(_norm(_USER) + os.sep):
        rest = n[len(_norm(_USER)) + 1:]
        first = rest.split(os.sep, 1)[0] if rest else ""
        if first in {"downloads"}:
            return Verdict(REVIEW, "Downloads — usually safe to clean, you decide")
        if first in {"documents", "pictures", "videos", "music", "desktop", "onedrive"}:
            return Verdict(REVIEW, "User data — your files, your call")
        return Verdict(REVIEW, "User profile content")

    # Anything in C:\ root not matched above
    if n.startswith(_norm("C:\\")):
        return Verdict(REVIEW, "Unclassified — inspect before deleting")

    return Verdict(REVIEW, "Outside known regions")


def is_deletion_blocked(path: str) -> Optional[str]:
    """Hard safety rail. Returns a reason string if deletion is forbidden, else None."""
    v = classify(path)
    if v.category == NEVER:
        return f"BLOCKED: {v.reason}"
    n = _norm(path)
    # Refuse to delete drive roots or near-root directories
    if len(n) <= 4:  # "c:\" style
        return "BLOCKED: refuses to delete drive root"
    # Refuse to delete the user profile root itself
    if n == _norm(_USER):
        return "BLOCKED: refuses to delete user profile root"
    return None
