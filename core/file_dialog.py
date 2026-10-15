"""Native "choose a file" dialog, shown by the local editor process.

The editor runs on the same Windows desktop as the browser, so instead of asking
the user to type an absolute path we can open the real Explorer file dialog and
hand the chosen path back to the page.

Order of preference:

1. ``GetOpenFileNameW`` (comdlg32) — the genuine Explorer open dialog, no extra
   dependency.
2. ``tkinter.filedialog`` — used only when the Win32 call is unavailable.

Every entry point returns ``None`` when the user cancels, and never raises for a
"dialog unavailable" situation: callers fall back to manual input instead.
"""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path
from typing import Optional, Sequence

DEFAULT_TITLE = "选择 FC26 Squads 存档"
SAVE_PATTERNS = ("Squads*", "*.sav", "*")

#: ``\0``-separated "description\0pattern\0...\0\0" filter for GetOpenFileNameW.
SAVE_FILTER = (
    "FC26 存档 (Squads*)\0Squads*\0"
    "其他存档 (*.sav)\0*.sav\0"
    "所有文件 (*.*)\0*.*\0\0"
)

OFN_HIDEREADONLY = 0x00000004
OFN_NOCHANGEDIR = 0x00000008
OFN_PATHMUSTEXIST = 0x00000800
OFN_FILEMUSTEXIST = 0x00001000
OFN_EXPLORER = 0x00080000
OFN_DONTADDTORECENT = 0x02000000


class OPENFILENAMEW(ctypes.Structure):
    _fields_ = [
        ("lStructSize", ctypes.c_uint32),
        ("hwndOwner", ctypes.c_void_p),
        ("hInstance", ctypes.c_void_p),
        ("lpstrFilter", ctypes.c_wchar_p),
        ("lpstrCustomFilter", ctypes.c_wchar_p),
        ("nMaxCustFilter", ctypes.c_uint32),
        ("nFilterIndex", ctypes.c_uint32),
        ("lpstrFile", ctypes.c_wchar_p),
        ("nMaxFile", ctypes.c_uint32),
        ("lpstrFileTitle", ctypes.c_wchar_p),
        ("nMaxFileTitle", ctypes.c_uint32),
        ("lpstrInitialDir", ctypes.c_wchar_p),
        ("lpstrTitle", ctypes.c_wchar_p),
        ("Flags", ctypes.c_uint32),
        ("nFileOffset", ctypes.c_uint16),
        ("nFileExtension", ctypes.c_uint16),
        ("lpstrDefExt", ctypes.c_wchar_p),
        ("lCustData", ctypes.c_void_p),
        ("lpfnHook", ctypes.c_void_p),
        ("lpTemplateName", ctypes.c_wchar_p),
        ("pvReserved", ctypes.c_void_p),
        ("dwReserved", ctypes.c_uint32),
        ("FlagsEx", ctypes.c_uint32),
    ]


def win32_available() -> bool:
    return sys.platform.startswith("win")


def tk_available() -> bool:
    try:
        import tkinter  # noqa: F401
        from tkinter import filedialog  # noqa: F401
    except Exception:
        return False
    return True


def default_save_dir() -> Optional[Path]:
    """First existing FC26 settings directory, used as the dialog's start folder."""
    try:
        from .config import save_dirs
    except ImportError:  # pragma: no cover - package layout fallback
        from core.config import save_dirs
    for directory in save_dirs():
        if directory.is_dir():
            return directory
    return None


def pick_file(
    initial_dir: Optional[Path] = None,
    title: str = DEFAULT_TITLE,
    filter_spec: str = SAVE_FILTER,
) -> Optional[Path]:
    """Show the native open dialog; return the chosen path or ``None``."""
    for picker in (_pick_win32, _pick_tk):
        try:
            return picker(initial_dir=initial_dir, title=title, filter_spec=filter_spec)
        except Exception:
            continue
    return None


def _pick_win32(initial_dir=None, title=DEFAULT_TITLE, filter_spec=SAVE_FILTER):
    if not win32_available():
        raise RuntimeError("win32 不可用")
    ole32 = ctypes.windll.ole32
    # Shell dialogs like an apartment-threaded thread; ignore RPC_E_CHANGED_MODE.
    ole32.CoInitializeEx(None, 0x2)
    try:
        comdlg32 = ctypes.windll.comdlg32
        comdlg32.GetOpenFileNameW.argtypes = [ctypes.POINTER(OPENFILENAMEW)]
        comdlg32.GetOpenFileNameW.restype = ctypes.c_int
        buffer = ctypes.create_unicode_buffer(4096)
        options = OPENFILENAMEW()
        options.lStructSize = ctypes.sizeof(OPENFILENAMEW)
        options.hwndOwner = None
        options.lpstrFilter = filter_spec
        options.nFilterIndex = 1
        options.lpstrFile = ctypes.cast(buffer, ctypes.c_wchar_p)
        options.nMaxFile = len(buffer)
        options.lpstrTitle = title
        if initial_dir:
            options.lpstrInitialDir = str(initial_dir)
        options.Flags = (
            OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST | OFN_NOCHANGEDIR
            | OFN_EXPLORER | OFN_DONTADDTORECENT | OFN_HIDEREADONLY
        )
        if comdlg32.GetOpenFileNameW(ctypes.byref(options)):
            value = buffer.value
            return Path(value) if value else None
        return None
    finally:
        try:
            ole32.CoUninitialize()
        except Exception:
            pass


def _pick_tk(initial_dir=None, title=DEFAULT_TITLE, filter_spec=SAVE_FILTER):
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass
    try:
        chosen = filedialog.askopenfilename(
            parent=root,
            title=title,
            initialdir=str(initial_dir) if initial_dir else "",
            filetypes=[("FC26 存档", "Squads*"), ("所有文件", "*.*")],
        )
    finally:
        root.destroy()
    return Path(chosen) if chosen else None
