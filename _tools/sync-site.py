#!/usr/bin/env python3
"""
Mirror the Cxotable Composer to the live site.

Takes a saved copy of the composer artifact, rebuilds the plain site file the
way the composer's own "Download site" button does, and pushes it to the
branch GitHub Pages serves. Exits 0 and does nothing when the site is already
up to date, so it is safe to run on a schedule.

    python3 sync-site.py <path-to-artifact-html>

The build runs the artifact's own renderers in a headless browser rather than
reimplementing them, so this never drifts from what the composer produces.
"""
import glob
import pathlib
import subprocess
import sys
import tempfile

REPO = "https://github.com/Ayush9205NITRR/enout-oddtable.git"
BRANCH = "claude/website-preview-drag-drop-gtrnu4"
TARGET = "index.html"
AUTHOR_NAME = "Ayush9205NITRR"
AUTHOR_EMAIL = "100430326+Ayush9205NITRR@users.noreply.github.com"


def chromium():
    """The preinstalled browser, without pinning a version that may change."""
    for pattern in (
        "/opt/pw-browsers/chromium-*/chrome-linux/chrome",
        "/opt/pw-browsers/chromium/chrome-linux/chrome",
    ):
        hits = sorted(glob.glob(pattern))
        if hits:
            return hits[-1]
    return None


def build(artifact_path):
    from playwright.sync_api import sync_playwright

    src = pathlib.Path(artifact_path).resolve()
    if not src.exists():
        sys.exit("artifact not found: %s" % src)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=chromium())
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        problems = []
        page.on("pageerror", lambda e: problems.append(str(e)))
        page.goto("file://%s" % src)
        page.wait_for_timeout(2500)
        # Download site writes to the clipboard when no download host is present.
        html = page.evaluate(
            """(function () {
                 var captured = null;
                 navigator.clipboard.writeText = function (t) {
                   captured = t; return Promise.resolve();
                 };
                 var btn = document.getElementById('btn-site');
                 if (!btn) return null;
                 btn.click();
                 return captured;
               })()"""
        )
        browser.close()

    if problems:
        sys.exit("the composer raised errors while building: %s" % problems[:3])
    if not html or not html.lstrip().lower().startswith("<!doctype html>"):
        sys.exit("build produced nothing usable")
    if "<body>" not in html or len(html) < 2000:
        sys.exit("build looks truncated (%d bytes)" % len(html or ""))
    return html if html.endswith("\n") else html + "\n"


def publish(html):
    work = tempfile.mkdtemp(prefix="cxotable-")
    subprocess.run(
        ["git", "clone", "--depth", "1", "-b", BRANCH, REPO, work],
        check=True, capture_output=True,
    )
    target = pathlib.Path(work) / TARGET
    if target.exists() and target.read_text() == html:
        print("no change — the live site already matches the composer")
        return False

    target.write_text(html)
    git = ["git", "-C", work, "-c", "user.name=%s" % AUTHOR_NAME,
           "-c", "user.email=%s" % AUTHOR_EMAIL]
    subprocess.run(git + ["add", TARGET], check=True, capture_output=True)
    subprocess.run(
        git + ["commit", "-m", "Publish the composer's latest saved version"],
        check=True, capture_output=True,
    )
    subprocess.run(git + ["push", "origin", BRANCH], check=True, capture_output=True)
    print("published %d bytes to %s" % (len(html), BRANCH))
    return True


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    publish(build(sys.argv[1]))
