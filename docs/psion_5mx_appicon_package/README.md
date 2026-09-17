# Psion Series 5mx application icon package

This package contains a Series 5mx / EPOC-ready icon set derived from the supplied crystal logo and visually adapted to the classic EPOC icon style.

## Contents

- `icons/icon_24x24_16g.bmp` + mask
- `icons/icon_32x32_16g.bmp` + mask
- `icons/icon_48x48_16g.bmp` + mask
- `preview/` enlarged nearest-neighbour previews
- `bmconv.cmd` input for Psion/Symbian BMCONV
- `build_mbm.bat` one-command Windows build/verification
- `APP_INTEGRATION.OPL.txt` integration snippet
- `manifest.json` machine-readable handoff metadata

## Bitmap format
The icon BMPs are genuine Windows 4-bpp indexed grayscale bitmaps (16 entries). Masks are 1-bpp BMPs. Order in the MBM is icon/mask for 24, 32 and 48 px.

## Current PsiVault build (Linux)

PsiVault builds its MBM with OpoLua through `tools/make_mbm.lua`; BMCONV is not
required. From the repository root:

```sh
OPOLUA_DIR=/path/to/opolua bash app/build.sh
```

The build uses the copies in `app/icon/`, creates `app/icon/PsiVault.mbm`, and
embeds it in `app/dist/PsiVault.aif`. Masks are inverted during conversion:
on the device, black mask pixels expose the icon. Keep this inversion when
using the source masks supplied here. See the [app README](../../app/README.md).

## Alternative SDK build: appicon.mbm

The original Windows SDK build helpers are retained as an alternative. Their
output `appicon.mbm` is separate from the MBM used by the current PsiVault build.

On a machine with the SDK:

    build_mbm.bat

Or manually:

    bmconv bmconv.cmd
    bmconv /v appicon.mbm

Expected result: six bitmaps in this order: 24 icon, 24 mask, 32 icon, 32 mask, 48 icon, 48 mask.

## Integration reference

`APP_INTEGRATION.OPL.txt` and the SDK scripts are generic examples from the
original icon handoff. For the actual PsiVault integration, use `app/build.sh`
and `app/src/main.opl` in this repository.
