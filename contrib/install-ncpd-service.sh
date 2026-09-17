#!/usr/bin/env bash
# Installiert den ncpd-Wrapper als systemd-User-Service (kein sudo noetig).
set -euo pipefail
here="$(cd -- "$(dirname -- "$0")" && pwd)"
install -Dm755 "$here/ncpd-psion" "$HOME/.local/bin/ncpd-psion"
install -Dm644 "$here/ncpd-psion.service" "$HOME/.config/systemd/user/ncpd-psion.service"
systemctl --user daemon-reload
systemctl --user enable --now ncpd-psion.service
systemctl --user --no-pager status ncpd-psion.service | head -5
