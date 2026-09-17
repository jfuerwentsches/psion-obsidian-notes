#!/usr/bin/env bash
# Baut app/dist/PsiVault.app + .aif mit OpoLua. Das App-Icon (app/icon/*.bmp) wird
# vorher mit tools/make_mbm.lua zu app/icon/PsiVault.mbm gepackt (kein BMCONV noetig).
# --invert-masks: EPOC zeichnet das Icon dort, wo die Maske SCHWARZ ist; die BMPs im
# Paket sind innen weiss (am Geraet verifiziert: ohne Invertierung nur ein Rahmen).
set -euo pipefail
app_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
: "${OPOLUA_DIR:?Set OPOLUA_DIR to your OpoLua checkout}"
mkdir -p "$app_dir/dist"
(
  cd "$app_dir/icon"
  lua "$app_dir/../tools/make_mbm.lua" "$OPOLUA_DIR" PsiVault.mbm --invert-masks \
    icon_24x24_16g.bmp icon_24x24_mask.bmp \
    icon_32x32_16g.bmp icon_32x32_mask.bmp \
    icon_48x48_16g.bmp icon_48x48_mask.bmp >/dev/null
)
cd "$app_dir/src"
lua "$OPOLUA_DIR/bin/compile.lua" --aif main.opl "$app_dir/dist/PsiVault.app"
