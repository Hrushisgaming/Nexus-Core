#!/usr/bin/env bash
# ==============================================================================
# Brahma Evo - macOS Build Script
# Builds BrahmaEvo.app via PyInstaller, then packages it into a distributable .dmg
# ==============================================================================
set -euo pipefail

echo "=============================================="
echo "  Brahma Evo - macOS App + DMG Build"
echo "=============================================="

APP_NAME="BrahmaEvo"

# Read only the numeric version, not the entire VSVersionInfo() blob
VERSION=$(cat version.txt 2>/dev/null | tr -d '\r\n' | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+' | head -n1 || echo "1.0.0")
VERSION="${VERSION:-1.0.0}"

DMG_NAME="BrahmaEvo-${VERSION}-macOS.dmg"

# ── 1. Clean previous builds ──────────────────────────────────────────
echo "[1/5] Cleaning previous builds..."
rm -rf dist build "${APP_NAME}.app"
mkdir -p dist

# ── 2. Build the .app with PyInstaller ────────────────────────────────
echo "[2/5] Building BrahmaEvo.app with PyInstaller..."

ARGS=(--noconfirm --clean --windowed --name "$APP_NAME")

# Only add --icon if an .icns exists
if [ -f "assets/nexus_app_icon.icns" ]; then
  ARGS+=(--icon=assets/nexus_app_icon.icns)
fi

ARGS+=(
  --add-data "assets:assets"
  --add-data "core:core"
  --add-data "actions:actions"
  --add-data "memory:memory"
  --add-data "smart_home:smart_home"
  --add-data "plugins:plugins"
  --add-data "features:features"
  --add-data "skills:skills"
  --add-data "dashboard/static:dashboard/static"
  --add-data "version.txt:."
  --add-data "requirements.txt:."
  --hidden-import mediapipe
  --hidden-import cv2
  --hidden-import google.genai
  --hidden-import PyQt6
  --hidden-import PyQt6.QtWebEngineCore
  --hidden-import PyQt6.QtWebEngineWidgets
  --hidden-import pyautogui
  --hidden-import sounddevice
  --hidden-import numpy
  main.py
)

pyinstaller "${ARGS[@]}"

APP_PATH="dist/${APP_NAME}.app"
if [ ! -d "$APP_PATH" ]; then
  echo "ERROR: PyInstaller did not produce ${APP_PATH}"
  exit 1
fi
echo "OK: ${APP_PATH} created"

# ── 3. Post-process the .app bundle ───────────────────────────────────
echo "[3/5] Finalizing .app bundle..."

# Ensure Info.plist has a proper identifier (PyInstaller sets one, but we tighten it)
PLIST="${APP_PATH}/Contents/Info.plist"
if [ -f "$PLIST" ]; then
  /usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier com.titech.brahmaevo" "$PLIST" 2>/dev/null || true
  /usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString ${VERSION}" "$PLIST" 2>/dev/null || true
  /usr/libexec/PlistBuddy -c "Set :LSMinimumSystemVersion 12.0" "$PLIST" 2>/dev/null || true

  # macOS will NOT show the microphone/camera permission prompt for a bundled app
  # unless these usage strings exist, so Gemini Live would silently hear nothing.
  set_plist_string() {
    /usr/libexec/PlistBuddy -c "Set :$1 $2" "$PLIST" 2>/dev/null \
      || /usr/libexec/PlistBuddy -c "Add :$1 string $2" "$PLIST"
  }
  set_plist_string NSMicrophoneUsageDescription "Nexus needs the microphone so you can talk to it by voice."
  set_plist_string NSCameraUsageDescription "Nexus uses the camera for vision and gesture features."
  set_plist_string NSAppleEventsUsageDescription "Nexus uses automation to control apps on your behalf."
fi

# Ad-hoc sign (no Developer ID needed) so the edited Info.plist is sealed and
# macOS can attach microphone permission to the app. Users still right-click > Open
# on first launch because it is not notarized.
codesign --force --deep --sign - "$APP_PATH"

# ── 4. Build the DMG ──────────────────────────────────────────────────
echo "[4/5] Creating ${DMG_NAME}..."

# Create a temporary staging folder
STAGING="dist/dmg_staging"
rm -rf "$STAGING"
mkdir -p "$STAGING"

# Copy the .app into staging
cp -R "$APP_PATH" "$STAGING/"

# Add a symlink to /Applications for drag-and-drop install
ln -s /Applications "$STAGING/Applications"

# Create a read-only DMG
hdiutil create "dist/${DMG_NAME}" \
  -volname "Brahma Evo ${VERSION}" \
  -srcfolder "$STAGING" \
  -ov -format UDZO

# Clean up staging
rm -rf "$STAGING"

# ── 5. Verify ─────────────────────────────────────────────────────────
echo "[5/5] Verifying build output..."
echo ""
echo "=============================================="
echo "  Build complete!"
echo "  App:    dist/${APP_NAME}.app"
echo "  DMG:    dist/${DMG_NAME}"
echo "=============================================="

ls -lh "dist/${APP_NAME}.app" 2>/dev/null || true
ls -lh "dist/${DMG_NAME}" 2>/dev/null || true
