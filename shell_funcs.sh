
alias ubersign="java -jar $HOME/Tools/cmdline-tools/latest/bin/uber-signer.jar"
alias szh="source ~/.zshrc"
alias emu=emulator
alias avdm=avdmanager
alias sdkm=sdkmanager
alias vi=nvim
alias vim=nvim
alias x86="$env /usr/bin/arch -x86_64 /bin/zsh" 
alias arm="$env /usr/bin/arch -arm64 /bin/zsh"
alias disas=apktool
alias apkb=apktool b


decom() {
  if [[ $# -ne 2 ]]; then
    echo -e "\033[1;31m[ERROR]\033[0m Usage: decom <api_level> <apk_file>"
    return 1
  fi

  local api_level="$1"
  local apk_file="$2"
  local apk_name
  local output_folder="src"
  local threads=$(nproc)

  apk_name=$(basename "$apk_file" .apk)

  echo -e "\033[1;34m[INFO]\033[0m Decoding APK with APKTool into $apk_name"
  apktool d "$apk_file" -o "$apk_name"

  if ! ls "$apk_name"/smali* >/dev/null 2>&1; then
    echo -e "\033[1;31m[ERROR]\033[0m No smali folders found in the APKTool output ($apk_name)."
    return 1
  fi

  cd "$apk_name" || {
    echo -e "\033[1;31m[ERROR]\033[0m Failed to move into $apk_name directory."
    return 1
  }

  echo -e "\033[1;34m[INFO]\033[0m Decompiling smali files with JADX into $output_folder"
  jadx -j "$threads" \
       --deobf \
       --show-bad-code \
       --escape-unicode \
       -Psmali-input.api-level="$api_level" \
       --no-res \
       smali* \
       -d "$output_folder"

  echo -e "\033[1;32m[FINI]\033[0m Decompilation completed. Output saved to $output_folder"
}


remu() {
    RETRIES=10
    SHOW_OUTPUT=false
    PORT=5555
    emulator_args="-no-window -no-boot-anim"
    custom_emulator_flags=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --retries)
                RETRIES="$2"
                shift 2
                ;;
            --show-output)
                SHOW_OUTPUT=true
                shift
                ;;
            --emu-flags)
                custom_emulator_flags="$2"
                shift 2
                ;;
            *)
                break
                ;;
        esac
    done

    log() {
        case "$1" in
            info) echo -e "\033[1;34m[INFO]\033[0m $2" ;;
            error) echo -e "\033[1;31m[ERROR]\033[0m $2" ;;
        esac
    }

    kill_port_process() {
        port=$1
        pid=$(lsof -i :$port -t)
        if [[ -n "$pid" ]]; then
            echo "[INFO] Killing process occupying port $port (PID: $pid)"
            kill -9 $pid
        else
            echo "[INFO] No process found on port $port to kill."
        fi
    }

    cleanup() {
        log info "Performing cleanup..."
        ssh tuf "pkill -f qemu-system-x86_64-headless" 2>/dev/null
        adb disconnect 2>/dev/null
        adb kill-server 2>/dev/null
        ssh tuf "adb kill-server" 2>/dev/null
        ssh tuf "adb start-server" 2>/dev/null
        kill_port_process $PORT
    }

    handle_exit() {
        cleanup
        log info "Exiting due to interruption or failure."
        exit 1
    }

    trap handle_exit SIGINT SIGTERM

    if [[ $# -lt 1 ]]; then
        echo "Usage: remu [--retries <number>] [--show-output] [--emu-flags <flags>] <emulator_args>"
        echo " remu --list"
        echo " remu --clean"
        return 1
    fi

    case "$1" in
        --list)
            log info "Listing connected devices..."
            ssh tuf "adb devices"
            return
            ;;
        --clean)
            cleanup
            return
            ;;
        --kill)
            if [[ -n "$2" ]]; then
                log info "Killing emulator with ID: $2"
                ssh tuf "adb -s $2 emu kill"
            else
                log error "Please provide the emulator ID to kill."
            fi
            return
            ;;
        --kill-all)
            log info "Killing all emulators on remote..."
            cleanup
            return
            ;;
        *)
            log info "Starting emulator with args: $*"
            log info "Using fixed port: $PORT"

            log info "Restarting local and remote ADB servers..."
            ssh tuf "adb kill-server" 2>/dev/null
            ssh tuf "adb start-server" 2>/dev/null

            log info "Setting up SSH tunnel on port $PORT..."
            ssh -f -N -L $PORT:127.0.0.1:5555 tuf

            log info "Starting emulator on remote..."
            if [[ -n "$custom_emulator_flags" ]]; then
                emulator_args="$custom_emulator_flags"
            fi

            tmp_file="/tmp/emulator_output_$$.log"
            if $SHOW_OUTPUT; then
                ssh tuf "emulator $emulator_args $*"
            else
                ssh tuf "emulator $emulator_args $* > $tmp_file 2>&1 &"
            fi

            log info "Waiting for emulator to initialize..."
            retries=$RETRIES
            while ((retries--)); do
                if adb connect localhost:$PORT; then
                    if adb -s localhost:$PORT shell getprop sys.boot_completed | grep 1 > /dev/null 2>&1; then
                        break
                    fi
                fi
                log info "Waiting for emulator to be ready... (retries left: $retries)"
                sleep 2
            done

            if ((retries <= 0)); then
                log error "Emulator failed to connect or boot within the timeout."
                [[ -f $tmp_file ]] && log info "Logs from remote: $(cat $tmp_file)"
                handle_exit
            fi

            log info "Emulator connected successfully."
            log info "Device list:"
            adb devices

            log info "Starting scrcpy..."
            scrcpy -s localhost:$PORT || handle_exit
            cleanup
            ;;
    esac
}
