# Canopy Finance Planner

An offline-first personal finance app: track monthly spending, build envelope
budgets for recurring costs (rent, subscriptions, EMIs), spot accidental
duplicate purchases (stationery/household restocking), and see visual
spending trends -- all stored locally in SQLite, with a custom glassmorphic
UI, built to package as an Android APK.

This is **Phase 1**: a complete, working app with manual/CSV-style
transaction entry, categorization, envelopes, budgeting, duplicate detection,
and trend charts. SMS-based auto-import is **Phase 2** (see below) -- it's
scaffolded for but intentionally not wired in yet, since it needs a real
Android device to test against and has real Play Store policy implications.

## Why nothing was compiled to a .apk in this pass

Building an actual Android `.apk` needs the Android SDK/NDK toolchain
(multi-GB downloads) and a full Gradle build, which is fragile to run
unattended in a cloud session with no device to test the result on. What's
here instead is the **complete, tested Python source** plus a ready
`buildozer.spec`, so you can produce the APK yourself in a few commands on
this machine (see below) -- and iterate on it, since you'll want to actually
run it on a phone/emulator to tune the UI anyway.

## Project layout

```
canopy_finance/
  main.py                  # App entry point, bottom-nav shell
  db/
    schema.sql              # SQLite schema (categories, transactions, envelopes, budgets...)
    database.py              # Connection, CRUD helpers, first-run seeding
  core/                       # All business logic -- framework-agnostic, fully unit tested
    models.py                 # Category / Transaction / Envelope dataclasses
    categorizer.py             # Offline merchant -> category rules + learning
    duplicate_detector.py       # Flags likely repeat purchases (stationery/household)
    budget_engine.py             # Trend-based next-month budget suggestions
    envelope_manager.py           # Envelope allocation, spend tracking, rollover
    analytics.py                   # Monthly trend / category breakdown queries
  ui/
    theme.py                  # Glass colors, spacing, status-color helpers
    widgets/                   # GlassCard, gradient background, charts (canvas-drawn), cards
    screens/                    # Dashboard, Transactions, Envelopes, Trends, Budget, Settings
  tests/                     # pytest suite for everything in core/ (30+ tests)
  buildozer.spec            # Android packaging config
  requirements.txt          # Desktop dev dependencies
```

## Running it on your desktop first (recommended before building the APK)

You already have Python, Android Studio, and Gradle on this machine, so the
fastest loop is: run the app as a normal desktop Kivy window first (windowed
at phone-portrait size), fix anything that looks wrong, *then* build the APK.

**Important: use Python 3.9-3.12, not whatever `python` defaults to.** Kivy's
Windows-only helper packages (`kivy_deps.sdl2_dev`, `gstreamer_dev`, `glew_dev`)
only ship prebuilt wheels for a specific range of CPython versions, and lag
behind new Python releases by months. If your system `python` is 3.13+
(check with `python --version`), `pip install -r requirements.txt` will fail
with something like `No matching distribution found for kivy_deps.sdl2_dev`.

Since Anaconda is already installed, the easiest fix is a dedicated conda
environment pinned to a compatible Python version:

```powershell
conda create -n canopy-finance python=3.11 -y
conda activate canopy-finance
cd "canopy_finance"
pip install -r requirements.txt
python main.py
```

(No Anaconda / prefer a plain venv instead: install Python 3.11 from
python.org alongside your existing Python, then `py -3.11 -m venv .venv`,
`.venv\Scripts\activate`, and continue as above.)

## Running the tests

```bash
cd canopy_finance
pip install pytest
pytest -v
```

## Building the Android APK

