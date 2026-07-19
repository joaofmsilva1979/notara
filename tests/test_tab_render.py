from pipeline.chord_detection import ChordSegment
from pipeline.key_detection import KeyEstimate
from pipeline.tab_render import render_tab
from pipeline.tuning import DROP_D, STANDARD_E_A_D_G_B_E, find_tuning


def _bar(index, start, end, label="Em"):
    return ChordSegment(bar_index=index, start=start, end=end, label=label)


def test_header_reports_selected_tuning_name():
    bars = [_bar(0, 0.0, 2.0)]
    key = KeyEstimate(tonic="E", mode="minor", correlation=0.9)
    text = render_tab(bars, [], key, 120.0, "song.wav", find_tuning(STANDARD_E_A_D_G_B_E))
    assert "# Tuning: Standard EADGBE" in text


def test_string_row_labels_follow_the_tuning():
    bars = [_bar(0, 0.0, 2.0)]
    key = KeyEstimate(tonic="D", mode="major", correlation=0.9)
    text = render_tab(bars, [], key, 120.0, "song.wav", find_tuning(DROP_D))
    lines = text.splitlines()
    assert any(line.startswith("D|") for line in lines)  # lowest string relabeled from E to D
    assert any(line.startswith("e|") for line in lines)  # highest string unchanged
