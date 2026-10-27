"""The version is written in several places; these keep them saying the same thing.

appConfig.appVersion is the one the app reports, the builds are named after
and the release workflow checks the tag against. The others are copies, and a
copy left behind is how an About box, an installer and a website end up
naming three different versions of one release.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import wagerBook
from wagerBook import appConfig

projectRoot = Path(__file__).resolve().parents[1]


def testTheProjectFileAgrees() -> None:
    project = tomllib.loads((projectRoot / "pyproject.toml").read_text(encoding="utf-8"))

    assert project["project"]["version"] == appConfig.appVersion


def testThePackageAgrees() -> None:
    assert wagerBook.__version__ == appConfig.appVersion


def testEveryVersionTheWebsiteNamesIsTheCurrentOne() -> None:
    page = (projectRoot / "docs" / "index.html").read_text(encoding="utf-8")
    named = re.findall(
        r"(?:Version |Wager Book |wagerBookSetup-|WagerBook-)(\d+\.\d+\.\d+)", page
    )

    assert named, "the website should say which version it describes"
    assert set(named) == {appConfig.appVersion}
