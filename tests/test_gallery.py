"""The gallery (docs/_ext/gallery.py): the "At a glance" box, the plots (which are shown, in what order, and the data charts.js draws them from; the drawing is tested in charts.test.js), "Try it with mirdata", and the site's two pages."""

import html
import json
import os
import re
import subprocess
import sys

DOCS = os.path.join(os.path.dirname(__file__), "..", "docs")
sys.path.insert(0, os.path.join(DOCS, "_ext"))

import gallery  # noqa: E402

HIST = {"unit": "bpm", "edges": [60, 80, 100], "counts": [2, 1]}


def entry(**fields):
    return {"type": "BeatData", "n_tracks": 3, "n_annotations": 3, **fields}


def test_counts_fields_are_plotted_next_to_histograms():
    plots = gallery.annotation_plots("beats", entry(tempo_from_beats=HIST, meter={4: 3}))
    assert [p["title"] for p in plots] == ["Tempo from beats", "Meter"]  # the schema's field order


def test_parts_are_counts_but_not_a_plot():
    plots = gallery.annotation_plots("beats", entry(meter={4: 3}, parts={"a": 2, "b": 1}))
    assert [p["title"] for p in plots] == ["Meter"]


def test_empty_counts_are_not_plotted():
    assert gallery.annotation_plots("beats", entry(meter={})) == []


def test_hover_text_says_what_the_bars_count():
    [meter] = gallery.annotation_plots("beats", entry(meter={4: 3}))
    assert meter["counted"] == "tracks"  # 3 = n_tracks; charts.js writes it in the hover text


def test_pitches_are_plotted_in_midi_then_in_hz():
    notes = {"type": "NoteData", "n_tracks": 3, "n_annotations": 3, "pitches_hz": {**HIST, "unit": "hz"}, "pitches_midi": {**HIST, "unit": "midi"}}
    plots = gallery.annotation_plots("notes", notes)
    assert [p["title"] for p in plots] == ["Pitches (MIDI)", "Pitches (Hz)"]  # the schema's order, whatever the card's
    assert [p["field"] for p in plots] == ["pitches_midi", "pitches_hz"]  # what Combine mode pools by


def tempo_entry(tempo):
    return {"type": "TempoData", "n_tracks": 3, "n_annotations": 3, "tempo": tempo}


def stats(**entries):
    return {"annotations": {"annotations": entries}}


def titles(plots):
    return [p["title"] for p in plots]


def test_an_annotated_tempo_replaces_the_tempo_from_beats():
    plots = gallery.ordered_plots(stats(beats=entry(tempo_from_beats=HIST, meter={4: 3}), tempo=tempo_entry(HIST)))
    assert "Tempo from beats" not in titles(plots)
    assert {"Tempo", "Meter"} <= set(titles(plots))


def test_without_an_annotated_tempo_the_tempo_from_beats_is_plotted():
    assert "Tempo from beats" in titles(gallery.ordered_plots(stats(beats=entry(tempo_from_beats=HIST))))
    no_values = stats(beats=entry(tempo_from_beats=HIST), tempo=tempo_entry(None))  # a TempoData without values
    assert "Tempo from beats" in titles(gallery.ordered_plots(no_values))


def page_plots(box):
    """The plots a Statistics box hands to charts.js (its data-plots)."""
    return json.loads(html.unescape(re.search(r'data-plots="([^"]*)"', box).group(1)))


def test_every_plot_is_shown_none_folded_away():
    chords = {"type": "ChordData", "n_tracks": 3, "n_annotations": 3, "labels": {"C:maj": 3}, "qualities": {"maj": 3}}
    box = gallery.statistics(stats(beats=entry(tempo_from_beats=HIST, meter={4: 3}), chords=chords))
    assert len(page_plots(box)) == 4
    assert "<details" not in box


