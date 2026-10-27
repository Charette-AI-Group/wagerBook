"""The version stamped into the Windows executable, from appConfig like everything else.

Without it, WagerBook.exe > Properties > Details shows no version at all, and
neither does anything that asks Windows rather than the app - a support
question, an inventory tool, a file you find on a stick a year later. The
About box knowing the version is not the same as the file knowing it.

Used by wagerBook.spec (PyInstaller's EXE takes the structure directly) and by
tools/buildExe.py, which reads the stamp back out of the built file to prove
it landed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def versionTuple(version: str) -> tuple[int, int, int, int]:
    """"0.8.1" -> (0, 8, 1, 0): Windows wants exactly four numbers.

    Anything after the numbers, as in "1.0.0rc1", is dropped rather than
    refused; the full text still goes into the string fields.
    """
    numbers = [int(part) for part in re.findall(r"\d+", version.split("-")[0])[:4]]
    if not numbers:
        raise ValueError(f"no version numbers in {version!r}")
    return tuple((numbers + [0, 0, 0, 0])[:4])  # type: ignore[return-value]


def stringFields(appConfig) -> dict[str, str]:
    """What Properties > Details lists, by its Windows field name."""
    return {
        "CompanyName": appConfig.copyrightHolder,
        "FileDescription": appConfig.appName,
        "FileVersion": appConfig.appVersion,
        "InternalName": appConfig.executableName,
        "LegalCopyright": f"Copyright (c) 2026 {appConfig.copyrightHolder}. MIT licensed.",
        "OriginalFilename": f"{appConfig.executableName}.exe",
        "ProductName": appConfig.appName,
        "ProductVersion": appConfig.appVersion,
    }


def versionInfo(appConfig):
    """PyInstaller's VSVersionInfo for this build. Imports PyInstaller, so build-time only."""
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo,
        StringFileInfo,
        StringStruct,
        StringTable,
        VarFileInfo,
        VarStruct,
        VSVersionInfo,
    )

    numbers = versionTuple(appConfig.appVersion)
    return VSVersionInfo(
        ffi=FixedFileInfo(
            filevers=numbers,
            prodvers=numbers,
            mask=0x3F,
            flags=0x0,
            OS=0x40004,  # Windows NT, 32-bit Windows API
            fileType=0x1,  # an application
            subtype=0x0,
            date=(0, 0),
        ),
        kids=[
            # 0409 = US English, 04B0 = Unicode: the table Explorer looks for first.
            StringFileInfo([
                StringTable("040904B0", [
                    StringStruct(name, value) for name, value in stringFields(appConfig).items()
                ])
            ]),
            VarFileInfo([VarStruct("Translation", [0x0409, 1200])]),
        ],
    )


def readFileVersion(executable: Path) -> str | None:
    """The fixed file version Windows reports for a built .exe, as "a.b.c.d"; None if absent."""
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    version = ctypes.windll.version
    path = str(executable)
    size = version.GetFileVersionInfoSizeW(path, None)
    if not size:
        return None
    buffer = ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(path, 0, size, buffer):
        return None
    pointer = ctypes.c_void_p()
    length = wintypes.UINT()
    if not version.VerQueryValueW(buffer, "\\", ctypes.byref(pointer), ctypes.byref(length)):
        return None

    class FixedInfo(ctypes.Structure):
        _fields_ = [(name, wintypes.DWORD) for name in (
            "signature", "strucVersion", "fileVersionMS", "fileVersionLS",
            "productVersionMS", "productVersionLS", "fileFlagsMask", "fileFlags",
            "fileOS", "fileType", "fileSubtype", "fileDateMS", "fileDateLS",
        )]

    info = ctypes.cast(pointer, ctypes.POINTER(FixedInfo)).contents
    return ".".join(str(part) for part in (
        info.fileVersionMS >> 16, info.fileVersionMS & 0xFFFF,
        info.fileVersionLS >> 16, info.fileVersionLS & 0xFFFF,
    ))
