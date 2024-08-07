#!/bin/bash

set -e  # Exit immediately if any command fails

echo "Downloading Chromium..."

curl "https://www.googleapis.com/download/storage/v1/b/chromium-browser-snapshots/o/Linux_x64%2F$CHROMIUM_VERSION%2Fchrome-linux.zip?generation=1652397748160413&alt=media" > /tmp/chromium.zip || { echo "Error downloading Chromium"; exit 1; }
unzip /tmp/chromium.zip -d /tmp/ || { echo "Error extracting Chromium"; exit 1; }
mv /tmp/chrome-linux/ /opt/chrome || { echo "Error moving Chromium"; exit 1; }

curl "https://www.googleapis.com/download/storage/v1/b/chromium-browser-snapshots/o/Linux_x64%2F$CHROMIUM_VERSION%2Fchromedriver_linux64.zip?generation=1652397753719852&alt=media" > /tmp/chromedriver_linux64.zip || { echo "Error downloading ChromeDriver"; exit 1; }
unzip /tmp/chromedriver_linux64.zip -d /tmp/ || { echo "Error extracting ChromeDriver"; exit 1; }
mv /tmp/chromedriver_linux64/chromedriver /opt/chromedriver || { echo "Error moving ChromeDriver"; exit 1; }