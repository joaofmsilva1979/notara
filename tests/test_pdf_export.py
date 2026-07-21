from pipeline.pdf_export import _blocks_per_page, _split_into_blocks


def test_blocks_per_page_returns_a_positive_count_at_8pt():
    assert _blocks_per_page(8) >= 1


def test_blocks_per_page_returns_a_positive_count_at_7pt():
    assert _blocks_per_page(7) >= 1


def test_blocks_per_page_fits_at_least_as_many_blocks_at_the_smaller_font():
    # Smaller font -> smaller line height -> more lines fit -> at least as
    # many whole 8-line blocks fit per page.
    assert _blocks_per_page(7) >= _blocks_per_page(8)


def test_blocks_per_page_exact_values_for_a4_with_36pt_margins():
    # Pins down the actual arithmetic (hand-verified: PAGE_HEIGHT=841.8898,
    # line_height=9.2 at 8pt / 8.05 at 7pt, 5 header line-heights + 2*36pt
    # margins reserved) so a stub that always returns a fixed positive
    # number can't silently pass the two tests above.
    assert _blocks_per_page(8) == 9
    assert _blocks_per_page(7) == 11


def test_split_into_blocks_groups_lines_into_chunks_of_eight():
    lines = [f"line{i}" for i in range(16)]
    blocks = _split_into_blocks(lines)
    assert len(blocks) == 2
    assert blocks[0] == lines[:8]
    assert blocks[1] == lines[8:]


def test_split_into_blocks_handles_empty_input():
    assert _split_into_blocks([]) == []
