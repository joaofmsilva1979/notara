import numpy as np
import pytest

from pipeline.chord_detection import _bass_root_pitch_class, _TEMPLATES, _best_chord, _score_label


def test_bass_root_pitch_class_detects_a_clear_single_note():
    # All energy in bin 9 (A) -- an unambiguous, sustained bass note
    vec = np.zeros(12)
    vec[9] = 1.0
    assert _bass_root_pitch_class(vec) == 9


def test_bass_root_pitch_class_returns_none_for_a_near_uniform_vector():
    # Energy spread evenly across all 12 bins -- no single note dominates
    vec = np.full(12, 1.0 / 12)
    assert _bass_root_pitch_class(vec) is None


def test_bass_root_pitch_class_returns_none_for_silence():
    vec = np.zeros(12)
    assert _bass_root_pitch_class(vec) is None


def test_score_label_scores_a_perfect_match_as_one():
    c_template = next(t for root, label, t in _TEMPLATES if label == "C")
    assert _score_label(c_template, "C") == pytest.approx(1.0)


def test_score_label_raises_on_unknown_label():
    with pytest.raises(ValueError):
        _score_label(np.zeros(12), "Not A Real Chord")


def test_best_chord_with_forced_root_only_searches_that_root():
    # A vector shaped exactly like a C major chord (root 0) -- with no
    # constraint this would clearly win as "C". Forcing root=7 (G) must
    # restrict the search to G's 5 templates regardless of fit quality.
    c_major_vec = np.zeros(12)
    c_major_vec[0] = 1.0   # C
    c_major_vec[4] = 0.8   # E
    c_major_vec[7] = 1.0   # G
    label, _score = _best_chord(c_major_vec, forced_root=7)
    assert label.startswith("G")  # G, Gm, G7, Gmaj7, or Gm7 -- never C-rooted


def test_best_chord_with_forced_root_zero_is_not_treated_as_falsy():
    # forced_root=0 is pitch class C -- the one value where a careless
    # `if forced_root:` (instead of `if forced_root is not None:`) would
    # silently behave as if no root were forced. Use a vector shaped like a
    # G major chord (root 7) to make sure forcing root=0 actually restricts
    # the search to C's 5 templates instead of the vector's "natural" winner.
    g_major_vec = np.zeros(12)
    g_major_vec[7] = 1.0   # G
    g_major_vec[11] = 0.8  # B
    g_major_vec[2] = 1.0   # D
    label, _score = _best_chord(g_major_vec, forced_root=0)
    assert label.startswith("C")  # C, Cm, C7, Cmaj7, or Cm7 -- never G-rooted


def test_best_chord_diatonic_bonus_does_not_override_a_clear_winner():
    # A pure, unambiguous F# major shape (root 6). "F#" isn't in this
    # (deliberately non-musical) diatonic set, but the bonus (0.03) is far
    # too small to make any bonused template beat F#'s own ~1.0 self-match.
    fsharp_template = next(t for root, label, t in _TEMPLATES if label == "F#")
    label, _score = _best_chord(fsharp_template, diatonic_roots={0, 2, 4, 5, 7, 9, 11})
    assert label == "F#"


def test_best_chord_diatonic_bonus_breaks_a_genuine_tie_against_a_non_diatonic_root():
    # For any two unit template vectors A, B: dot(A+B, A) == dot(A+B, B), by
    # symmetry of the dot product. So scoring their sum against "C" and
    # against "Am" always gives an EXACT tie on raw score, regardless of
    # which two templates are chosen -- this doesn't depend on knowing the
    # full 60-template landscape.
    c_template = next(t for root, label, t in _TEMPLATES if label == "C")
    am_template = next(t for root, label, t in _TEMPLATES if label == "Am")
    tied_vec = c_template + am_template
    assert _score_label(tied_vec, "C") == pytest.approx(_score_label(tied_vec, "Am"))

    # With Am's root (9) diatonic and C's root (0) not, Am's score gets the
    # bonus while C's doesn't -- so Am now strictly beats C. Since they were
    # exactly tied before the bonus, C can never be the overall winner here
    # (something else might beat Am too, but never C, which Am now
    # strictly dominates).
    label, _score = _best_chord(tied_vec, diatonic_roots={9})
    assert label != "C"


