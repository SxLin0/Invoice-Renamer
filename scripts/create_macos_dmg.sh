#!/usr/bin/env bash
set -euo pipefail

APP_PATH="dist/曹姐发票改名器.app"
DMG_PATH="dist/InvoiceRenamer-macos.dmg"
VOLUME_NAME="曹姐发票改名器"

if [[ ! -d "$APP_PATH" ]]; then
  echo "Missing app bundle: $APP_PATH" >&2
  exit 1
fi

rm -f "$DMG_PATH"
hdiutil create \
  -volname "$VOLUME_NAME" \
  -srcfolder "$APP_PATH" \
  -ov \
  -format UDZO \
  "$DMG_PATH"
