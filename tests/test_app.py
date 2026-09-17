"""Execute freshly compiled OPL against disposable files, never the real device.

Set OPOLUA_DIR to a checkout of the pinned compiler/runtime (see docs/testing.md).
CI sets REQUIRE_OPL_TESTS=1 so a missing runtime cannot silently skip this suite.
"""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from psionsync.sync.fsmap import encode_content

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def opl_build(tmp_path_factory):
    opolua = Path(os.environ.get("OPOLUA_DIR", "/tmp/psivault-opolua")).resolve()
    lua = shutil.which(os.environ.get("LUA", "lua"))
    if not lua or not (opolua / "bin/compile.lua").is_file():
        if os.environ.get("REQUIRE_OPL_TESTS") == "1":
            pytest.fail("OPL tests require Lua and OPOLUA_DIR")
        pytest.skip("Lua/OpoLua unavailable; set OPOLUA_DIR to enable OPL tests")
    dist = tmp_path_factory.mktemp("opl-build")
    result = subprocess.run(
        [lua, str(opolua / "bin/compile.lua"), "--aif", "main.opl", str(dist / "PsiVault.app")],
        cwd=ROOT / "app/src", capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return lua, opolua, dist


@pytest.fixture
def app_env(tmp_path, opl_build):
    vault = tmp_path / "vault"
    vault.mkdir()
    appdir = tmp_path / "app"
    appdir.mkdir()

    def run(doc=None, **options):
        lua, opolua, dist = opl_build
        command = [lua, str(ROOT / "tools/smoke_app.lua"), str(opolua), str(dist), str(vault)]
        if doc:
            command.append("C:\\Vault\\" + doc)
        env = {k: v for k, v in os.environ.items() if not k.startswith("SMOKE_")}
        env.update(SMOKE_APPDIR=str(appdir), **options)
        result = subprocess.run(command, capture_output=True, env=env, timeout=20)
        output = (result.stdout + result.stderr).decode("cp1252", errors="replace")
        assert result.returncode == 0, output
        assert "PASS:" in output
        return output

    return vault, appdir, run


def test_app_browser_links_and_umlauts(app_env):
    vault, _, run = app_env
    for source in (ROOT / "tests/fixtures/vault").rglob("*.md"):
        if "?" in source.name:
            continue
        target = vault / source.relative_to(ROOT / "tests/fixtures/vault")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(encode_content(source.read_text()))
    run()


@pytest.mark.parametrize("length", [255, 256, 300, 1024])
@pytest.mark.parametrize("closing", [True, False])
def test_app_long_frontmatter_terminates(app_env, length, closing):
    vault, _, run = app_env
    data = b"---\r\n" + b"a" * length
    if closing:
        data += b"\r\n---\r\nVISIBLE-BODY\r\n"
    (vault / "Long.md").write_bytes(data)
    run("Long.md", SMOKE_EXPECT_TEXT="VISIBLE-BODY" if closing else "[Frontmatter]")
    assert (vault / "Long.md").read_bytes() == data


def test_app_reuses_search_index_and_rebuilds_after_sync(app_env):
    vault, appdir, run = app_env
    (vault / "Recipe.md").write_bytes(b"Lasagne recipe\r\n")
    (vault / "_psionsync.gen").write_bytes(b"12")
    run(SMOKE_FLOW="search_twice", SMOKE_EXPECT_INDEX_WRITES="1", SMOKE_EXPECT_TEXT="Lasagne recipe")
    first = (appdir / "search.idx").read_bytes()
    assert first.startswith(b"PSIVAULT-IDX 1 12\r\n")
    run(SMOKE_FLOW="search_twice", SMOKE_EXPECT_INDEX_WRITES="0", SMOKE_EXPECT_TEXT="Lasagne recipe")
    assert (appdir / "search.idx").read_bytes() == first
    (vault / "Recipe.md").write_bytes(b"Lasagne changed\r\n")
    (vault / "_psionsync.gen").write_bytes(b"13")
    run(SMOKE_FLOW="search_twice", SMOKE_EXPECT_INDEX_WRITES="1", SMOKE_EXPECT_TEXT="Lasagne changed")
    assert (appdir / "search.idx").read_bytes().startswith(b"PSIVAULT-IDX 1 13\r\n")


def test_app_new_note_writes_expected_file(app_env):
    vault, _, run = app_env
    run(SMOKE_FLOW="new")
    assert (vault / "Smoke Test.md").read_bytes() == b"# Smoke Test\r\n\r\n"


def test_app_delete_removes_only_selected_note(app_env):
    vault, _, run = app_env
    (vault / "A.md").write_bytes(b"keep\r\n")
    (vault / "Z.md").write_bytes(b"delete\r\n")
    run(SMOKE_FLOW="delete")
    assert not (vault / "Z.md").exists()
    assert (vault / "A.md").read_bytes() == b"keep\r\n"


@pytest.mark.parametrize("large", [False, True])
def test_app_editor_preserves_surrounding_content(app_env, large):
    vault, _, run = app_env
    original = b"unchanged line\r\n" * (2500 if large else 3)
    (vault / "Edit.md").write_bytes(original)
    run("Edit.md", SMOKE_EDIT="2" if large else "0")
    edited = (vault / "Edit.md").read_bytes()
    assert edited.count(b" smoke") == 1
    assert edited.replace(b" smoke", b"", 1) == original
    assert not list(vault.glob("*.bak"))
    assert not list(vault.glob("*.tmp"))


def test_smoke_script_rejects_exhausted_input(app_env):
    _, _, run = app_env
    with pytest.raises(AssertionError, match="key script exhausted"):
        run(SMOKE_FLOW="exhausted")
