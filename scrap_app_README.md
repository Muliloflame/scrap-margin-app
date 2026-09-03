# Scrap Metal Margin Calculator — Android app (Python / Kivy)

This is the same calculator as the web version, written in Python with
[Kivy](https://kivy.org) so it runs as a native Android app (and also
runs on your desktop for quick testing, no phone required).

## What it does
- Shows the full ZAR/kg price sheet grouped by category (Copper, Brass &
  Gunmetal, Aluminium, Lead/Zinc/Batteries, Stainless, Exotic Metals).
- Converts each price to Kwacha using an editable ZAR→ZMW rate.
- Lets you enter your buy price (ZK/kg) and the kg bought for each
  product.
- Deducts an editable transport cost (R/kg) before computing margin.
- Shows per-product margin % and profit, and a running total at the
  bottom: total kg, total spent, total transport (in ZK and R), and
  total profit.
- **Settlement Slip** (at the bottom of the scrollable list): mirrors a
  buyer's payout docket — subtotal at ZAR sheet prices for the kg
  you've entered, minus a cash-handling charge (%), an advance
  deduct, and the transport deduct, giving the final balance in Rand
  and its Kwacha equivalent.
- **Local Kwacha trades**: Ali Cans, Ali Cast Clean, and Ali Old Roll
  Clean are priced directly in Kwacha (both buy and sell) rather than
  converted from the ZAR sheet — no transport is deducted from their
  margin, and they're left out of the Settlement Slip since they never
  cross into the ZAR side of the business.
- **Live forex rate**: a "Fetch live rate" button pulls the ZAR→ZMW
  rate straight from your own `forex_bridge.py` service (which reads
  the FNB/Zanaco rates your `master_scraper.py` saves to MySQL) — see
  the separate `forex_bridge` project for setup. If the bridge isn't
  running, it fails gracefully and you can still type the rate in by
  hand.
- Saves everything to a small JSON file on the device automatically —
  closing and reopening the app keeps your numbers.

## 1. Try it on your computer first (optional, no Android tools needed)

```bash
pip install kivy
python3 main.py
```

A desktop window opens with the same app — good for checking it looks
right before building the Android version. You can skip this and go
straight to step 2 if you just want the APK.

## 2. Build the APK using GitHub Actions (recommended — no Linux needed)

This folder includes `.github/workflows/build.yml`, which tells GitHub
to build the Android APK for you on their servers — you don't need
Buildozer, Linux, WSL, or the Android SDK installed on your own PC at
all.

1. **Create a free GitHub account** at github.com if you don't have one.
2. **Create a new repository** — click the "+" in the top right →
   "New repository". Give it any name (e.g. `scrap-margin-app`), leave
   it Public or Private, don't add a README, click "Create repository".
3. **Upload the files** — on the new repo's page, click
   "uploading an existing file", then drag in everything from this
   folder: `main.py`, `buildozer.spec`, `README.md`, and the whole
   `.github` folder (drag the folder itself, GitHub keeps its
   structure). Scroll down and click "Commit changes".
4. **Watch it build** — click the "Actions" tab at the top of your
   repo. You should see a workflow run start automatically (it's
   triggered by the upload). Click into it — it takes roughly
   10–20 minutes the first time.
5. **Download the APK** — once it finishes (green checkmark), stay on
   that same run's page and scroll down to "Artifacts". Click
   `scrap-margin-apk` to download a zip containing your `.apk` file.

If the build fails (red X), click into the failed step to see the
error message — paste it back for help fixing it.

## 3. Get the APK onto your phone

The zip you downloaded is on your computer, not your phone, so get it
across some way you already use — email it to yourself, upload to
Google Drive/WhatsApp/etc., or plug your phone in via USB and copy it
over like any file.

Then on your phone:
1. Open the `.apk` file (from your Downloads app, Gmail, Drive, etc.)
2. Android will warn about installing from an unknown source —
   allow it (you'll need to approve this once, in Settings, the first
   time).
3. Tap Install.

## Alternative: building it yourself with Buildozer (Linux/WSL2 only)

If you'd rather build locally instead of using GitHub, you'll need a
Linux environment (WSL2 on Windows works):

```bash
sudo apt update
sudo apt install -y python3-pip build-essential git python3-dev \
    ffmpeg libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
    libportmidi-dev libswscale-dev libavformat-dev libavcodec-dev \
    zlib1g-dev openjdk-17-jdk unzip

pip install --upgrade buildozer cython
buildozer android debug
```

The APK lands in `bin/`. With your phone connected via USB and USB
debugging enabled, `buildozer android deploy run` installs and
launches it directly.

## Notes
- `icon.filename` in `buildozer.spec` points to `icon.png`, which isn't
  included — either add your own 512×512 PNG next to `main.py`, or
  delete that line to use Kivy's default icon.
- `android.permissions = INTERNET` is set in `buildozer.spec` — needed
  for the "Fetch live rate" feature to reach your forex bridge over
  Wi-Fi. See the separate `forex_bridge` project, and note the app's
  "Bridge address" field needs your PC's LAN IP (not `localhost`) when
  running on an actual phone.
