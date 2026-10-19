"""The gallery (docs/_ext/gallery.py): the "At a glance" box, and the plots (histograms and counts fields, one chart style)."""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "docs", "_ext"))

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


def test_text_labels_plot_the_ten_most_common_and_the_rest_as_other():
    counts = {f"label{i}": 100 - i for i in range(30)}
    counts["(other)"] = 7  # what the stats folded already
    bars = gallery.count_bars(counts)
    assert len(bars) == gallery.MAX_LABELS + 1
    assert bars[:2] == [("label0", 100), ("label1", 99)]
    assert bars[-1] == ("(other)", sum(100 - i for i in range(10, 30)) + 7)
    assert sum(c for _, c in bars) == sum(counts.values())


def test_number_labels_plot_every_value_in_order():
    assert gallery.count_bars({6: 1, 4: 95, 5: 3}) == [(4, 95), (5, 3), (6, 1)]


def test_short_labels_sit_flat_and_long_ones_are_tilted_and_cut():
    flat = gallery.counts_svg({"major": 240, "minor": 120}, "tracks")
    assert "rotate" not in flat and ">major<" in flat
    tilted = gallery.counts_svg({f"C#:maj7/{i}": 10 - i for i in range(10)}, "values")
    assert "plot-label-tilted" in tilted
    labels = re.findall(r'plot-label-tilted"[^>]*>([^<]*)<', tilted)
    assert all(len(label) <= gallery.MAX_LABEL_CHARS for label in labels)
    assert "<title>C#:maj7/0: 10 values</title>" in tilted  # the hover text has the whole label


def test_hover_text_says_what_the_bars_count():
    [meter] = gallery.annotation_plots("beats", entry(meter={4: 3}))
    assert meter["counted"] == "tracks"  # 3 = n_tracks
    assert "4: 3 tracks" in gallery.chart_svg(meter["data"], meter["counted"])


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


def test_every_plot_is_shown_none_folded_away():
    chords = {"type": "ChordData", "n_tracks": 3, "n_annotations": 3, "labels": {"C:maj": 3}, "qualities": {"maj": 3}}
    box = gallery.statistics(stats(beats=entry(tempo_from_beats=HIST, meter={4: 3}), chords=chords))
    assert box.count('<figure class="plot">') == 4
    assert "<details" not in box


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


def bar_rects(svg):
    return [(float(x), float(w)) for x, w in re.findall(r'class="plot-bar" x="([\d.]+)" y="[\d.]+" width="([\d.]+)"', svg)]


def test_few_bars_keep_the_width_of_min_slots_bars_and_spread_out():
    few = bar_rects(gallery.counts_svg({3: 1, 4: 2}, "tracks"))
    full = bar_rects(gallery.counts_svg({i: 1 for i in range(gallery.MIN_SLOTS)}, "tracks"))
    assert few[0][1] == full[0][1]  # the same bar width as a chart of MIN_SLOTS bars
    plot_width = gallery.WIDTH - gallery.LEFT - gallery.RIGHT
    centres = [x + w / 2 for x, w in few]
    assert abs((centres[1] - centres[0]) - plot_width / 2) < 0.2  # each bar in the middle of its half


def test_many_bars_fill_their_slots():
    bars = bar_rects(gallery.counts_svg({i: 1 for i in range(20)}, "tracks"))
    plot_width = gallery.WIDTH - gallery.LEFT - gallery.RIGHT
    assert abs(bars[0][1] - (plot_width / 20 - 1)) < 0.1


def test_y_ticks_are_round_steps_below_the_tallest_bar():
    assert gallery.y_ticks(47) == [10, 20, 30, 40]
    assert gallery.y_ticks(360) == [100, 200, 300]
    assert gallery.y_ticks(19_276) == [5_000, 10_000, 15_000]
    assert gallery.y_ticks(473_953) == [100_000, 200_000, 300_000, 400_000]
    assert gallery.y_ticks(1_658_562) == [500_000, 1_000_000, 1_500_000]
    assert gallery.y_ticks(3) == [1, 2, 3]
    assert gallery.y_ticks(1) == [1]
    assert gallery.y_ticks(0) == []  # no "0" tick, and nothing above an empty chart


def test_y_numbers_are_short_from_1000_up():
    assert [gallery.short_number(n) for n in [500, 1_000, 1_500, 20_000, 1_000_000, 1_500_000]] == [
        "500", "1k", "1.5k", "20k", "1M", "1.5M",
    ]


def gridline_ys(svg):
    return [float(y) for y in re.findall(r'class="plot-gridline" x1="[\d.]+" y1="([\d.]+)"', svg)]


def test_every_y_tick_has_a_gridline_behind_the_bars_and_a_number():
    svg = gallery.counts_svg({"a": 40, "b": 10}, "tracks")
    assert re.findall(r'plot-y-label"[^>]*>([^<]*)<', svg) == ["10", "20", "30", "40"]
    ys = gridline_ys(svg)
    assert len(ys) == 4
    assert min(ys) == gallery.TOP  # the tallest bar (40) reaches the top line
    assert svg.index("plot-gridline") < svg.index("plot-bar")  # drawn first, so behind


def test_histograms_get_y_ticks_too():
    svg = gallery.histogram_svg(HIST, "tracks")  # counts [2, 1]
    assert re.findall(r'plot-y-label"[^>]*>([^<]*)<', svg) == ["1", "2"]


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
