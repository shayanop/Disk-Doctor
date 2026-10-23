"""Send paths to the Windows Recycle Bin via SHFileOperationW.

Pure stdlib (ctypes) — no third-party deps. Always uses Recycle Bin (FOF_ALLOWUNDO),
never permanent delete. Caller is still responsible for the safety check upstream.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes


FO_DELETE = 0x0003
FOF_ALLOWUNDO = 0x0040
FOF_NOCONFIRMATION = 0x0010
FOF_NOERRORUI = 0x0400
FOF_SILENT = 0x0004
FOF_WANTNUKEWARNING = 0x4000  # warn if can't go to recycle bin (don't silently nuke)


class SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("wFunc", wintypes.UINT),
        ("pFrom", wintypes.LPCWSTR),
        ("pTo", wintypes.LPCWSTR),
        ("fFlags", ctypes.c_uint16),
        ("fAnyOperationsAborted", wintypes.BOOL),
        ("hNameMappings", ctypes.c_void_p),
        ("lpszProgressTitle", wintypes.LPCWSTR),
    ]


_shell32 = ctypes.windll.shell32
_shell32.SHFileOperationW.argtypes = [ctypes.POINTER(SHFILEOPSTRUCTW)]
_shell32.SHFileOperationW.restype = ctypes.c_int


def send_to_recycle_bin(path: str) -> tuple[bool, str]:
    """Move a single path to the Recycle Bin.

    Returns (success, message). On failure, file is untouched.
    The path string is passed double-null-terminated as required by the API.
    """
    if not path:
        return False, "empty path"
    op = SHFILEOPSTRUCTW()
    op.hwnd = None
    op.wFunc = FO_DELETE
    op.pFrom = path + "\0\0"
    op.pTo = None
    # Confirm-via-our-dialog already; the OS dialog would be a second prompt.
    # WANTNUKEWARNING ensures we get an error rather than silent permanent-delete
    # if the file is too big for Recycle Bin or on a non-supporting volume.
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_WANTNUKEWARNING | FOF_SILENT
    op.fAnyOperationsAborted = False
    op.hNameMappings = None
    op.lpszProgressTitle = None

    rc = _shell32.SHFileOperationW(ctypes.byref(op))
    if rc != 0:
        return False, f"SHFileOperation failed (code {rc})"
    if op.fAnyOperationsAborted:
        return False, "operation aborted"
    return True, "moved to Recycle Bin"
