from datetime import datetime

import pytest

from psionsync.transport.base import TransportError
from psionsync.transport.plp import PlpTransport, parse_gtime, parse_ls


def test_parse_ls_files_dirs_and_odd_names():
    out = ("-rw--a----         79 Thu Sep 17 19:12:42 2026 Willkommen.md\n"
           "drw-------          0 Thu Sep 17 19:13:32 2026 Entwürfe\n"
           "-rw--a----          7 Thu Sep 17 19:18:14 2026  leading space.md\n"
           "-rw--a----          7 Fri Jan  1 14:10:00 1999 Musik-Player (Spotify) & Co, Test.md\n")
    entries = parse_ls(out, "C:\\Vault")
    assert [e.name for e in entries] == ["Willkommen.md", "Entwürfe", " leading space.md",
                                         "Musik-Player (Spotify) & Co, Test.md"]
    assert entries[0].path == "C:\\Vault\\Willkommen.md"
    assert entries[0].size == 79 and not entries[0].is_dir
    assert entries[0].mtime == datetime(2026, 9, 17, 19, 12, 42)
    assert entries[1].is_dir and entries[1].path == "C:\\Vault\\Entwürfe"
    assert entries[3].mtime == datetime(1999, 1, 1, 14, 10)


def test_parse_ls_rejects_garbage():
    with pytest.raises(TransportError):
        parse_ls("Error: no such directory\n", "C:\\X")


def test_parse_gtime():
    assert parse_gtime("Thu Sep 17 19:18:16 2026(00e33964:07576600)\n") == datetime(2026, 9, 17, 19, 18, 16)


def test_relative_paths():
    t = PlpTransport()
    assert t.relative("C:\\Vault\\a\\b.md") == "Vault\\a\\b.md"
    assert t.relative("c:\\Vault") == "Vault"
    with pytest.raises(TransportError):
        t.relative("D:\\x")
    with pytest.raises(TransportError):
        t.relative("C:\\")