def test_the_page_gets_counts_as_pairs_with_number_labels_kept():
    chords = {"type": "ChordData", "n_tracks": 3, "n_annotations": 3, "labels": {"C:maj": 2, "7": 1}}
    box = gallery.statistics(stats(beats=entry(tempo_from_beats=HIST, meter={4: 3}), chords=chords))
    tempo, meter, labels = page_plots(box)
    assert tempo["data"] == HIST
    assert meter == {
        "title": "Meter", "source": "beats · BeatData", "data": [[4, 3]], "counted": "tracks",
        "prop": "beats", "type": "BeatData", "field": "meter",  # what Combine mode matches plots by
    }
    assert labels["data"] == [["C:maj", 2], ["7", 1]]  # "7" is a text label: it stays a string


def test_the_page_gets_the_hidden_tempo_from_beats_for_combine_mode():
    s = stats(beats=entry(tempo_from_beats=HIST), tempo=tempo_entry(HIST))
    s["audio"] = {"n_tracks": 3, "duration_histogram": HIST}
    duration, beat_tempo, tempo = page_plots(gallery.statistics(s))
    assert (duration["prop"], duration["type"], duration["field"]) == (None, None, "duration_histogram")
    assert beat_tempo["title"] == "Tempo from beats" and beat_tempo["combined_only"]  # the single panel hides it
    assert "combined_only" not in tempo and "combined_only" not in duration


def chords_entry(n_annotations):
    return {"type": "ChordData", "n_tracks": 3, "n_annotations": n_annotations, "labels": {"C:maj": 3}, "qualities": {"maj": 3}}


def test_plots_are_grouped_by_type_after_the_audio():
    s = stats(beats=entry(tempo_from_beats=HIST, meter={4: 3}), inferred_chords=chords_entry(2), leadsheet_chords=chords_entry(5))
    s["audio"] = {"n_tracks": 3, "duration_histogram": HIST}
    # inside a type, the entry with the most annotations first; each entry's plots in the schema's order
    assert [(p["title"], p["source"]) for p in gallery.ordered_plots(s)] == [
        ("Duration", "audio"),
        ("Tempo from beats", "beats · BeatData"),
        ("Meter", "beats · BeatData"),
        ("Labels", "leadsheet_chords · ChordData"),
        ("Qualities", "leadsheet_chords · ChordData"),
        ("Labels", "inferred_chords · ChordData"),
        ("Qualities", "inferred_chords · ChordData"),
    ]


def test_try_it_comes_after_the_bibtex():
    card = gallery.render_card({"name": "x", "bibtex": "@article{x}"}, "x")
    assert card.index("BibTeX Citation") < card.index("Try it with mirdata") < card.index("dataset.choice_track()")


SETUP = ["import mirdata", 'dataset = mirdata.initialize("x")', "track = dataset.choice_track()"]


def test_try_it_without_property_names_only_gets_a_track():
    assert gallery.try_it("x", None).splitlines() == SETUP
    assert gallery.try_it("x", {"annotations": {"status": "error", "error": "boom"}}).splitlines() == SETUP


def test_try_it_has_one_line_per_property_grouped_by_type():
    chords = {"type": "ChordData", "n_tracks": 3, "n_annotations": 3}
    keys = {"type": "KeyData", "n_tracks": 3, "n_annotations": 3}
    code = gallery.try_it("x", stats(leadsheet_chords=chords, key_mode=keys, beats=entry(), inferred_chords=chords))
    lines = code.splitlines()
    assert lines[:4] == SETUP + [""]
    access = lines[4:]
    # by type in the tags' order, A–Z inside a type: key_mode comes after both chords
    assert [line.split("#")[0].strip() for line in access] == [
        "track.beats", "track.inferred_chords", "track.leadsheet_chords", "track.key_mode",
    ]
    assert [line.split("# ")[1] for line in access] == ["BeatData", "ChordData", "ChordData", "KeyData"]
    assert len({line.index("#") for line in access}) == 1  # the comments line up
    assert "download" not in code and "validate" not in code and "print" not in code


