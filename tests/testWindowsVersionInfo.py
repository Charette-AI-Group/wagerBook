"""Tests for the version stamped into the Windows executable."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from windowsVersionInfo import readFileVersion, stringFields, versionTuple  # noqa: E402

from wagerBook import appConfig  # noqa: E402


def testVersionsBecomeTheFourNumbersWindowsWants() -> None:
    assert versionTuple("0.8.1") == (0, 8, 1, 0)
    assert versionTuple("1.2") == (1, 2, 0, 0)
    assert versionTuple("1.2.3.4.5") == (1, 2, 3, 4)
    assert versionTuple("1.0.0rc1") == (1, 0, 0, 1)
    with pytest.raises(ValueError):
        versionTuple("dev")


def testTheDetailsTabSaysWhatTheAppSays() -> None:
    fields = stringFields(appConfig)

    assert fields["FileVersion"] == appConfig.appVersion
    assert fields["ProductVersion"] == appConfig.appVersion
    assert fields["ProductName"] == appConfig.appName
    assert fields["OriginalFilename"] == f"{appConfig.executableName}.exe"
    assert appConfig.copyrightHolder in fields["LegalCopyright"]


def testTheStructureBuildsForThisVersion() -> None:
    """Needs PyInstaller, so only where the build extra is installed."""
    pytest.importorskip("PyInstaller")
    from windowsVersionInfo import versionInfo

    info = versionInfo(appConfig)

    numbers = versionTuple(appConfig.appVersion)
    assert info.ffi.fileVersionMS == (numbers[0] << 16) | numbers[1]
    assert info.ffi.fileVersionLS == (numbers[2] << 16) | numbers[3]
    assert f"ProductVersion', '{appConfig.appVersion}" in str(info)


@pytest.mark.skipif(sys.platform != "win32", reason="reads a Windows version resource")
def testReadingAFileWithAStampReturnsIt() -> None:
    """python.exe always carries one, so the reader is checked against a known file."""
    stamped = readFileVersion(Path(sys.executable))

    assert stamped is not None
    assert stamped.startswith(f"{sys.version_info.major}.{sys.version_info.minor}.")


def testAFileWithoutAStampReadsAsNone(tmp_path) -> None:
    plain = tmp_path / "plain.exe"
    plain.write_bytes(b"not a program")

    assert readFileVersion(plain) is None
