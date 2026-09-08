# OPTIONAL. You normally do not need this file any more -- main.py starts Chrome
# by itself. Keep it for when you want a browser open to poke around by hand.
#
# Do NOT delete C:\selenium\loopnet-chrome -- it holds the Akamai cookies that
# get us past the bot wall. If the site starts returning "Access Denied", the
# profile has been burned; run `python main.py --fresh` instead of deleting it.

$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$profileDir = "C:\selenium\loopnet-chrome"

if (-not (Test-Path $chrome)) {
    Write-Error "Chrome not found at $chrome"
    exit 1
}

if (-not (Test-Path $profileDir)) {
    New-Item -ItemType Directory -Force -Path $profileDir | Out-Null
    Write-Host "Created profile directory $profileDir"
}

Write-Host "Launching Chrome with remote debugging on 127.0.0.1:9222 ..."

# --no-first-run / --no-default-browser-check matter: without them a brand-new
# profile opens Chrome's welcome screen and never navigates to the URL.
& $chrome `
    --remote-debugging-port=9222 `
    --user-data-dir="$profileDir" `
    --no-first-run `
    --no-default-browser-check `
    "https://www.loopnet.com/"

# Check the port is up:
#   Invoke-WebRequest http://127.0.0.1:9222/json/version -UseBasicParsing