from pipeline.chord_detection import _diatonic_roots
from pipeline.key_detection import KeyEstimate


def test_diatonic_roots_for_c_major():
    key = KeyEstimate(tonic="C", mode="major", correlation=0.9)
    assert _diatonic_roots(key) == {0, 2, 4, 5, 7, 9, 11}


def test_diatonic_roots_for_a_minor():
    key = KeyEstimate(tonic="A", mode="minor", correlation=0.9)
    # A natural minor uses the same 7 pitch classes as its relative major
    # (C major) -- {A, B, C, D, E, F, G} = {9, 11, 0, 2, 4, 5, 7} -- which is
    # a useful sanity check that the interval math is right.
    assert _diatonic_roots(key) == {0, 2, 4, 5, 7, 9, 11}


from pipeline.chord_detection import BarResult, HYSTERESIS_MARGIN, _smooth_labels


def test_smooth_labels_pulls_an_isolated_ambiguous_bar_to_match_its_neighbors():
    c_template = next(t for root, label, t in _TEMPLATES if label == "C")
    am_template = next(t for root, label, t in _TEMPLATES if label == "Am")
    tied_chroma = c_template + am_template
    am_score = _score_label(tied_chroma, "Am")

    bars = [
        BarResult(label="C", score=1.0, root_forced=False, chroma=c_template),
        BarResult(label="Am", score=am_score, root_forced=False, chroma=tied_chroma),
        BarResult(label="C", score=1.0, root_forced=False, chroma=c_template),
    ]
    assert _smooth_labels(bars) == ["C", "C", "C"]


def test_smooth_labels_never_changes_a_root_forced_bar():
    c_template = next(t for root, label, t in _TEMPLATES if label == "C")
    am_template = next(t for root, label, t in _TEMPLATES if label == "Am")
    tied_chroma = c_template + am_template
    am_score = _score_label(tied_chroma, "Am")

    bars = [
        BarResult(label="C", score=1.0, root_forced=False, chroma=c_template),
        BarResult(label="Am", score=am_score, root_forced=True, chroma=tied_chroma),
        BarResult(label="C", score=1.0, root_forced=False, chroma=c_template),
    ]
    assert _smooth_labels(bars) == ["C", "Am", "C"]


def test_smooth_labels_keeps_a_clearly_dominant_bar():
    # C and F# major triads share no pitch classes at all (disjoint support),
    # so their raw cosine similarity is exactly 0 -- a gap of 1.0, far above
    # HYSTERESIS_MARGIN, so F# must never be smoothed away here.
    c_template = next(t for root, label, t in _TEMPLATES if label == "C")
    fsharp_template = next(t for root, label, t in _TEMPLATES if label == "F#")

    bars = [
        BarResult(label="C", score=1.0, root_forced=False, chroma=c_template),
        BarResult(label="F#", score=1.0, root_forced=False, chroma=fsharp_template),
    ]
    assert _smooth_labels(bars) == ["C", "F#"]


def test_smooth_labels_never_alters_the_first_bar():
    c_template = next(t for root, label, t in _TEMPLATES if label == "C")
    bars = [BarResult(label="C", score=1.0, root_forced=False, chroma=c_template)]
    assert _smooth_labels(bars) == ["C"]


def test_smooth_labels_handles_empty_input():
    assert _smooth_labels([]) == []


def test_smooth_labels_never_overwrites_a_genuinely_silent_bar():
    c_template = next(t for root, label, t in _TEMPLATES if label == "C")
    silent_chroma = np.zeros(12)

    bars = [
        BarResult(label="C", score=1.0, root_forced=False, chroma=c_template),
        BarResult(label="N.C.", score=0.0, root_forced=False, chroma=silent_chroma),
        BarResult(label="C", score=1.0, root_forced=False, chroma=c_template),
    ]
    assert _smooth_labels(bars) == ["C", "N.C.", "C"]
