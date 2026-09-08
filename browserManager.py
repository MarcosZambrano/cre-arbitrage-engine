import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)

URL = "https://www.loopnet.com/"

DEBUG_HOST = "127.0.0.1"
DEBUG_PORT = 9222
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
# Every profile lives under this root. delete_profile() refuses to touch anything
# outside it, so a bad profile_dir cannot turn into a stray recursive delete.
PROFILE_ROOT = r"C:\selenium"

class BrowserManager:
    def __init__(self):
        # Akamai can burn a profile: once it hands out a "blocked" _abck cookie, that
        # profile keeps getting Access Denied forever. `python main.py --fresh` starts
        # from a clean profile directory, which clears it.
        #
        # This must be an instance attribute. Assigning to the bare name PROFILE_DIR
        # here would create a local variable inside __init__ and leave the module
        # constant untouched, so --fresh silently did nothing.
        if "--fresh" in sys.argv:
            self.profile_dir = self.new_profile_dir()
        else:
            self.profile_dir = self.latest_profile_dir() or self.new_profile_dir()


    def port_is_open(self, host=DEBUG_HOST, port=DEBUG_PORT):
        """True if something is already listening on Chrome's debugging port."""
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            return False


    def start_chrome(self, url=URL):
        """Launch Chrome detached, so it outlives this script and keeps its cookies."""
        if not os.path.exists(CHROME_PATH):
            raise SystemExit(f"Chrome not found at {CHROME_PATH}")

        os.makedirs(self.profile_dir, exist_ok=True)

        command = [
            CHROME_PATH,
            f"--remote-debugging-port={DEBUG_PORT}",
            f"--user-data-dir={self.profile_dir}",
            # Without these, a brand-new profile opens Chrome's welcome screen
            # instead of the URL, and the browser never reaches LoopNet.
            "--no-first-run",
            "--no-default-browser-check",
            url,
        ]

        # DETACHED_PROCESS + CREATE_BREAKAWAY_FROM_JOB stop Chrome from being killed
        # when this Python process (or the terminal running it) goes away.
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        try:
            subprocess.Popen(command, creationflags=flags | subprocess.CREATE_BREAKAWAY_FROM_JOB)
        except OSError:
            # Some environments forbid breaking away from the job object.
            subprocess.Popen(command, creationflags=flags)


    def wait_for_port(self, timeout=30):
        """Block until Chrome's debugging port answers, or give up after `timeout`."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.port_is_open():
                return True
            time.sleep(0.5)
        return False


# ------------- MODULE 1: ACCESS LOOPNET WEBSITE -------------

# --- 1. Make sure a real Chrome is running with its debugging port open -------
#
# LoopNet sits behind Akamai Bot Manager. A browser that ChromeDriver spawns
# itself gets an "Access Denied" edge block, so we drive a normal Chrome with a
# real profile and real cookies instead. If one is already up we reuse it.
    def run(self):
        self.launch_and_attach()

        # --- 3. Confirm we got the real page and not the bot wall --------------------
        #
        # This check comes BEFORE any element lookup on purpose: otherwise a block and a
        # wrong selector both surface as the same unhelpful TimeoutException.

        if not self.wait_for_real_page():
            # The profile is burned. That is permanent for this profile, but a clean
            # one gets straight through, so rotate and retry once instead of dying
            # and making the user remember a flag.
            print(f"Profile {self.profile_dir} is burned - rotating to a fresh one.")
            burned = self.running_profile_dir() or self.profile_dir

            # Kill by the profile the browser is ACTUALLY using, not by
            # self.profile_dir. When the port was already open we inherited
            # someone else's browser, so those two can differ - and killing the
            # wrong one left the burned browser alive, whereupon launch_and_attach
            # cheerfully reattached to it and reported the fresh profile as blocked.
            self.close_chrome_for_profile(burned)
            self.wait_for_port_to_close()

            # Delete only after the browser is gone and the port is released,
            # otherwise Chrome still holds the files open.
            reclaimed = self.delete_profile(burned)
            if reclaimed:
                print(f"Deleted burned profile ({reclaimed} MB reclaimed).")

            self.profile_dir = self.new_profile_dir()
            self.launch_and_attach()

            if not self.wait_for_real_page():
                raise SystemExit(
                    "Blocked by Akamai even on a brand-new profile.\n"
                    "That points at the network rather than the profile: disable any "
                    "VPN/proxy, or try a different connection."
                )

        print(f"Access OK -> {self.driver.title}")

    @staticmethod
    def new_profile_dir():
        return os.path.join(PROFILE_ROOT, f"loopnet-{datetime.now():%Y%m%d-%H%M%S}")

    @staticmethod
    def latest_profile_dir():
        """Most recently used profile under PROFILE_ROOT, or None if there are none.

        Rotation deletes a burned profile and creates a timestamped replacement, so
        any hardcoded default goes stale the first time a profile is burned - which
        cost a pointless rotate-and-relaunch cycle on every cold start. Picking the
        newest directory keeps the warm profile in use without anything to maintain.
        """
        try:
            candidates = [
                os.path.join(PROFILE_ROOT, name)
                for name in os.listdir(PROFILE_ROOT)
                if name.startswith("loopnet-")
                and os.path.isdir(os.path.join(PROFILE_ROOT, name))
            ]
        except OSError:
            return None
        return max(candidates, key=os.path.getmtime) if candidates else None

    @staticmethod
    def running_profile_dir():
        """The --user-data-dir of the Chrome currently holding the debug port.

        Needed because an already-running browser may have been started by an
        earlier run with a different profile than this instance is configured for.
        """
        script = (
            "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
            f"Where-Object {{ $_.CommandLine -like '*--remote-debugging-port={DEBUG_PORT}*' }} | "
            "ForEach-Object { if ($_.CommandLine -match '--user-data-dir=([^\" ]+)') "
            "{ $matches[1]; break } }"
        )
        try:
            done = subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                capture_output=True, text=True, timeout=20,
            )
            found = done.stdout.strip().splitlines()
            return found[0].strip() if found else None
        except Exception:
            return None

    @staticmethod
    def delete_profile(profile_dir):
        """Delete a burned profile directory. Returns the MB reclaimed, or 0.

        A burned profile is dead weight the moment it is detected: Akamai's
        rejection is stored in its cookie database and is permanent, so the
        directory can never be used again. Without this, every burn left another
        100-250 MB directory behind for good.

        Deliberately defensive, because this is a recursive delete running
        unattended: the path must resolve to somewhere strictly inside
        PROFILE_ROOT, must not be PROFILE_ROOT itself, and must actually look
        like a Chrome profile. Cleanup failure is never fatal - a leftover
        directory is a nuisance, a crashed scraper is not.
        """
        target = os.path.abspath(profile_dir)
        root = os.path.abspath(PROFILE_ROOT)

        inside_root = os.path.normcase(target).startswith(os.path.normcase(root) + os.sep)
        if not inside_root or target == root:
            print(f"Refusing to delete {target!r}: outside {root}")
            return 0

        # A Chrome profile always has one of these. Guards against pointing this
        # at some unrelated directory that happens to sit under the root.
        looks_like_profile = any(
            os.path.exists(os.path.join(target, name))
            for name in ("Local State", "Default")
        )
        if not looks_like_profile:
            print(f"Refusing to delete {target!r}: not a Chrome profile")
            return 0

        size_mb = 0
        for current, _dirs, files in os.walk(target):
            for name in files:
                try:
                    size_mb += os.path.getsize(os.path.join(current, name))
                except OSError:
                    pass
        size_mb = round(size_mb / (1024 * 1024), 1)

        # Chrome releases its file handles a moment after the process dies, so a
        # single attempt can fail on a locked file even though the kill worked.
        for attempt in range(3):
            try:
                shutil.rmtree(target)
                return size_mb
            except OSError as err:
                if attempt == 2:
                    print(f"Could not delete {target}: {err}")
                    return 0
                time.sleep(2)
        return 0

    @staticmethod
    def close_chrome_for_profile(profile_dir):
        """Terminate only the Chrome processes using this profile directory.

        driver.quit() is not enough: Selenium merely attached to this browser, it
        did not start it, so quitting the session leaves the process running and
        the debug port open - and the next launch would reattach to the same
        burned browser instead of starting a clean one.

        Matching on the profile directory keeps this surgical: the user's ordinary
        Chrome windows use a different --user-data-dir and are left alone.
        """
        marker = os.path.basename(profile_dir.rstrip("\\/"))
        script = (
            "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
            f"Where-Object {{ $_.CommandLine -like '*{marker}*' }} | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
        )

    def navigate(self, url, timeout=90):
        """Load `url` by restarting Chrome on it, then re-attach Selenium.

        Akamai rejects any navigation made in a browser that ChromeDriver has
        attached to - and the taint outlives driver.quit(), so detaching first is
        not enough. What does work is a page loaded by a browser that has never
        been driven: Chrome launched directly at the URL passes every time.

        The profile itself is not tainted, only the live browser session, so the
        same profile (and its cookies) is reused across relaunches.

        Costs roughly 20-30s per navigation, which is the price of the only
        sequence that survives the bot wall.
        """
        if getattr(self, "driver", None) is not None:
            self.driver.quit()
            self.driver = None

        self.close_chrome_for_profile(self.running_profile_dir() or self.profile_dir)
        self.wait_for_port_to_close()

        self.start_chrome(url)
        if not self.wait_for_port():
            raise SystemExit(f"Chrome did not reopen {DEBUG_HOST}:{DEBUG_PORT}")

        deadline = time.time() + timeout
        title = ""
        while time.time() < deadline:
            titles = self.devtools_page_titles()
            title = titles[0] if titles else ""
            if any("Access Denied" in t for t in titles):
                raise SystemExit(
                    f"Blocked by Akamai while loading {url}. "
                    "Re-run to rotate to a clean profile."
                )
            # While the challenge runs the title is the bare host, "loopnet.com".
            if title and title != "loopnet.com":
                break
            time.sleep(1)
        else:
            raise SystemExit(f"{url} never settled (last title: {title!r})")

        self.attach()
        # Right after attaching, driver.title can come back empty for a beat.
        settle = time.time() + 10
        while time.time() < settle and not (self.driver.title or ""):
            time.sleep(0.5)
        return self.driver

    def close_other_tabs(self):
        """Close every tab except the one currently focused."""
        keep = self.driver.current_window_handle
        for handle in self.driver.window_handles:
            if handle != keep:
                self.driver.switch_to.window(handle)
                self.driver.close()
        self.driver.switch_to.window(keep)

    def focus_tab(self, url):
        """Point the re-attached driver at the tab showing `url`."""
        marker = urllib.parse.urlparse(url).path or url
        for handle in self.driver.window_handles:
            self.driver.switch_to.window(handle)
            if marker in (self.driver.current_url or ""):
                return True
        return False

    def devtools_target_title(self, target_id):
        """Title of one specific DevTools target, read without a CDP session."""
        try:
            url = f"http://{DEBUG_HOST}:{DEBUG_PORT}/json/list"
            raw = urllib.request.urlopen(url, timeout=5).read()
            for target in json.loads(raw):
                if target.get("id") == target_id:
                    return target.get("title", "")
        except Exception:
            pass
        return ""

    def devtools_page_titles(self):
        """Tab titles read passively from the DevTools HTTP endpoint (no CDP session)."""
        try:
            url = f"http://{DEBUG_HOST}:{DEBUG_PORT}/json/list"
            raw = urllib.request.urlopen(url, timeout=5).read()
            return [t.get("title", "") for t in json.loads(raw) if t.get("type") == "page"]
        except Exception:
            return []

    def wait_for_challenge_via_devtools(self, timeout=60):
        """Watch the tab title until the challenge resolves, without attaching."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            titles = self.devtools_page_titles()
            # The interstitial title is the bare host, "loopnet.com".
            if any("LoopNet" in t for t in titles):
                return True
            if any("Access Denied" in t for t in titles):
                return False
            time.sleep(1)
        return False

    def wait_for_port_to_close(self, timeout=15):
        """Wait for the old Chrome to release the debugging port before relaunching."""
        deadline = time.time() + timeout
        while time.time() < deadline and self.port_is_open():
            time.sleep(0.5)

    def attach(self):
        """Attach Selenium to the Chrome already listening on the debug port."""
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_experimental_option("debuggerAddress", f"{DEBUG_HOST}:{DEBUG_PORT}")
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
        except WebDriverException as err:
            raise SystemExit(f"Could not attach to Chrome.\n\nOriginal error: {err}")
        return self.driver

    def launch_and_attach(self):
        """Ensure Chrome is running on the debug port, then attach Selenium to it."""
        if self.port_is_open():
            print(f"Chrome already listening on {DEBUG_HOST}:{DEBUG_PORT} - reusing it.")
        else:
            print(f"Starting Chrome (profile: {self.profile_dir})...")
            self.start_chrome()
            if not self.wait_for_port():
                raise SystemExit(
                    f"Chrome did not open {DEBUG_HOST}:{DEBUG_PORT} within 30s.\n"
                    f"Close any Chrome window already using {self.profile_dir} and try again."
                )
            print("Chrome is up. Waiting for the Akamai challenge to clear...")

            # Do NOT attach Selenium yet. The debug port binds within a second or
            # two, but Akamai's JS challenge needs ~15-20s more. Attaching
            # ChromeDriver mid-challenge is itself enough to fail it and burn the
            # profile - that is what kept producing Access Denied on profiles that
            # loaded fine when left alone.
            #
            # /json/list is a passive HTTP read of the DevTools target list. It
            # reports the tab title without opening a CDP session, so watching
            # through it does not disturb the challenge.
            self.wait_for_challenge_via_devtools()

        # --- 2. Attach to it ---------------------------------------------------------

        self.attach()

        # Navigate only if we are not already somewhere on loopnet.com.
        #
        # An exact != URL comparison meant that any run after a search - where the
        # URL has become /search/... - triggered a driver.get() reload. Reloading
        # while ChromeDriver is attached is what burns the profile: the challenge
        # re-runs under an active CDP session and fails. Chrome is launched with
        # the URL already, so on a cold start there is nothing to navigate to.
        # current_url is None for a moment right after attaching to a
        # freshly launched browser, so guard it.
        if "loopnet.com" not in (self.driver.current_url or ""):
            self.driver.get(URL)

    def wait_for_real_page(self, timeout=45):
        """Return True once the real page loads, False if Akamai blocked us.

        On a cold profile the challenge runs for 10-20 seconds. While it does, the
        tab title is the bare host ("loopnet.com"), which is neither the real page
        nor a block. Checking too early reads that interstitial and misreports it,
        so poll until the title actually settles.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            title = self.driver.title

            if "Access Denied" in title or "Access Denied" in self.driver.page_source[:2000]:
                return False

            # The real homepage title; the interstitial is just "loopnet.com".
            if "LoopNet" in title:
                return True

            time.sleep(1)

        raise SystemExit(
            f"Page never settled within {timeout}s (last title: {self.driver.title!r}).\n"
            "The Akamai challenge may still be running - try again."
        )

        # --- 4. Find the search bar --------------------------------------------------
        #
        # Two inputs are named "geography"; the first is the visible one
        # (placeholder "Enter a location"), the second is hidden.

        # wait = WebDriverWait(self.driver, 10)

        # try:
        #     geography_input = wait.until(
        #         EC.visibility_of_element_located((By.NAME, "geography"))
        #     )



        # except TimeoutException:
        #     raise SystemExit(
        #         "Page loaded, but no visible input named 'geography' was found.\n"
        #         "Inspect the search box in DevTools and update the locator."
        #     )

        # print(f"Search bar found: placeholder={geography_input.get_attribute('placeholder')!r}")

        # Never call driver.quit(): it would close the browser we just warmed up and
        # throw away the Akamai cookies stored in the profile.




