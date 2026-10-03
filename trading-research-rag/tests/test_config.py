from pathlib import Path

import pytest

from tradingrag.config import _resolve_edwardcrook_root


def _make_showcase_dirs(base: Path) -> None:
    (base / "crypto-cointegration-signal").mkdir()
    (base / "pm-bayes-pricer").mkdir()


def test_resolves_direct_sibling_layout_first(tmp_path: Path) -> None:
    # published layout: trading-research-rag lives directly inside edwardcrook/
    edwardcrook = tmp_path / "edwardcrook"
    edwardcrook.mkdir()
    _make_showcase_dirs(edwardcrook)
    project_root = edwardcrook / "trading-research-rag"
    project_root.mkdir()

    assert _resolve_edwardcrook_root(project_root) == edwardcrook


def test_falls_back_to_nested_dev_layout(tmp_path: Path) -> None:
    # dev layout: trading-research-rag lives in the outer portfolio folder,
    # siblings are nested one level down inside edwardcrook/
    outer = tmp_path / "Personal Portfolio"
    edwardcrook = outer / "edwardcrook"
    edwardcrook.mkdir(parents=True)
    _make_showcase_dirs(edwardcrook)
    project_root = outer / "trading-research-rag"
    project_root.mkdir()

    assert _resolve_edwardcrook_root(project_root) == edwardcrook


def test_raises_clearly_when_neither_layout_is_found(tmp_path: Path) -> None:
    project_root = tmp_path / "trading-research-rag"
    project_root.mkdir()

    with pytest.raises(FileNotFoundError, match="crypto-cointegration-signal"):
        _resolve_edwardcrook_root(project_root)
