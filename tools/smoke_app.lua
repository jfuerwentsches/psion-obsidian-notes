-- Headless run of the compiled APP in OpoLua with a scripted key sequence.
-- Usage: lua tools/smoke_app.lua /path/to/opolua /abs/path/to/app/dist /abs/path/to/fake-device/C/Vault [C:\Vault\Note.md]
-- The vault dir must be CP1252/CRLF as on the device (psionsync --fake-device).
-- With a 4th argument the app is started "with a document": it opens that note in
-- the viewer, pages through it (stress test) and only checks for runtime errors.
local opolua, dist, vault, doc = assert(arg[1]), assert(arg[2]), assert(arg[3]), arg[4]
package.path = opolua .. "/core/src/?.lua"
local hostio, hostos = io, os
require("init")
_G.io, _G.os = hostio, hostos
local handler = require("defaultiohandler")
handler.fsmap("C:\\Vault\\", vault .. "/")
handler.fsmap("C:\\Vault", vault)
local appdir = os.getenv("SMOKE_APPDIR") or os.tmpname()
if not os.getenv("SMOKE_APPDIR") then
    os.remove(appdir)
    os.execute('mkdir -p "' .. appdir .. '"')
end
handler.fsmap("C:\\System\\Apps\\PsiVault\\", appdir .. "/")   -- state.txt
-- GETEVENT32 key codes: PgUp 4100, PgDn 4101, End 4099, Ctrl-E 5.
-- Enter, Enter, Tab, Enter, PgDn, Esc, Esc, Esc, Ctrl-E (quit -> STOP)
local keys = { 13, 13, 9, 13, 4101, 27, 27, 27, 5 }
if doc and os.getenv("SMOKE_EDIT") then
    -- Editor round trip: PgDn x N (so a chunk edit starts mid-file), E, then the fake
    -- dialog below appends " smoke" to the editor buffer and presses Speichern; Esc, Ctrl-E.
    keys = {}
    for _ = 1, tonumber(os.getenv("SMOKE_EDIT")) do table.insert(keys, 4101) end
    table.insert(keys, 101)
    table.insert(keys, 27)
    table.insert(keys, 5)
    handler.dialog = function(d)
        for _, item in ipairs(d.items) do
            if item.addr and item.value then
                local value = item.value .. " smoke"
                item.addr:write(string.pack("<i4", #value))
                ;(item.addr + 4):write(value)
                print("fake dialog: " .. d.title .. " (" .. #item.value .. " -> " .. #value .. " bytes)")
                return 115   -- %s = Speichern
            end
        end
        return 27
    end
elseif os.getenv("SMOKE_FLOW") == "search" then
    -- Browser: Ctrl-F (fake dialog enters the term), Enter opens the first hit, Esc, Esc, Ctrl-E
    keys = { 6, 13, 27, 27, 5 }
elseif os.getenv("SMOKE_FLOW") == "search_twice" then
    keys = { 6, 27, 6, 27, 5 }
elseif os.getenv("SMOKE_FLOW") == "exhausted" then
    keys = {} -- negative test: running out of input must fail, not pass
elseif os.getenv("SMOKE_FLOW") == "new" then
    -- Browser: Ctrl-N (fake dialog names the note) -> viewer; Esc; Ctrl-E
    keys = { 14, 27, 5 }
elseif os.getenv("SMOKE_FLOW") == "delete" then
    -- Browser: End (last entry = a file), Ctrl-D (fake dialog confirms), Ctrl-E
    keys = { 4099, 4, 5 }
elseif doc then
    keys = { 43, 43, 4101, 45, 45, 45, 4101, 43, 4099 }   -- zoom in/out (re-layout), End: full layout
    for _ = 1, 60 do table.insert(keys, 4101) end   -- PgDn beyond the end
    for _ = 1, 30 do table.insert(keys, 4100) end   -- PgUp
    table.insert(keys, 9)                 -- Tab: select a link, if any
    table.insert(keys, 27)
    table.insert(keys, 5)
end
local ki = 0
local EXHAUSTED = "key script exhausted"
handler.getch = function()
    ki = ki + 1
    if not keys[ki] then error(EXHAUSTED, 0) end
    return keys[ki]
end
-- GETEVENT32 support: the default handler only knows GET's "getevent".
-- Each key from the script is delivered as a 16-long event array (key code first).
local pendingEvent
local origAsync, origWait = handler.asyncRequest, handler.waitForAnyRequest
handler.asyncRequest = function(name, ...)
    if name == "event" then
        local _, completion = ...
        pendingEvent = completion
    else
        return origAsync(name, ...)
    end
end
handler.waitForAnyRequest = function()
    if pendingEvent then
        local completion = pendingEvent
        pendingEvent = nil
        local ev = { handler.getch() }
        for i = 2, 16 do ev[i] = 0 end
        completion(0, string.pack(string.rep("<i4", 16), table.unpack(ev)))
        return true
    end
    return origWait()
end
handler.testEvent = function() return false end
-- The default handler has no "rename" fsop (needed by the editor's atomic save).
local function hostPath(p)
    if p:sub(1, 9):upper() == "C:\\VAULT\\" then return vault .. "/" .. p:sub(10):gsub("\\", "/") end
    error("no mapping for " .. p)
end
local origFsop = handler.fsop
local traceT0 = os.clock()
local indexWrites = 0
handler.fsop = function(cmd, path, ...)
    if cmd == "write" and path:lower():find("search.idx", 1, true) then indexWrites = indexWrites + 1 end
    if os.getenv("SMOKE_TRACE") then io.stderr:write(string.format("%7.2fs fsop %s %s\n", os.clock() - traceT0, cmd, path)) end
    if cmd == "rename" then
        local dest = ...
        local ok = os.rename(hostPath(path), hostPath(dest))
        return ok and 0 or -33
    end
    return origFsop(cmd, path, ...)
end
if os.getenv("SMOKE_FLOW") then
    handler.dialog = function(d)
        print("fake dialog: " .. d.title)
        for _, item in ipairs(d.items) do
            if item.variable and d.title == "Volltextsuche" then item.variable("lasagne") return 13 end
            if item.variable and d.title:find("Neue Notiz", 1, true) then item.variable("Smoke Test") return 13 end
        end
        if d.title:find("schen?", 1, true) then return 108 end   -- %l = Loeschen
        return 27
    end
end
local displayed = {}
handler.graphicsop = function(cmd)
    if cmd == "loadfont" then
        local widths = {}
        for i = 1, 256 do widths[i] = 7 end
        return { maxwidth = 7, height = 11, ascent = 9, descent = 2, widths = widths }
    end
    return 0
end
handler.draw = function() end
local file = assert(io.open(dist .. "/PsiVault.app", "rb"))
local data = file:read("a")
file:close()
local program = require("opofile").parseOpo(data)
local runtime = require("runtime").newRuntime(handler, program.translatorVersion)
runtime.drawText = function(_, text)
    table.insert(displayed, text)
    if os.getenv("SMOKE_TRACE") then io.stderr:write(string.format("%7.2fs text %s\n", os.clock() - traceT0, text)) end
end
runtime:addModule("C:\\System\\Apps\\PsiVault\\PsiVault.app", program)
if doc then
    runtime:setResource("cmdStr", { "C:\\System\\Apps\\PsiVault\\PsiVault.app", doc, "O" })
end
if os.getenv("SMOKE_HOOK") then
    -- periodic Lua traceback to locate hangs
    debug.sethook(function() io.stderr:write("---- hook ----\n" .. debug.traceback("", 2):sub(1, 1500) .. "\n") end, "", 50000000)
end
local err = runtime:pcallProc("MAIN")
-- STOP surfaces as an error object in pcallProc; anything else is a real failure
if err and not tostring(err):find("KStopErr", 1, true) then
    print("Runtime error: " .. tostring(err))
    print("Displayed so far:\n" .. table.concat(displayed, "\n"))
    os.exit(1)
end
local text = table.concat(displayed, "\n")
assert(ki == #keys, "app stopped before all scripted input was consumed")
if os.getenv("SMOKE_EXPECT_TEXT") then
    assert(text:find(os.getenv("SMOKE_EXPECT_TEXT"), 1, true), "expected content was not displayed")
end
if os.getenv("SMOKE_EXPECT_INDEX_WRITES") then
    assert(indexWrites == tonumber(os.getenv("SMOKE_EXPECT_INDEX_WRITES")),
           "unexpected index rebuild count: " .. indexWrites)
end
if os.getenv("SMOKE_FLOW") then
    if os.getenv("SMOKE_DUMP") then print(text) end
    print("PASS: flow " .. os.getenv("SMOKE_FLOW"))
    os.exit(0)
end
if doc then
    if os.getenv("SMOKE_DUMP") then print(text) end
    print("PASS: " .. doc .. " (" .. #displayed .. " text runs)")
    os.exit(0)
end
local function expect(s)
    assert(text:find(s, 1, true), "missing on screen: " .. s .. "\n--- screen text ---\n" .. text)
end
expect("rfe\\")                                       -- browser shows folder (host dir names are UTF-8, so no umlaut check)
expect("Gem" .. string.char(252) .. "se-Lasagne")      -- heading of opened note
expect("[Frontmatter]")
expect("Zutaten f" .. string.char(252) .. "r 4 Personen")
expect("Willkommen bei PsiVault!")                     -- followed [[Willkommen]] link
print("PASS: browser, viewer, frontmatter, umlauts and wikilink navigation (" .. ki .. " keys)")
