from pipeline.fretboard import map_notes_to_fretboard
from pipeline.transcription import Note
from pipeline.tuning import DROP_D, STANDARD_E_A_D_G_B_E, find_tuning


def _note(pitch, start=0.0, end=0.5):
    return Note(start=start, end=end, pitch=pitch, velocity=0.8)


def test_defaults_to_standard_tuning():
    fretted = map_notes_to_fretboard([_note(40)])
    assert len(fretted) == 1
    assert fretted[0].string == 0
    assert fretted[0].fret == 0


def test_low_note_is_dropped_under_standard_tuning():
    fretted = map_notes_to_fretboard([_note(38)], find_tuning(STANDARD_E_A_D_G_B_E))
    assert fretted == []


def test_low_note_is_fretted_under_drop_d_tuning():
    fretted = map_notes_to_fretboard([_note(38)], find_tuning(DROP_D))
    assert len(fretted) == 1
    assert fretted[0].string == 0
    assert fretted[0].fret == 0


def test_position_window_keeps_sequential_notes_in_same_region():
    """After a high-fret note shifts the window up, subsequent notes should
    prefer frets within that region rather than jumping back to the lowest
    available fret."""
    tuning = find_tuning(STANDARD_E_A_D_G_B_E)
    # MIDI 76 = E5: only playable at fret 12, string 5 (e4) within MAX_FRET=15.
    # This shifts the position window to [10, 14].
    # MIDI 62 = D4: options are (string4, fret3), (string3, fret7), (string2, fret12).
    # Without window: greedy picks fret 3 on string 4 (lowest fret, string 4 is free).
    # With window [10,14]: fret 3 is out of window, fret 7 is out of window,
    #   fret 12 on string 2 IS in window — so window implementation picks fret 12.
    notes = [
        _note(76, start=0.0),  # E5 — forces window to frets 10-14
        _note(62, start=0.1),  # D4 — should land on fret 12 (in-window), not fret 3 (greedy)
    ]
    fretted = map_notes_to_fretboard(notes, tuning)
    assert len(fretted) == 2
    d4_note = [fn for fn in fretted if fn.pitch == 62][0]
    # Without window: greedy picks fret 3 on string 4 (lowest available fret)
    # With window shifted to ~[10,14]: should pick fret 12 on string 2 instead
    assert d4_note.fret >= 10, (
        f"Expected fret >= 10 for D4 after window shift to [10,14], got fret {d4_note.fret}"
    )


def test_open_strings_always_allowed_regardless_of_window():
    """Open strings (fret 0) are always valid even after window has shifted up."""
    tuning = find_tuning(STANDARD_E_A_D_G_B_E)
    # MIDI 76 = E5 at fret 12, string 5 — shifts window up to [10, 14]
    # MIDI 40 = E2 — only playable at fret 0, string 0 (open low E)
    # Even though fret 0 is outside the shifted window, it must still be allowed.
    notes = [
        _note(76, start=0.0),  # shifts window up
        _note(40, start=0.1),  # only playable at fret 0, string 0
    ]
    fretted = map_notes_to_fretboard(notes, tuning)
    open_e = [fn for fn in fretted if fn.pitch == 40]
    assert len(open_e) == 1
    assert open_e[0].fret == 0


def test_dp_open_e_major_chord_is_the_open_shape():
    from pipeline.fretboard import map_notes_to_fretboard_dp
    notes = [Note(start=0.0, end=1.0, pitch=p, velocity=1.0) for p in (40, 47, 52, 56, 59, 64)]
    got = sorted((f.string, f.fret) for f in map_notes_to_fretboard_dp(notes))
    assert got == [(0, 0), (1, 2), (2, 2), (3, 1), (4, 0), (5, 0)]


def test_dp_keeps_a_riff_in_one_position():
    from pipeline.fretboard import map_notes_to_fretboard_dp
    notes = [Note(start=i * 0.5, end=i * 0.5 + 0.4, pitch=p, velocity=1.0)
             for i, p in enumerate((69, 71, 73, 71, 69))]
    frets = [f.fret for f in map_notes_to_fretboard_dp(notes)]
    assert max(frets) - min(frets) <= 4
