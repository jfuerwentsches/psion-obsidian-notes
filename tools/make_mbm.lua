-- Build an EPOC MBM from Windows BMPs (4-bpp indexed grayscale icons, 1-bpp masks)
-- using OpoLua's mbm.makeMbm. No BMCONV needed.
-- Usage: lua tools/make_mbm.lua /path/to/opolua out.mbm [--invert-masks] icon.bmp mask.bmp [icon.bmp mask.bmp ...]
local opolua, out = assert(arg[1]), assert(arg[2])
package.path = opolua .. "/core/src/?.lua"
local hostio, hostos = io, os
require("init")
_G.io, _G.os = hostio, hostos
local mbm = require("mbm")

local invertMasks = false
local files = {}
for i = 3, #arg do
    if arg[i] == "--invert-masks" then invertMasks = true else table.insert(files, arg[i]) end
end
assert(#files % 2 == 0 and #files > 0, "need icon/mask pairs")

local function readBmp(path)
    local f = assert(io.open(path, "rb"))
    local d = f:read("a")
    f:close()
    assert(d:sub(1, 2) == "BM", path .. ": not a BMP")
    local off = string.unpack("<I4", d, 11)
    local hs = string.unpack("<I4", d, 15)
    local w, h, _, bpp = string.unpack("<i4i4I2I2", d, 19)
    local ncol = string.unpack("<I4", d, 47)
    if ncol == 0 then ncol = 1 << bpp end
    local pal = {}
    for i = 0, ncol - 1 do
        local b, g, r = string.unpack("<BBB", d, 15 + hs + 4 * i)
        pal[i] = math.floor((r + g + b) / 3 + 0.5)
    end
    local topDown = h < 0
    h = math.abs(h)
    local stride = ((w * bpp + 31) // 32) * 4
    local rows = {}
    for y = 0, h - 1 do
        local base = off + y * stride
        local px = {}
        for x = 0, w - 1 do
            local v
            if bpp == 4 then
                local byte = d:byte(1 + base + x // 2)
                v = (x % 2 == 0) and (byte >> 4) or (byte & 15)
            elseif bpp == 1 then
                v = (d:byte(1 + base + x // 8) >> (7 - x % 8)) & 1
            elseif bpp == 8 then
                v = d:byte(1 + base + x)
            else
                error(path .. ": unsupported bpp " .. bpp)
            end
            px[x + 1] = pal[v]
        end
        rows[topDown and (y + 1) or (h - y)] = px
    end
    return w, h, bpp, rows
end

local bitmaps = {}
for i = 1, #files, 2 do
    for j = 0, 1 do
        local path = files[i + j]
        local w, h, bpp, rows = readBmp(path)
        local isMask = (j == 1)
        local bytes = {}
        for y = 1, h do
            for x = 1, w do
                local g = rows[y][x]
                if isMask and invertMasks then g = 255 - g end
                bytes[#bytes + 1] = string.char(g)
            end
        end
        table.insert(bitmaps, {
            width = w, height = h,
            mode = isMask and KColorgCreate2GrayMode or KColorgCreate16GrayMode,
            normalizedImgData = table.concat(bytes),
        })
        io.stderr:write(string.format("%s: %dx%d %d-bpp -> %s\n", path, w, h, bpp, isMask and "mask (2 gray)" or "icon (16 gray)"))
    end
end
local data = mbm.makeMbm(KUidMultiBitmapFileImage, bitmaps)
local f = assert(io.open(out, "wb"))
f:write(data)
f:close()
print(string.format("wrote %s (%d bytes, %d bitmaps)", out, #data, #bitmaps))
