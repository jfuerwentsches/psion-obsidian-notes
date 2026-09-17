from pathlib import PurePosixPath

import pytest

from psionsync.sync import fsmap
from psionsync.sync.fsmap import (UnmappablePath, decode_content, device_to_vault, encode_content,
                                  is_synced_path, restore_unicode, transliterate, vault_to_device)


def test_only_md_outside_dot_dirs_is_synced():
    assert is_synced_path("Willkommen.md")
    assert is_synced_path("Entwürfe/Gemüse-Lasagne.md")
    assert not is_synced_path(".obsidian/app.json")
    assert not is_synced_path(".trash/alt.md")
    assert not is_synced_path("Bilder/foto.png")
    assert not is_synced_path("Ordner/.versteckt.md")


def test_vault_to_device_and_back():
    dev = vault_to_device(PurePosixPath("Entwürfe/Gemüse-Lasagne.md"))
    assert dev == "C:\\Vault\\Entwürfe\\Gemüse-Lasagne.md"
    assert device_to_vault(dev) == PurePosixPath("Entwürfe/Gemüse-Lasagne.md")
    assert device_to_vault("c:\\vault\\a.md") == PurePosixPath("a.md")


@pytest.mark.parametrize("name", ["Was ist das?.md", "a*b.md", "x|y.md", 'q"q.md', "<a>.md", "c:d.md"])
def test_forbidden_characters_rejected(name):
    with pytest.raises(UnmappablePath):
        vault_to_device(name)


def test_allowed_special_characters():
    dev = vault_to_device("Musik-Player (Spotify) & Co, ¥ – Test.md")
    assert dev.endswith("Musik-Player (Spotify) & Co, ¥ – Test.md")


def test_non_cp1252_name_rejected():
    with pytest.raises(UnmappablePath, match="CP1252"):
        vault_to_device("Notiz → Ziel.md")


def test_too_long_path_rejected():
    with pytest.raises(UnmappablePath, match="zu lang"):
        vault_to_device("a" * 200 + "/" + "b" * 60 + ".md")


def test_absolute_and_dotdot_rejected():
    with pytest.raises(UnmappablePath):
        vault_to_device("/etc/passwd.md")
    with pytest.raises(UnmappablePath):
        vault_to_device("../x.md")


def test_device_path_outside_root_rejected():
    with pytest.raises(UnmappablePath):
        device_to_vault("C:\\System\\x.md")


def test_transliteration_table():
    assert transliterate("A → B ↔ C") == "A -> B <-> C"
    assert transliterate("├── src\n│   └── x\n─") == "+-- src\n|   +-- x\n-"
    assert transliterate("✅ ok ✓ ❌ ⚠ ≥ ∙ ō") == "[x] ok [x] [ ] (!) >= * o"
    assert transliterate("a\u200bb 1\ufe0f\u20e3") == "ab 1"
    assert transliterate("ä ö ü ß € „x“") == "ä ö ü ß € „x“"
    assert transliterate("日本") == "??"


def test_encode_decode_roundtrip_for_cp1252_text():
    text = "# Titel\nä ö ü ß €\n"
    data = encode_content(text)
    assert data == "# Titel\r\nä ö ü ß €\r\n".encode("cp1252")
    assert decode_content(data) == text


def test_encode_normalizes_existing_crlf():
    assert encode_content("a\r\nb\n") == b"a\r\nb\r\n"


def test_encode_transliterates():
    assert encode_content("A → B\n") == b"A -> B\r\n"


def test_restore_unicode_only_for_unchanged_lines():
    snapshot = "# Plan\n- A → B\n- ✅ fertig\n- gleich\n"
    pulled = "# Plan\n- A -> B\n- [x] fertig, ergänzt\n- gleich\n- neu\n"
    assert restore_unicode(pulled, snapshot) == "# Plan\n- A → B\n- [x] fertig, ergänzt\n- gleich\n- neu\n"


def test_restore_unicode_survives_inserted_and_removed_lines():
    snapshot = "x\n- A → B\ny\n- C ✅\n"
    pulled = "neu oben\n- C [x]\n- A -> B\n"
    assert restore_unicode(pulled, snapshot) == "neu oben\n- C ✅\n- A → B\n"


def test_restore_unicode_ambiguous_mapping_is_left_alone():
    # Zwei verschiedene Originale mit gleicher Transliteration -> nicht raten.
    snapshot = "- ✅ ok\n- ✓ ok\n"
    pulled = "- [x] ok\n"
    assert restore_unicode(pulled, snapshot) == "- [x] ok\n"


def test_restore_unicode_identical_duplicates_are_fine():
    snapshot = "- ✅ ok\n- ✅ ok\n"
    assert restore_unicode("- [x] ok\n- [x] ok\n", snapshot) == snapshot
    # An extra matching line may be newly written ASCII: don't guess which one.
    extra = "- [x] ok\n- [x] ok\n- [x] ok\n"
    assert restore_unicode(extra, snapshot) == extra


def test_restore_preserves_mixed_ascii_unicode_originals():
    snapshot = "→\n->\n"
    assert restore_unicode("->\n->\n", snapshot) == snapshot
    # With edits, identical projections cannot be uniquely attributed.
    edited = "->\n->\nnew line\n"
    assert restore_unicode(edited, snapshot) == edited


def test_restore_is_idempotent_with_encode():
    snapshot = "├── src\n│   └── main.opl\n"
    pulled = decode_content(encode_content(snapshot))
    restored = restore_unicode(pulled, snapshot)
    assert restored == snapshot
    assert encode_content(restored) == encode_content(snapshot)


def test_table_only_contains_non_cp1252_chars():
    for ch in fsmap.TRANSLIT:
        with pytest.raises(UnicodeEncodeError):
            ch.encode("cp1252")