**Recommended: GitHub Actions (no local Android SDK/NDK setup at all).**
A ready-to-run workflow is already in this project at
`.github/workflows/build-apk.yml`. It builds the APK entirely on GitHub's
cloud runners using the [buildozer-action](https://github.com/ArtemSBulgakov/buildozer-action).

```powershell
# from inside canopy_finance/ (make this folder itself the repo root)
git init
git add .
git commit -m "Canopy Finance Planner -- Phase 1 + Phase 2 SMS import"
# create a new repo on github.com first (can be Private), then:
git remote add origin https://github.com/<your-username>/<repo-name>.git
git branch -M main
git push -u origin main
```

That push triggers the workflow automatically. To watch/download the result:
1. Go to your repo on github.com -> the **Actions** tab.
2. Click the running "Build Android APK" workflow (takes roughly 10-15 min).
3. Once it finishes, scroll to **Artifacts** at the bottom of the run page and
   download `canopy-finance-debug-apk` -- that's a zip containing the `.apk`.
4. Copy the `.apk` to your phone and open it to install (you'll need to allow
   "install from unknown sources" for sideloaded apps), or run
   `adb install canopyfinance-*.apk` if your phone is connected via USB
   with USB debugging on.

You can also trigger a rebuild any time from the Actions tab (the
`workflow_dispatch` trigger in the workflow file) without needing a new push.

**Alternative: WSL2, fully local.** If you'd rather nothing leave your
machine, or want to iterate on native builds faster than CI round-trips
allow:

```bash
# inside WSL2 (Ubuntu), with this project directory shared/accessible:
pip install buildozer cython
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip autoconf libtool pkg-config \
    zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev
cd canopy_finance
buildozer -v android debug
```

The first build downloads the Android SDK/NDK (several GB) and will take a
while. The resulting APK lands in `bin/canopyfinance-0.1.0-trial-debug.apk` --
copy it to your phone (or `adb install bin/*.apk`) to sideload it for
trial use. Since you already have Android Studio installed, you can point
`buildozer.spec`'s SDK/NDK paths at your existing installs (via the
`ANDROID_HOME` / `ANDROID_SDK_ROOT` env vars) to skip re-downloading them.

## Data & privacy

Every byte of financial data lives in one local SQLite file
(`<app data dir>/canopy_finance.db` on Android; `./data/canopy_finance.db` on
desktop). The app makes no network calls. `android.permissions` in
`buildozer.spec` is `INTERNET` only as a placeholder for future optional
features (e.g. cloud backup, opt-in) -- nothing currently uses it.

## Phase 2: SMS auto-import -- implemented

Settings now has a real "Scan SMS for bank/UPI transactions" toggle + "Scan
inbox now" button, and `android.permissions` in `buildozer.spec` includes
`READ_SMS`. How it works:

- `core/sms_parser.py` -- fully offline, regex-based parser for common Indian
  bank/UPI SMS templates (debit/credit alerts, UPI sent/received). No network,
  no ML. 13 unit tests cover the common formats plus OTP/promo/bill-reminder
  messages it should correctly ignore. Bank SMS formats vary and drift over
  time without notice, so treat `DEBIT_KEYWORDS`/`CREDIT_KEYWORDS`/the regexes
  in that file as a starting lexicon to extend as you see real messages it
  misses.
- `core/sms_import.py` -- the review-queue layer. Every parsed SMS lands in
  the `sms_staging` table with `status='pending'`; nothing becomes a real
  transaction until `approve_sms()` is called (i.e. the user taps Approve in
  Settings). Duplicate detection and merchant-category learning both run on
  approval, same as a manually-entered transaction.
- `integrations/android_sms.py` -- the actual Android-side read. Only
  importable inside a real python-for-android build (uses `pyjnius`/`android`,
  which don't exist on desktop Python) -- every call site wraps the import in
  a try/except, so desktop development is unaffected. It's a **one-shot inbox
  scan**, not a background listener: tapping "Scan inbox now" requests
  `READ_SMS` if not yet granted, reads the last 90 days of
  `content://sms/inbox` via `ContentResolver`, and stages whatever
  `core/sms_parser.py` recognizes. This could not be tested against a real
  device/SMS inbox in the environment this was built in -- **test this path
  first on a real phone** before relying on it, since bank SMS formats are
  the part most likely to need tuning.
- **Play Store policy still applies if you publish there.** `READ_SMS` is in
  Google Play's "sensitive permissions" group. For a finance app, Play only
  approves it if SMS reading is a *core, advertised feature* (which it is
  here) and you complete the Permissions Declaration Form in Play Console
  plus a privacy policy explicitly covering SMS use -- expect additional
  review scrutiny. None of this applies to sideloaded/trial installs.

## Roadmap beyond Phase 2

- CSV/bank-statement import as a lower-risk alternative to SMS reading.
- Export (CSV) for backup, since this is fully offline with no cloud sync.
- Category management UI (rename/merge/color) -- currently seeded defaults
  only.
- Per-envelope history charts (this vault's cost over the last 6 months).
