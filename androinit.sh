#!/bin/bash

if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    DOWNLOAD_URL=$(curl -s https://developer.android.com/studio | grep -Eo 'https://dl.google.com/android/repository/commandlinetools-linux-[0-9]+_latest.zip' | head -n 1)
elif [[ "$OSTYPE" == "darwin"* ]]; then
    DOWNLOAD_URL=$(curl -s https://developer.android.com/studio | grep -Eo 'https://dl.google.com/android/repository/commandlinetools-mac-[0-9]+_latest.zip' | head -n 1)
else
    echo "Unsupported platform: $OSTYPE"
    exit 1
fi

if ! command -v java &> /dev/null; then
    echo "!!!![ERR] Java is not installed or not available in your PATH."
    echo "Install Java to run this script."
    exit 1
fi

if [ "$SHELL" = "/bin/bash" ] || [ "$SHELL" = "/usr/bin/bash" ]; then
    SHELL_RC="$HOME/.bashrc"
elif [ "$SHELL" = "/bin/zsh" ] || [ "$SHELL" = "/usr/bin/zsh" ]; then
    SHELL_RC="$HOME/.zshrc"
else
    echo "[INFO] Your current shell is not bash or zsh."
    read -p "Specify the path to your shell's rc file: " SHELL_RC
fi

echo "[INFO] Editing shell configuration file: $SHELL_RC"

TOOLS_DIR="$HOME/Tools"
CMDLINE_TOOLS_DIR="$TOOLS_DIR/cmdline-tools"
LATEST_DIR="$CMDLINE_TOOLS_DIR/latest"
mkdir -p "$TOOLS_DIR"

if [ -z "$DOWNLOAD_URL" ]; then
    echo "!!!![ERR] Unable to find the latest command-line tools download URL. Install manually."
    exit 1
fi

ZIP_FILE="$TOOLS_DIR/commandlinetools.zip"
echo "[INFO] Downloading Android SDK tools from: $DOWNLOAD_URL"
curl -o "$ZIP_FILE" "$DOWNLOAD_URL" || { echo "Download failed!"; exit 1; }

echo "[INFO] Extracting SDK tools to $TOOLS_DIR"
unzip -o "$ZIP_FILE" -d "$TOOLS_DIR" || { echo "Extraction failed!"; exit 1; }
rm "$ZIP_FILE"

mkdir -p "$LATEST_DIR"
mv "$TOOLS_DIR/cmdline-tools/"* "$LATEST_DIR/"

ANDROID_SDK_ROOT="$TOOLS_DIR"
PLATFORM_TOOLS_DIR="$ANDROID_SDK_ROOT/platform-tools"
CMDLINE_BIN_DIR="$LATEST_DIR/bin"

if ! grep -q "ANDROID_SDK_ROOT" "$SHELL_RC"; then
    echo "[INFO] Exporting paths to $SHELL_RC"
    {
        echo ""
        echo "# Android SDK environment variables"
        echo "export ANDROID_SDK_ROOT=$ANDROID_SDK_ROOT"
        echo "export ANDROID_HOME=$ANDROID_SDK_ROOT"
        echo "export PATH=\$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:\$ANDROID_SDK_ROOT/emulator:\$ANDROID_SDK_ROOT/platform-tools:\$PATH"
    } >>"$SHELL_RC"
fi

echo "[INFO] Please reload your shell configuration by running: source $SHELL_RC"

echo "[INFO] Downloading platform-tools using sdkmanager"
yes | "$CMDLINE_BIN_DIR/sdkmanager" "platform-tools"

if [ ! -d "$PLATFORM_TOOLS_DIR" ]; then
    echo "!!!![ERR] platform-tools directory is missing. Please check the installation."
    exit 1
fi

ARCH=$(uname -m)
echo "[INFO] System architecture detected: $ARCH"
read -p "Do you want system images for the same architecture? (y/n): " SAME_ARCH

echo "Listing available system images..."
"$CMDLINE_BIN_DIR/sdkmanager" --list | grep "system-images"

read -p "Enter the system image you want to download (e.g., system-images;android-33;google_apis;x86_64): " IMAGE
if [ -z "$IMAGE" ]; then
    echo "!!!![ERR] No system image provided. Exiting."
    exit 1
fi

echo "[INFO] Downloading system image: $IMAGE"
yes | "$CMDLINE_BIN_DIR/sdkmanager" "$IMAGE"

ANDROID_VERSION=$(echo "$IMAGE" | grep -oE 'android-[0-9]+')

if [ -n "$ANDROID_VERSION" ]; then
    echo "[INFO] Detected Android version: $ANDROID_VERSION. Downloading platform files."
    y | "$CMDLINE_BIN_DIR/sdkmanager" "platforms;$ANDROID_VERSION"
else
    echo "!!!![ERR] Unable to detect Android version from the system image. Skipping platform download. Make sure to download the platform otherwise emulator WILL NOT WORK."
fi

AVD_NAME="default"
read -p "Name your AVD: " AVD_NAME

echo "[INFO] Creating an AVD with the name: $AVD_NAME"
"$CMDLINE_BIN_DIR/avdmanager" create avd -n "$AVD_NAME" -k "$IMAGE" --device "pixel"

echo "[SUCCESS] Your AVD ($AVD_NAME) is ready to use. Source your shell config and run emulator @($AVD_NAME)"
