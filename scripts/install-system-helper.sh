#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(dirname -- "$script_dir")

if [ "$(id -u)" -ne 0 ]; then
    echo "Run this installer as root:" >&2
    echo "  sudo $0" >&2
    exit 1
fi

install -d -o root -g root -m 0755 /usr/lib/keyd-mapper
install -o root -g root -m 0755 \
    "$project_dir/system/keyd-mapper-helper.py" \
    /usr/lib/keyd-mapper/keyd-mapper-helper

install -d -o root -g root -m 0755 /usr/share/polkit-1/actions
install -o root -g root -m 0644 \
    "$project_dir/system/io.github.keydmapper.apply-config.policy" \
    /usr/share/polkit-1/actions/io.github.keydmapper.apply-config.policy

echo "KeydMapper privileged helper installed successfully."
