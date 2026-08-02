from pipeline.chord_detection import ChordSegment
from pipeline.key_detection import KeyEstimate
from pipeline.tab_render import render_tab
from pipeline.tuning import BASS_STANDARD_EADG, DROP_D, STANDARD_E_A_D_G_B_E, find_tuning


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


def test_bass_tab_renders_four_string_rows():
    bars = [_bar(0, 0.0, 2.0, "Em")]
    key = KeyEstimate(tonic="E", mode="minor", correlation=0.9)
    bass_tuning = find_tuning(BASS_STANDARD_EADG)
    text = render_tab(bars, [], key, 120.0, "song.wav", bass_tuning)
    lines = text.splitlines()
    string_rows = [l for l in lines if "|" in l and not l.startswith("#")]
    # Should have exactly 4 string rows per line group (not 6)
    assert len(string_rows) == 4
    # Lowest string label should be E (not a sixth string)
    assert any(l.startswith("E|") for l in string_rows)
    # Should NOT have guitar-only strings B or high-e
    assert not any(l.startswith("B|") for l in string_rows)
    assert not any(l.startswith("e|") for l in string_rows)
