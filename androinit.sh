#!/bin/bash

if [ "$SHELL" = "/bin/bash" ] || [ "$SHELL" = "/usr/bin/bash" ]; then
    SHELL_RC="$HOME/.bashrc"
elif [ "$SHELL" = "/bin/zsh" ] || [ "$SHELL" = "/usr/bin/zsh" ]; then
    SHELL_RC="$HOME/.zshrc"
else
    echo "Your current shell is not bash or zsh."
    read -p "Please specify the path to your shell's rc file: " SHELL_RC
fi

echo "Editing shell configuration file: $SHELL_RC"

TOOLS_DIR="$HOME/Tools"
CMDLINE_TOOLS_DIR="$TOOLS_DIR/cmdline-tools"
LATEST_DIR="$CMDLINE_TOOLS_DIR/latest"
mkdir -p "$TOOLS_DIR"

DOWNLOAD_URL=$(curl -s https://developer.android.com/studio | grep -Eo 'https://dl.google.com/android/repository/commandlinetools-mac-[0-9]+_latest.zip' | head -n 1)

if [ -z "$DOWNLOAD_URL" ]; then
    echo "Unable to find the latest command-line tools download URL. Please check manually."
    exit 1
fi

ZIP_FILE="$TOOLS_DIR/commandlinetools.zip"
echo "Downloading Android SDK tools from: $DOWNLOAD_URL"
curl -o "$ZIP_FILE" "$DOWNLOAD_URL"

echo "Extracting SDK tools to $TOOLS_DIR"
unzip -o "$ZIP_FILE" -d "$TOOLS_DIR"
rm "$ZIP_FILE"

mkdir -p "$LATEST_DIR"
mv "$TOOLS_DIR/cmdline-tools/"* "$LATEST_DIR/"

ANDROID_SDK_ROOT="$TOOLS_DIR"
PLATFORM_TOOLS_DIR="$ANDROID_SDK_ROOT/platform-tools"
CMDLINE_BIN_DIR="$LATEST_DIR/bin"

if ! grep -q "ANDROID_SDK_ROOT" "$SHELL_RC"; then
    echo "Exporting paths to $SHELL_RC"
    echo "" >>"$SHELL_RC"
    echo "# Android SDK environment variables" >>"$SHELL_RC"
    echo "export ANDROID_SDK_ROOT=$ANDROID_SDK_ROOT" >>"$SHELL_RC"
    echo "export ANDROID_HOME=$ANDROID_SDK_ROOT" >>"$SHELL_RC"
    echo "export PATH=\$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:\$ANDROID_SDK_ROOT/platform-tools:\$PATH" >>"$SHELL_RC"
fi

echo "Applying changes to the shell"
source "$SHELL_RC"

echo "Downloading platform-tools using sdkmanager"
"$CMDLINE_BIN_DIR/sdkmanager" "platform-tools"

ARCH=$(uname -m)
echo "Your system architecture is detected as: $ARCH"
read -p "Do you want system images for the same architecture only? (y/n): " SAME_ARCH

echo "Listing available system images..."
"$CMDLINE_BIN_DIR/sdkmanager" --list | grep "system-images"

read -p "Please enter the system image you want to download (e.g., system-images;android-30;google_apis;x86_64): " IMAGE
if [ -z "$IMAGE" ]; then
    echo "No system image provided. Exiting."
    exit 1
fi

echo "Downloading the selected system image: $IMAGE"
"$CMDLINE_BIN_DIR/sdkmanager" "$IMAGE"

AVD_NAME="Custom_AVD"
echo "Creating an AVD with the name: $AVD_NAME"
"$CMDLINE_BIN_DIR/avdmanager" create avd -n "$AVD_NAME" -k "$IMAGE" --device "pixel"

echo "Android SDK tools, platform-tools, and system images are installed!"
echo "Your AVD ($AVD_NAME) is ready to use!"