def test_try_it_names_the_parts_up_to_six():
    notes = {"type": "NoteData", "n_tracks": 3, "n_annotations": 18, "parts": {s: 3 for s in "GDBAeE"}}
    assert gallery.try_it("x", stats(notes=notes)).splitlines()[-1].endswith("# NoteData, one per: G, D, B, A, e, E")
    many = {**notes, "parts": {f"a{i}": 1 for i in range(8)}}
    assert gallery.try_it("x", stats(notes=many)).splitlines()[-1].endswith("# NoteData, one per: a0, a1, a2, a3, a4, a5, …")


CARD ={"name": "x", "license": "MIT", "annotations": ["BeatData"]}


def tasks_value(box):
    return re.search(r'glance-label">Tasks</span><span class="glance-value">([^<]*)<', box).group(1)


def test_glance_rows_end_with_tasks_and_annotation_types_are_not_counted():
    labels = re.findall(r'glance-label">([^<]+)<', gallery.at_a_glance(CARD))
    assert labels == ["Tracks", "Sample rate", "Total duration", "License", "Tasks"]


def test_annotation_tags_stay_for_the_filter():
    assert '<code data-ann="BeatData">BeatData</code>' in gallery.at_a_glance(CARD)


def test_tasks_are_listed():
    box = gallery.at_a_glance({**CARD, "tasks": ["beat tracking", "chord recognition"]})
    assert tasks_value(box) == "beat tracking, chord recognition"


def test_missing_or_null_tasks_show_a_dash():
    assert tasks_value(gallery.at_a_glance(CARD)) == "—"
    assert tasks_value(gallery.at_a_glance({**CARD, "tasks": None})) == "—"


def card_facts(card):
    """What a card hands to Combine mode (its data-facts)."""
    return json.loads(html.unescape(re.search(r'data-facts="([^"]*)"', gallery.combine_facts(card)).group(1)))


def test_combine_mode_gets_the_numbers_behind_at_a_glance():
    audio = {"status": "ok", "n_tracks": 3, "total_seconds": 90.5, "sample_rate": 44100}
    card = {**CARD, "tasks": ["beat tracking"], "stats": {"audio": audio}}
    assert card_facts(card) == {
        "tracks": 3, "seconds": 90.5, "sample_rate": 44100, "tasks": ["beat tracking"], "notes": ["Nothing to plot yet."],
    }


def test_unknown_facts_are_null_and_a_card_without_stats_says_so():
    assert card_facts(CARD) == {
        "tracks": None, "seconds": None, "sample_rate": None, "tasks": [], "notes": ["No statistics yet."],
    }


def test_combine_mode_gets_the_notes_the_statistics_box_shows():
    s = stats(beats=entry(tempo_from_beats=HIST))
    s["annotations"].update(status="needs_local", n_tracks=10, n_tracks_loaded=8)
    box_notes = re.findall(r'<p class="stats-note">([^<]*)</p>', gallery.statistics(s))
    assert box_notes == ["Computed from 8 of 10 tracks (some files need a local run)."]
    assert card_facts({**CARD, "stats": s})["notes"] == box_notes


def test_the_site_has_a_front_page_and_a_gallery_page(tmp_path):
    """The site builds without warnings; the front page links to the gallery, and only the
    gallery page has the mirdata-gallery section that gallery.js turns into the gallery."""
    out = tmp_path / "html"
    build = subprocess.run(
        [sys.executable, "-m", "sphinx", "-W", "-q", "-b", "html", DOCS, str(out), "-d", str(tmp_path / "doctrees")],
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr
    front, gallery_page = (out / "index.html").read_text(), (out / "gallery.html").read_text()
    assert 'href="gallery.html"' in front
    assert 'id="mirdata-gallery"' in gallery_page
    assert 'id="mirdata-gallery"' not in front
