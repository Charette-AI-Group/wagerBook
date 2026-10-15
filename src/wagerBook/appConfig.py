"""Application configuration — paths, defaults, and metadata."""

from __future__ import annotations

import os
from pathlib import Path

appName = "Wager Book"
appVersion = "0.1.0"
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
resourcesDir = Path(__file__).resolve().parent / "resources"

# Help > User Manual. The copy in the checkout is what a new app has, and it is
# enough: the menu item works from the first run rather than being a promise.
manualPath = projectRoot / "docs" / "manual" / "README.md"
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
