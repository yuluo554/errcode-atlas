"""编目装载层：fail-closed 与摘要口径。

被测对象 = ``catalog.load()`` 与 ``catalog.build_indexes()``。
每条 assert 对应 ``plan/04`` §2.1 / §3.1 的一条纪律。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from errcode_atlas import catalog as catalog_mod
from errcode_atlas import contract


def _file_source(**overrides):
    base = {"kind": "file", "file": "include/uapi/x.h", "line": 12, "repo": "o/r", "ref": "abc"}
    base.update(overrides)
    return base


def test_loader_rejects_absolute_source_path(tmp_path, write_catalog):
    payload = {"platforms": {"linux": [_entry(_file_source(file="/etc/x.h"))]}}
    path = write_catalog(payload)
    with pytest.raises(catalog_mod.CatalogError, match="相对路径"):
        catalog_mod.load(path, tmp_path / "missing.manifest.json")


def test_loader_rejects_missing_line(tmp_path, write_catalog):
    source = _file_source()
    del source["line"]
    path = write_catalog({"platforms": {"linux": [_entry(source)]}})
    with pytest.raises(catalog_mod.CatalogError, match="line"):
        catalog_mod.load(path, tmp_path / "missing.manifest.json")


def test_loader_rejects_unknown_source_kind(tmp_path, write_catalog):
    path = write_catalog(
        {"platforms": {"linux": [_entry({"kind": "blog", "url": "https://x/y"})]}}
    )
    with pytest.raises(catalog_mod.CatalogError, match="source.kind"):
        catalog_mod.load(path, tmp_path / "missing.manifest.json")


def test_runtime_source_cannot_claim_hard_strength(tmp_path, write_catalog):
    """`runtime` 出处永远拿不到 `hard`（强度不可升级，plan/04 §2.2）。"""
    entry = _entry({"kind": "runtime", "runtime": "node", "program_version": "v1", "verified_at": "2026-11-01"})
    path = write_catalog({"platforms": {"win32-node": [entry]}})
    loaded = catalog_mod.load(path, tmp_path / "missing.manifest.json")
    assert loaded.entries[0].strength == contract.STRENGTH_DIFF
    assert loaded.entries[0].strength != contract.STRENGTH_HARD


def test_duplicate_name_with_different_value_is_hard_error(tmp_path, write_catalog):
    a = _entry(_file_source(), name="EAGAIN", value=11)
    b = _entry(_file_source(), name="EAGAIN", value=12)
    path = write_catalog({"platforms": {"linux": [a, b]}})
    with pytest.raises(catalog_mod.CatalogError, match="重复定义"):
        catalog_mod.load(path, tmp_path / "missing.manifest.json")


def test_duplicate_value_with_distinct_names_is_legal(tmp_path, write_catalog):
    """同值多名是 `AMBIGUOUS-SAME-PLATFORM` 的素材，**合法**。"""
    a = _entry(_file_source(), name="SIGABRT", value=6, domain="signal")
    b = _entry(_file_source(), name="SIGIOT", value=6, domain="signal")
    path = write_catalog({"platforms": {"linux": [a, b]}})
    loaded = catalog_mod.load(path, tmp_path / "missing.manifest.json")
    assert loaded.names_at("linux", "signal", 6) == ("SIGABRT", "SIGIOT")


def test_missing_catalog_raises_not_returns_empty(tmp_path):
    with pytest.raises(catalog_mod.CatalogError, match="编目不存在"):
        catalog_mod.load(tmp_path / "nope.json", tmp_path / "nope.manifest.json")


def test_unknown_platform_in_catalog_is_rejected(tmp_path, write_catalog):
    path = write_catalog({"platforms": {"windows": []}})
    with pytest.raises(catalog_mod.CatalogError, match="平台"):
        catalog_mod.load(path, tmp_path / "missing.manifest.json")


# ── 摘要口径（plan/04 §3.1）────────────────────────────────────────────────
def test_digest_is_newline_normalized() -> None:
    lf = '{"a":1}\n'
    crlf = '{"a":1}\r\n'
    assert catalog_mod.sha256_of_text(lf) == catalog_mod.sha256_of_text(crlf)


def test_digest_changes_with_content() -> None:
    assert catalog_mod.sha256_of_text('{"a":1}\n') != catalog_mod.sha256_of_text('{"a":2}\n')


def test_manifest_digest_mismatch_is_rejected(tmp_path, write_catalog):
    path = write_catalog({"platforms": {}})
    manifest = tmp_path / "catalog.manifest.json"
    manifest.write_text(json.dumps({"sha256": "0" * 64}), encoding="utf-8")
    with pytest.raises(catalog_mod.CatalogError, match="摘要不符"):
        catalog_mod.load(path, manifest)


# ── 索引与分母 ─────────────────────────────────────────────────────────────
def test_entry_count_is_derived_not_hardcoded(tmp_path, write_catalog):
    entries = [
        _entry(_file_source(), name="EAGAIN", value=11),
        _entry(_file_source(), name="SIGKILL", value=9, domain="signal"),
    ]
    path = write_catalog({"platforms": {"linux": entries}})
    loaded = catalog_mod.load(path, tmp_path / "missing.manifest.json")
    counts = loaded.entry_count()
    assert counts["errno"] == 1
    assert counts["signal"] == 1
    assert sum(counts.values()) == len(entries)


def test_signal_numbers_come_only_from_catalog(tmp_path, write_catalog):
    entries = [_entry(_file_source(), name="SIGKILL", value=9, domain="signal")]
    path = write_catalog({"platforms": {"linux": entries}})
    loaded = catalog_mod.load(path, tmp_path / "missing.manifest.json")
    assert loaded.signal_numbers("linux") == frozenset({9})
    assert loaded.signal_numbers("macos") == frozenset()


# ── 夹具 ───────────────────────────────────────────────────────────────────
def _entry(source, name="EAGAIN", value=11, domain="errno"):
    return {
        "name": name,
        "domain": domain,
        "value": value,
        "source": source,
        "description_zh": "t",
        "posix_ref": "<none>",
    }