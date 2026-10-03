import pytest

from deskagent.tools.get_file import get_file


def test_reads_a_real_allowed_file() -> None:
    result = get_file("pm-bayes-pricer/README.md")

    assert result["path"] == "pm-bayes-pricer/README.md"
    assert "pm-bayes-pricer" in result["content"]
    assert result["size_bytes"] > 0


def test_rejects_a_root_not_in_the_allowlist() -> None:
    with pytest.raises(ValueError, match="not under an allowed root"):
        get_file("oop-codeblocks/python/charts.py")


def test_rejects_path_traversal() -> None:
    with pytest.raises(ValueError, match="path traversal"):
        get_file("pm-bayes-pricer/../../../../etc/passwd")


def test_rejects_a_nonexistent_file() -> None:
    with pytest.raises(ValueError, match="no such file"):
        get_file("pm-bayes-pricer/this-file-does-not-exist.md")


def test_rejects_a_file_over_the_size_cap(tmp_path) -> None:
    from deskagent.config import Settings

    big_root = tmp_path / "pm-bayes-pricer"
    big_root.mkdir()
    big_file = big_root / "big.txt"
    big_file.write_text("x" * 300_000)

    fake_settings = Settings(showcase_root=tmp_path)

    with pytest.raises(ValueError, match="over the"):
        get_file("pm-bayes-pricer/big.txt", settings=fake_settings)
