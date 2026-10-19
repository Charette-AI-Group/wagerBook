"""Tests for the check that decides whether a build is shippable.

This one gates a release, so it has to fail when something is genuinely
missing. A self-test that passes unconditionally is worse than none: it turns
a broken build into a signed-off one.
"""

from __future__ import annotations

from wagerBook import appConfig, selftest
from wagerBook.services import httpsService


def testEveryBundledThingIsChecked(qapp) -> None:
    names = [name for name, _, _ in selftest.resourceChecks()]

    assert names == ["applicationIcon", "manual", "certificates"]


def testACheckoutPassesItsOwnCheck(qapp) -> None:
    assert all(found for _, found, _ in selftest.resourceChecks())


def testAMissingIconIsCaught(qapp, monkeypatch, tmp_path) -> None:
    """The failure this exists for: packaging dropped the icon."""
    monkeypatch.setattr(appConfig, "iconFile", tmp_path / "gone.ico")

    failures = [name for name, found, _ in selftest.resourceChecks() if not found]

    assert failures == ["applicationIcon"]


def testAMissingManualIsCaught(qapp, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(appConfig, "manualPath", tmp_path / "gone.md")

    failures = [name for name, found, _ in selftest.resourceChecks() if not found]

    assert failures == ["manual"]


def testNoCertificatesIsCaught(qapp, monkeypatch) -> None:
    """Without them every price request fails as if the sites were down."""
    monkeypatch.setattr(httpsService, "trustedAuthorityCount", lambda: 0)

    failures = [name for name, found, _ in selftest.resourceChecks() if not found]

    assert failures == ["certificates"]


def testTheWindowIsBuiltWithBothTabsAndItsIcon(qapp) -> None:
    ok, detail = selftest.windowCheck()

    assert ok, detail
    assert detail == appConfig.windowTitle


def testTheWindowCheckNeverTouchesTheRealBook(qapp, monkeypatch, tmp_path) -> None:
    """It points the app at a scratch folder before building anything."""
    realBook = tmp_path / "real" / "wagers.json"
    realSettings = tmp_path / "real" / "settings.ini"
    monkeypatch.setattr(appConfig, "wagersFile", realBook)
    monkeypatch.setattr(appConfig, "settingsFile", realSettings)

    ok, _detail = selftest.windowCheck()

    assert ok
    assert not realBook.exists() and not realSettings.exists()
    assert appConfig.wagersFile != realBook


def testTheReportNamesTheVersionAndPasses(qapp) -> None:
    text, passed = selftest.report()

    assert passed
    assert f"app={appConfig.appName} {appConfig.appVersion}" in text
    assert "result=ok" in text
    assert "MISSING" not in text


def testAFailedCheckShowsUpInTheReportAndTheExitCode(qapp, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(appConfig, "iconFile", tmp_path / "gone.ico")

    text, passed = selftest.report()

    assert not passed
    assert "applicationIcon=MISSING" in text
    assert "result=FAILED" in text
    assert selftest.runSelfTest(str(tmp_path / "report.txt")) == 1


def testTheReportIsWrittenWhereItIsAsked(qapp, tmp_path) -> None:
    """A windowed build has no console, so the file is the whole output."""
    target = tmp_path / "selftest.txt"

    code = selftest.runSelfTest(str(target))

    assert code == 0
    assert "result=ok" in target.read_text(encoding="utf-8")


def testTheAppCarriesItsOwnCertificateList() -> None:
    import certifi

    assert httpsService.trustedAuthorityCount() > 100
    assert httpsService.sslContext() is httpsService.sslContext()  # built once
    assert certifi.where().endswith("cacert.pem")


def testFromSourceTheBundleIsTheCheckout() -> None:
    assert not appConfig.isFrozen
    assert appConfig.bundleRoot == appConfig.projectRoot
    assert appConfig.manualPath == appConfig.projectRoot / "docs" / "manual" / "README.md"
