"""Pfad- und Inhaltsabbildung Vault <-> Psion.

Pfade: Relativpfad im Vault (POSIX) <-> ``C:\\Vault\\<Relativpfad>`` mit ``\\``.
Inhalt: UTF-8/LF <-> CP1252/CRLF, Zeichen außerhalb CP1252 werden nach einer
festen Tabelle transliteriert (nie stillschweigend zu ``?``).
"""
from __future__ import annotations

from pathlib import PurePosixPath
from collections import Counter

DEVICE_ROOT = "C:\\Vault"
ENCODING = "cp1252"
# In EPOC-Dateinamen verboten (Phase 0 am Gerät verifiziert).
FORBIDDEN_NAME_CHARS = frozenset('?*|"<>:')
# Am Gerät gemessen: 253 ok, 270 Fehler. Konservativ bleiben.
MAX_DEVICE_PATH = 250

# Version der Tabelle; wird im State abgelegt, damit eine spätere Änderung der
# Tabelle alte Snapshots nicht falsch rekonstruiert.
TRANSLIT_VERSION = 1
TRANSLIT: dict[str, str] = {
    "\u2192": "->",   # →
    "\u2194": "<->",  # ↔
    "\u2500": "-",    # ─
    "\u2502": "|",    # │
    "\u251c": "+",    # ├
    "\u2514": "+",    # └
    "\u2705": "[x]",  # ✅
    "\u2713": "[x]",  # ✓
    "\u274c": "[ ]",  # ❌
    "\u26a0": "(!)",  # ⚠
    "\u2265": ">=",   # ≥
    "\u2264": "<=",   # ≤
    "\u2219": "*",    # ∙
    "\u014d": "o",    # ō
    "\u200b": "",     # Zero-Width Space
    "\ufe0f": "",     # Variation Selector 16
    "\u20e3": "",     # Combining Enclosing Keycap
}


class UnmappablePath(ValueError):
    """Pfad lässt sich nicht auf das Gerät abbilden (Zeichen, Länge, Kodierung)."""


def is_synced_path(rel: PurePosixPath | str) -> bool:
    """Nur ``*.md`` außerhalb von ``.``-Ordnern (``.obsidian``, ``.trash`` …)."""
    rel = PurePosixPath(rel)
    if rel.suffix.lower() != ".md":
        return False
    return not any(part.startswith(".") for part in rel.parts)


def check_name_part(part: str) -> None:
    bad = sorted(set(part) & FORBIDDEN_NAME_CHARS)
    if bad:
        raise UnmappablePath(f"verbotene Zeichen {''.join(bad)!r} in {part!r}")
    try:
        part.encode(ENCODING)
    except UnicodeEncodeError as exc:
        raise UnmappablePath(f"nicht CP1252-kodierbar: {part!r} ({exc.object[exc.start:exc.end]!r})") from None
    if part in ("", ".", ".."):
        raise UnmappablePath(f"ungültiger Pfadbestandteil {part!r}")


def vault_to_device(rel: PurePosixPath | str, root: str = DEVICE_ROOT) -> str:
    rel = PurePosixPath(rel)
    if rel.is_absolute():
        raise UnmappablePath(f"absoluter Pfad {rel!s}")
    for part in rel.parts:
        check_name_part(part)
    device = root + "\\" + "\\".join(rel.parts)
    if len(device) > MAX_DEVICE_PATH:
        raise UnmappablePath(f"Pfad zu lang ({len(device)} > {MAX_DEVICE_PATH}): {device}")
    return device


def device_to_vault(path: str, root: str = DEVICE_ROOT) -> PurePosixPath:
    prefix = root.rstrip("\\") + "\\"
    if not path.upper().startswith(prefix.upper()):
        raise UnmappablePath(f"{path!r} liegt nicht unter {root!r}")
    return PurePosixPath(*path[len(prefix):].split("\\"))


def transliterate(text: str) -> str:
    """Ersetzt Zeichen außerhalb CP1252 nach ``TRANSLIT``; unbekannte werden ``?``."""
    out: list[str] = []
    for ch in text:
        if ch in TRANSLIT:
            out.append(TRANSLIT[ch])
            continue
        try:
            ch.encode(ENCODING)
        except UnicodeEncodeError:
            out.append("?")
        else:
            out.append(ch)
    return "".join(out)


def needs_transliteration(text: str) -> bool:
    return transliterate(text) != text


def encode_content(text: str) -> bytes:
    """Vault-Text -> Gerätebytes (Transliteration, LF -> CRLF, CP1252)."""
    text = text.replace("\r\n", "\n")
    text = transliterate(text).replace("\n", "\r\n")
    return text.encode(ENCODING)


def decode_content(data: bytes) -> str:
    """Gerätebytes -> Text (CP1252 -> str, CRLF -> LF). Undefinierte Bytes bleiben als U+FFFD."""
    return data.decode(ENCODING, errors="replace").replace("\r\n", "\n")


def restore_unicode(pulled: str, snapshot: str) -> str:
    """Stellt transliterierte Zeilen aus ``snapshot`` (letzter Sync-Stand, Unicode) wieder her.

    Eine Zeile aus ``pulled`` wird nur ersetzt, wenn sie exakt der Transliteration
    einer Snapshot-Zeile entspricht und diese Zuordnung eindeutig ist. Geänderte,
    neue oder mehrdeutige Zeilen bleiben transliteriert.
    """
    candidates: dict[str, set[str]] = {}
    original_lines = snapshot.replace("\r\n", "\n").split("\n")
    projected = [transliterate(line) for line in original_lines]
    if pulled.split("\n") == projected:
        return "\n".join(original_lines)
    for line in original_lines:
        translit = transliterate(line)
        # Plain ASCII originals also make a projection ambiguous.
        candidates.setdefault(translit, set()).add(line)
    if not candidates:
        return pulled
    out = []
    before = Counter(projected)
    after = Counter(pulled.split("\n"))
    for line in pulled.split("\n"):
        originals = candidates.get(line)
        if originals and len(originals) == 1 and after[line] <= before[line]:
            out.append(next(iter(originals)))
        else:
            out.append(line)
    return "\n".join(out)
