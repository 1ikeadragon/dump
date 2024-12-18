#!/bin/bash

function check_java() {
    if ! command -v java &> /dev/null; then
        echo "Java is not installed or not available in your PATH."
        echo "Install Java to run this script."
        exit 1
    fi
}

function configure_shell_rc() {
    if [ "$SHELL" = "/bin/bash" ] || [ "$SHELL" = "/usr/bin/bash" ]; then
        SHELL_RC="$HOME/.bashrc"
    elif [ "$SHELL" = "/bin/zsh" ] || [ "$SHELL" = "/usr/bin/zsh" ]; then
        SHELL_RC="$HOME/.zshrc"
    else
        echo "Your current shell is not bash or zsh."
        read -p "Specify the path to your shell's rc file: " SHELL_RC
    fi

    if ! grep -q "ANDROID_SDK_ROOT" "$SHELL_RC"; then
        echo "Exporting paths to $SHELL_RC"
        echo "" >>"$SHELL_RC"
        echo "# Android SDK environment variables" >>"$SHELL_RC"
        echo "export ANDROID_SDK_ROOT=$ANDROID_SDK_ROOT" >>"$SHELL_RC"
        echo "export ANDROID_HOME=$ANDROID_SDK_ROOT" >>"$SHELL_RC"
        echo "export PATH=\$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:\$ANDROID_SDK_ROOT/emulator:\$ANDROID_SDK_ROOT/platform-tools:\$PATH" >>"$SHELL_RC"
    fi

    echo "Applying changes to the shell"
    source "$SHELL_RC"
}

function download_sdk_tools() {
    mkdir -p "$TOOLS_DIR"

    DOWNLOAD_URL=$(curl -s https://developer.android.com/studio | grep -Eo 'https://dl.google.com/android/repository/commandlinetools-mac-[0-9]+_latest.zip' | head -n 1)

    if [ -z "$DOWNLOAD_URL" ]; then
        echo "Unable to find the latest command-line tools download URL. Install manually."
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
}

function download_image_and_platform() {
    echo "Listing available system images..."
    "$CMDLINE_BIN_DIR/sdkmanager" --list | grep "system-images"

    read -p "Enter the system image you want to download (e.g., system-images;android-33;google_apis;x86_64): " IMAGE
    if [ -z "$IMAGE" ]; then
        echo "No system image provided. Exiting."
        exit 1
    fi

    echo "Downloading system image: $IMAGE"
    y | "$CMDLINE_BIN_DIR/sdkmanager" "$IMAGE"

    ANDROID_VERSION=$(echo "$IMAGE" | grep -oP 'android-\K[0-9]+')

    if [ -n "$ANDROID_VERSION" ]; then
        echo "Detected Android version: $ANDROID_VERSION. Downloading platform files."
        y | "$CMDLINE_BIN_DIR/sdkmanager" "platforms;android-$ANDROID_VERSION"
    else
        echo "Unable to detect Android version from the system image. Skipping platform download."
    fi
}

function create_avd() {
    read -p "Enter the name of your AVD: " AVD_NAME
    if [ -z "$AVD_NAME" ]; then
        AVD_NAME="default"
    fi

    echo "Creating an AVD with the name: $AVD_NAME"
    "$CMDLINE_BIN_DIR/avdmanager" create avd -n "$AVD_NAME" -k "$IMAGE" --device "pixel"

    echo "Your AVD ($AVD_NAME) is ready to use. Run emulator @$AVD_NAME to start it."
}

source "$SHELL_RC" 

TOOLS_DIR="$HOME/Tools"
CMDLINE_TOOLS_DIR="$TOOLS_DIR/cmdline-tools"
LATEST_DIR="$CMDLINE_TOOLS_DIR/latest"
ANDROID_SDK_ROOT="$TOOLS_DIR"
CMDLINE_BIN_DIR="$LATEST_DIR/bin"
PLATFORM_TOOLS_DIR="$ANDROID_SDK_ROOT/platform-tools"

check_java
configure_shell_rc

case "$1" in
    create-avd)
        create_avd
        ;;
    dl-image)
        download_sdk_tools
        download_image_and_platform
        ;;
    *)
        echo "Usage: $0 {create-avd|dl-image}"
        exit 1
        ;;
esac
