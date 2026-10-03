from pathlib import Path

import nbformat

from tradingrag.ingest.chunk import chunk_markdown, chunk_notebook


def test_chunk_markdown_splits_on_headers_and_tags_provenance(tmp_path: Path) -> None:
    root = tmp_path / "myproj"
    root.mkdir()
    md = root / "README.md"
    md.write_text(
        "intro line\n\n## Scope and limits\nnot tested on live data\n\n## Results\nSharpe 1.2\n"
    )

    chunks = chunk_markdown(md, [root])

    assert [c.section for c in chunks] == ["(preamble)", "Scope and limits", "Results"]
    assert chunks[0].text == "intro line"
    assert "Sharpe 1.2" in chunks[2].text
    assert all(c.source_repo == "myproj" for c in chunks)
    assert all(c.source_path == "README.md" for c in chunks)


def test_chunk_markdown_drops_empty_sections(tmp_path: Path) -> None:
    root = tmp_path / "myproj"
    root.mkdir()
    md = root / "README.md"
    md.write_text("## Empty heading\n\n## Real heading\ncontent here\n")

    chunks = chunk_markdown(md, [root])

    assert [c.section for c in chunks] == ["Real heading"]


def test_chunk_notebook_one_chunk_per_nonempty_cell(tmp_path: Path) -> None:
    root = tmp_path / "myproj"
    root.mkdir()
    nb_path = root / "notebooks" / "01_demo.ipynb"
    nb_path.parent.mkdir()

    nb = nbformat.v4.new_notebook()
    nb.cells = [
        nbformat.v4.new_markdown_cell("## Setup\nsome text"),
        nbformat.v4.new_code_cell("x = 1"),
        nbformat.v4.new_code_cell(""),  # empty cell should be skipped
    ]
    nbformat.write(nb, nb_path)

    chunks = chunk_notebook(nb_path, [root])

    assert len(chunks) == 2
    assert chunks[0].cell_type == "markdown"
    assert chunks[0].section == "Setup"
    assert chunks[1].cell_type == "code"
    assert chunks[1].section == "Setup"  # inherits most recent markdown heading
    assert chunks[1].cell_index == 1
    assert chunks[0].source_path == "notebooks/01_demo.ipynb"


def test_citation_format(tmp_path: Path) -> None:
    root = tmp_path / "myproj"
    root.mkdir()
    md = root / "README.md"
    md.write_text("## Results\nSharpe 1.2\n")
    chunk = chunk_markdown(md, [root])[0]

    assert chunk.citation() == "myproj/README.md (Results)"


def test_chunk_markdown_ignores_hash_lines_inside_fenced_code_blocks(tmp_path: Path) -> None:
    # Regression test: a `#` comment at column 0 inside a fenced code block
    # must not be misread as a markdown header, which would corrupt the
    # chunk's section/citation with the comment text itself.
    root = tmp_path / "myproj"
    root.mkdir()
    md = root / "README.md"
    md.write_text(
        "## Real heading\n"
        "some prose\n"
        "```bash\n"
        "# comment at column 0, not a markdown header\n"
        "echo hello\n"
        "```\n"
        "more prose under the same real heading\n"
    )

    chunks = chunk_markdown(md, [root])

    assert [c.section for c in chunks] == ["Real heading"]
    assert "comment at column 0" in chunks[0].text  # code block content is preserved
    assert "more prose under the same real heading" in chunks[0].text


def test_chunk_id_does_not_collide_across_repos_with_the_same_filename(tmp_path: Path) -> None:
    # Regression test: two different projects' same-named README.md, each with
    # a section at the same position and same heading text, must not produce
    # the same chunk_id — this collided once before the repo-name prefix was
    # added (see README.md "What running it against real data caught").
    root_a = tmp_path / "project-a"
    root_b = tmp_path / "project-b"
    root_a.mkdir()
    root_b.mkdir()
    (root_a / "README.md").write_text("## Overview\nproject a content\n")
    (root_b / "README.md").write_text("## Overview\nproject b content\n")

    corpus_roots = [root_a, root_b]
    chunk_a = chunk_markdown(root_a / "README.md", corpus_roots)[0]
    chunk_b = chunk_markdown(root_b / "README.md", corpus_roots)[0]

    assert chunk_a.chunk_id != chunk_b.chunk_id
    assert chunk_a.chunk_id.startswith("project-a/")
    assert chunk_b.chunk_id.startswith("project-b/")
