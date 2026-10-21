#!/bin/bash

KLIPPER_PATH="${KLIPPER_PATH:-${HOME}/klipper}"
INSTALL_PATH="${INSTALL_PATH:-${HOME}/klipper-toolchanger}"
MOONRAKER_PATH="${MOONRAKER_PATH:-${HOME}/moonraker}"
MOONRAKER_CONFIG="${MOONRAKER_CONFIG:-${HOME}/printer_data/config/moonraker.conf}"
MOONRAKER_SERVICE="${MOONRAKER_SERVICE:-moonraker}"
REPOSITORY_URL="${REPOSITORY_URL:-https://github.com/orion23rigel/klipper-toolchanger.git}"
MOONRAKER_COMPONENT_INSTALLED=0

set -eu
export LC_ALL=C

function preflight_checks {
    if [ "$EUID" -eq 0 ]; then
        echo "[PRE-CHECK] This script must not be run as root!"
        exit -1
    fi

    if [ ! -d "$KLIPPER_PATH" ]; then
        echo "[ERROR] Klipper path '$KLIPPER_PATH' does not exist!"
        echo "Set KLIPPER_PATH environment variable if Klipper is installed elsewhere."
        exit -1
    fi

    if [ "$(sudo systemctl list-units --full -all -t service --no-legend | grep -F 'klipper.service')" ]; then
        printf "[PRE-CHECK] Klipper service found! Continuing...\n\n"
    else
        echo "[ERROR] Klipper service not found, please install Klipper first!"
        exit -1
    fi
}

function check_download {
    local installdirname installbasename
    installdirname="$(dirname "${INSTALL_PATH}")"
    installbasename="$(basename "${INSTALL_PATH}")"

    if [ ! -d "${INSTALL_PATH}" ]; then
        echo "[DOWNLOAD] Downloading repository from ${REPOSITORY_URL}..."
        if git -C "${installdirname}" clone "${REPOSITORY_URL}" "${installbasename}"; then
            chmod +x "${INSTALL_PATH}/install.sh"
            printf "[DOWNLOAD] Download complete!\n\n"
        else
            echo "[ERROR] Download of git repository failed!"
            exit -1
        fi
    else
        printf "[DOWNLOAD] repository already found locally. Continuing...\n\n"
    fi
}

function link_extension {
    echo "[INSTALL] Linking extension to Klipper..."
    if [ ! -d "${KLIPPER_PATH}/klippy/extras/" ]; then
        echo "[ERROR] Klipper extras directory not found at ${KLIPPER_PATH}/klippy/extras/"
        exit -1
    fi
    for file in "${INSTALL_PATH}"/klipper/extras/*.py; do ln -sfn "${file}" "${KLIPPER_PATH}/klippy/extras/"; done
}

function link_moonraker_component {
    local components_dir source source_real file_manager_source target backup
    components_dir="${MOONRAKER_PATH}/moonraker/components"

    if [ ! -d "${components_dir}" ]; then
        echo "[INFO] Moonraker source checkout not found at '${MOONRAKER_PATH}'."
        echo "[INFO] Skipping the optional Moonraker processor. Set MOONRAKER_PATH if it is elsewhere."
        return
    fi

    source="${INSTALL_PATH}/moonraker/toolchanger_gcode_processor.py"
    if [ ! -f "${source}" ]; then
        echo "[ERROR] Moonraker processor source not found at '${source}'."
        echo "Update this checkout from the intended fork before running the installer."
        exit 1
    fi

    file_manager_source="${components_dir}/file_manager/file_manager.py"
    if [ ! -f "${file_manager_source}" ] \
            || ! grep -q '^[[:space:]]*def register_gcode_processor' "${file_manager_source}" \
            || ! grep -q 'self[.]gcode_metadata[[:space:]]*=[[:space:]]*MetadataStorage' "${file_manager_source}"; then
        echo "[ERROR] Moonraker file-manager metadata processor API was not found at '${file_manager_source}'."
        echo "This component requires file_manager.gcode_metadata.register_gcode_processor()."
        exit 1
    fi

    if [ ! -f "${MOONRAKER_CONFIG}" ]; then
        echo "[ERROR] Moonraker config not found at '${MOONRAKER_CONFIG}'."
        echo "Set MOONRAKER_CONFIG to the active moonraker.conf path."
        exit 1
    fi

    if ! sudo systemctl list-units --full --all -t service --no-legend \
            | grep -Fq "${MOONRAKER_SERVICE}.service"; then
        echo "[ERROR] Moonraker service '${MOONRAKER_SERVICE}.service' was not found."
        echo "Set MOONRAKER_SERVICE if it uses a different unit name."
        exit 1
    fi

    target="${components_dir}/toolchanger_gcode_processor.py"
    source_real="$(readlink -f "${source}")"
    if [ -e "${target}" ] || [ -L "${target}" ]; then
        if [ "$(readlink -f "${target}")" != "${source_real}" ]; then
            echo "[ERROR] Refusing to replace existing Moonraker component '${target}'."
            exit 1
        fi
    else
        ln -s "${source_real}" "${target}"
    fi
    echo "[INSTALL] Moonraker processor link ready at ${target}"

    if grep -Fqx '[toolchanger_gcode_processor]' "${MOONRAKER_CONFIG}"; then
        echo "[INFO] Existing [toolchanger_gcode_processor] config preserved."
    else
        backup="${MOONRAKER_CONFIG}.bak.$(date +%Y%m%d%H%M%S)"
        cp -p "${MOONRAKER_CONFIG}" "${backup}"
        printf '%s\n' '' '[toolchanger_gcode_processor]' 'enabled: False' 'timeout: 120' '# Set these to a verified safe slicer-coordinate envelope before enabling:' '# x_min: ...' '# x_max: ...' '# y_min: ...' '# y_max: ...' >> "${MOONRAKER_CONFIG}"
        echo "[CONFIG] Added disabled processor section; backup: ${backup}"
    fi
    MOONRAKER_COMPONENT_INSTALLED=1
}

function restart_klipper {
    echo "[POST-INSTALL] Restarting Klipper..."
    sudo systemctl restart klipper
}

function restart_moonraker {
    if [ "${MOONRAKER_COMPONENT_INSTALLED}" -eq 1 ]; then
        echo "[POST-INSTALL] Restarting Moonraker..."
        sudo systemctl restart "${MOONRAKER_SERVICE}"
    fi
}

printf "\n======================================\n"
echo "- Klipper toolchanger install script -"
printf "======================================\n\n"

# Run steps
preflight_checks
check_download
link_extension
link_moonraker_component
restart_klipper
restart_moonraker
