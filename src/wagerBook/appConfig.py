"""Application configuration — paths, defaults, and metadata."""

from __future__ import annotations

import os
import sys
from pathlib import Path

appName = "Wager Book"
appVersion = "0.8.1"
organizationName = "Charette-AI-Group"

# Help > About contents
editorName = "Francois Charette, PhD"
aiAgentName = "Claude - Opus 5"
copyrightHolder = "Charette AI Group, LLC"
# createNewApp rewrites the package name throughout, so this follows the repo
# it actually creates without anyone having to remember to edit it.
repoUrl = "https://github.com/Charette-AI-Group/wagerBook"

# Donate button, shared across the Charette AI Group applications so they look
# like they come from the same place.
donateUrl = "https://www.paypal.com/donate/?hosted_button_id=FEM4WLD7LHY36"
donateColour = "#f0b232"
donateTextColour = "#1f1e1b"
donatePressedColour = "#d9991f"

projectRoot = Path(__file__).resolve().parents[2]

# In a bundled build the package lives inside an archive rather than on disk,
# so bundled files come from the extraction directory instead. Getting this
# wrong is the classic "works from source, no icon in the .exe" bug.
isFrozen = bool(getattr(sys, "frozen", False))
# What everything bundled hangs off: the extraction directory when frozen,
# the checkout when not.
bundleRoot = Path(getattr(sys, "_MEIPASS", projectRoot)) if isFrozen else projectRoot
if isFrozen:
    resourcesDir = bundleRoot / "wagerBook" / "resources"
else:
    resourcesDir = Path(__file__).resolve().parent / "resources"
# The standalone build's names. No spaces in the executable or its folder,
# which scripts and the installer must otherwise quote; people see appName.
executableName = "WagerBook"
# Drawn by tools/makeIcons.py. The app runs without one if it is missing.
iconFile = resourcesDir / "wagerBook.ico"
# Windows groups taskbar buttons by this ID. Without one, a window started by
# pythonw.exe is filed under Python and shows Python's icon, not this app's.
appUserModelId = f"{organizationName}.WagerBook"

# Help > User Manual, the offline fallback. Rooted at the bundle when frozen
# and at the checkout otherwise, for the same reason resourcesDir is: a built
# app has no source tree above it, and projectRoot would climb out of it.
manualPath = bundleRoot / "docs" / "manual" / "README.md"
# The manual is pushed to GitHub, which renders the markdown and shows the
# screenshots a local .md opened in an editor does not, so the published copy
# is preferred, with the local one as the offline fallback. The app checks the
# address answers before sending anyone to it, off the interface thread.
manualUrl = f"{repoUrl}/blob/main/docs/manual/README.md"
# How long to wait for the published copy before falling back to the local one.
manualTimeoutSeconds = 3.0

appDataDir = Path(os.environ.get("APPDATA", str(Path.home()))) / appName
settingsFile = appDataDir / "settings.ini"
# The book itself: every wager, open or closed, in one JSON file.
wagersFile = appDataDir / "wagers.json"
# Offered in the Category box; anything else can be typed in.
wagerCategories = [
    "Politics", "Economics", "Sports", "Crypto", "Science", "Entertainment",
    "Weather", "World", "Other",
]
windowTitle = appName
# Wide enough for the Active tab's fifteen columns without scrolling at once.
defaultWindowWidth = 1280
defaultWindowHeight = 640
