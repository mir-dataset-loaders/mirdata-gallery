# Stats scripts: structure

The stats code is a `stats` package used by two commands. The package does
the work and returns plain dicts; the commands read the arguments and print.

- `scripts/generate_cards.py` puts the stats into each card's `stats` field
  (see "Stats in the cards" below).
- `scripts/compute_stats.py` is for looking at the stats: might remove after inspecting. 

Apart from the cards, nothing is written to disk except, in remote mode, the
fetched annotation files in a temporary folder.

```
scripts/
  generate_cards.py         # the cards, including their stats field
  compute_stats.py          # inspection: prints the full stats, writes nothing
  card_builder.py           # the card fields; also which track properties are annotations
  card_utils.py             # reads and writes the card YAML
  stats/
    __init__.py             # compute(): both parts for one dataset (used by both commands)
    audio.py                # the audio part: track and file counts from the index
    annotations.py          # the annotations part: fetch (remote), load each track, feed the Stats
    annotation_types.py     # one Stat class per annotation type: what is measured
    remote.py               # reading the remotes: zips by range, annotation files, budget
    histograms.py           # numbers -> {unit, edges, counts}
    card.py                 # a result -> the card's "stats" field; keep or replace
    utils.py                # what the two commands share: flags, dataset choice, to-do list

tests/card_schema.py        # the fields each annotation type must have in a card
docs/_ext/gallery.py        # draws the card's stats as plots on the docs page
```

## Stats in the cards

`generate_cards.py` builds every card with `build_card`, whose last field is
`stats`. Like the summary, the stats are only recomputed when needed:

- the card has no stats yet, or the dataset's index changed (the card stores
  the index checksum), or `--force-stats` or `--local` is given;
- otherwise the card keeps its stats, and nothing is computed.

When both old and new stats exist for the same index, the more complete ones
win (ok, then incomplete, then needs_local, then error, judged by each
card's worst part). So a local `ok` is never replaced by a later remote
`needs_local`. The run ends with the datasets whose stats need a local run.

```
python scripts/generate_cards.py --dataset rwc_popular          # stats from the remotes
python scripts/generate_cards.py --dataset tonas --local        # stats from ~/mir_datasets/tonas
python scripts/generate_cards.py --no-stats                     # keep every card's stats as is
python scripts/generate_cards.py --force-stats                  # recompute every dataset's stats
python scripts/generate_cards.py --max-mb 4000 --max-minutes 30 # larger remote limits
```

## How one run flows

`python scripts/compute_stats.py --dataset rwc_popular` (remote mode, the
default):

1. **Choose the datasets.** `main` reads the flags (`parse_args`) and picks
   the datasets (`select_datasets` in `stats/utils.py`). It makes a temporary
   folder for the fetched files, deleted at the end (`--fetch-dir` keeps
   them).
2. **One dataset: `stats.compute`** (`stats/__init__.py`).
   - Local mode: stops if `~/mir_datasets/<name>` does not exist.
   - Calls `mirdata.initialize(name, data_home)` once. `data_home` is the
     local copy, or in remote mode `<fetch folder>/<name>`: once the files
     are fetched there, mirdata's loaders read them as if the dataset had
     been downloaded.
   - Remote mode: makes one `Budget` (`--max-mb`, `--max-minutes`) for the
     whole dataset.
   - Runs the two parts, each in its own `try`: a part that fails becomes
     `{"status": "error", "error": ...}` and the other still runs.
     `compute_stats.py` prints each part as it finishes (`on_part`).
3. **Audio part:** `audio.dataset_stats`. `load_index` gets the index file,
   and only that file. The part counts the tracks and the audio files the
   index lists. No audio is read, so its status is always `ok`.
4. **Annotations part.**
   - Remote: `annotations.remote_stats`
     1. `remote.annotation_paths` lists every non-audio file in the index,
        plus the metadata files.
     2. `remote.fetch` copies those files into `data_home`, reading big zips
        by range. Every read is charged to the budget. It returns the files
        it could not get (`missing_files`) and why a local run is needed
        (`problems`).
     3. `dataset_stats` reads the fetched files.
   - Local: `annotations.local_stats` runs `dataset_stats` on the local copy;
     nothing is fetched.
   - `annotations.dataset_stats` reads the annotations in both modes:
     1. `card_builder.annotation_properties` gives `{property: type}` for the
        dataset's Track class. Only the 10 official mirdata types are kept.
     2. It makes one `Stat` per property, from `STATS` in
        `annotation_types.py`.
     3. For each track (only the first N with `--limit`), it creates the
        track (`ds.track`), then reads each property on its own:
        `getattr(track, prop)` makes mirdata load that file. Empty values
        are skipped. `stat.add(value)` unpacks dicts, annotators and lists
        and calls `read` on each annotation. An error costs only that
        property of that track (`annotation_errors`); a track that cannot be
        created at all goes to `errors`.
     4. It makes one entry per property that has at least one track:
        `type`, `n_tracks`, `n_annotations`, `parts` (when a track holds
        several annotations), and the type's fields from `stat.result()`.
   - `part_status` sets the status: `needs_local` when there are problems,
     `incomplete` when files are missing or failed, else `ok`.
5. **Print.** Each part's block (or everything as JSON with `--json`), a
   table after several datasets, then `print_to_do`: the datasets to rerun
   with `--local`.

`generate_cards.py` runs the same steps 2 to 4 through `update_stats`, only
when the stats must be recomputed (see "Stats in the cards"). Then:

6. `stats.card.result_to_card_stats` keeps what the card needs, `choose`
   decides between the old and the new stats, `build_card` puts them in the
   `stats` field, and `card_utils.write_card` writes the YAML.
7. When the docs are built, `docs/_ext/gallery.py` reads each card's `stats`
   and draws the plots.

The result per dataset (the `name` key is removed from each part):

```
{"name": ...,
 "audio": {status, problems, n_tracks, n_audio_files},
 "annotations": {status, problems, sources, missing_files,
                 n_tracks, n_tracks_loaded, tracks_with,
                 annotations: {property: entry}, skipped, errors, annotation_errors}}
```

## Usage

```
python scripts/compute_stats.py --dataset rwc_popular                    # both parts, from the remotes
python scripts/compute_stats.py --dataset rwc_popular --only audio
python scripts/compute_stats.py --dataset rwc_popular --only annotations
python scripts/compute_stats.py --dataset rwc_popular --limit 5          # quick look
python scripts/compute_stats.py --dataset rwc_popular --json
python scripts/compute_stats.py --exclude acousticbrainz_genre           # every other dataset
python scripts/compute_stats.py --dataset rwc_popular --local            # ~/mir_datasets/<name>
python scripts/compute_stats.py --local --datasets-dir /path/to/mir_datasets
python scripts/compute_stats.py --dataset rwc_popular --fetch-dir /tmp/ann  # keep fetched files
python scripts/compute_stats.py --max-mb 4000 --max-minutes 30           # larger remote limits
```

## Status of each part

| Status | Meaning | What to do |
|---|---|---|
| `ok` | Everything was read. | Nothing. |
| `incomplete` | Some files failed in a way a local copy would not fix: a corrupt file, a mirdata loader bug. | Look at its errors. |
| `needs_local` | The remotes cannot give a complete answer. The `problems` field says why. | Run with `--local`. |

Reasons for `needs_local`: no remotes (manual download or restricted data),
no access (HTTP 403 or 404), archives that cannot be read remotely
(tar.gz), the remote limit reached, or files that are in
no readable remote.

The audio part is always `ok`: it reads only the index, so these statuses
come from the annotations part.

A remote run has one budget per dataset, spent by the annotations part:
`--max-mb` (default 2000) counts the annotation files downloaded, and
`--max-minutes` (default 10) the time spent reading remotes. Local runs have
no limits.

## What each file holds, and why it is needed

### `scripts/compute_stats.py`

Why: to see everything a run found (sources, missing files, per-file errors)
without touching a card.

- `parse_args`, `main`: the flags and the loop over datasets.
- `compute`: one dataset, through `stats.compute`, printing each part as
  it finishes.
- `print_part`, `print_audio`, `print_annotations`, `fmt`, `hms`: the
  terminal output.
- `print_table`: the summary table after several datasets. The closing list
  of what to rerun locally is `print_to_do` in `stats/utils.py`, shared with
  `generate_cards.py`.

### `scripts/generate_cards.py` (the stats part)

Why: the only command that puts stats into the cards.

- `update_stats`: the stats of one card. It keeps the old ones (with
  `--no-stats`, without a local copy in local mode, or when they are
  current), or computes (`stats.compute`), converts (`stats/card.py`) and
  keeps the more complete.
- `generate`: prints each card's stats status and ends with the list of
  datasets to complete with `--local` (`print_to_do`, shared with
  `compute_stats.py`).

The stats flags (`--local`, `--datasets-dir`, `--max-mb`, `--max-minutes`)
and the `--dataset` check are the same functions in both commands
(`add_stats_arguments`, `select_datasets` in `stats/utils.py`).

### `scripts/card_builder.py` and `scripts/card_utils.py` (what the stats use)

- `card_builder.annotation_properties`: which Track properties are
  annotations, and of which type. The card's `annotations` field and the
  stats use the same detection, so they never disagree.
- `card_builder.build_card`: every card field, `stats` last.
- `card_utils.write_card`: writes the YAML. Lists of numbers go on one
  line, so a histogram takes three lines.

### `stats/__init__.py`

Why: both commands go through one function, so they compute exactly the same
thing, and each dataset is initialized and its index loaded only once.

- `compute`: steps 2 to 4 above. The audio part is the same in both modes
  and whatever `--limit`; only the annotations part depends on the mode.
- `load_index`: gets a dataset's index file, never the whole dataset. It
  never calls `ds.download()`: some loaders override it and pull gigabytes.
- `PARTS`: the two parts, `audio` and `annotations`.

### `stats/audio.py`

Why: track and file counts come free from the index, so no audio is ever
downloaded.

- `track_audio_paths`: which index entries are audio (keys containing
  "audio").
- `summarize`: counts the tracks and the distinct audio files they list.
- `dataset_stats`: the whole audio part: those counts, with the status
  (always `ok`).

Durations and sample rates are not computed: they will come from mirdata's
index once it has them. For now `total_seconds`, `sample_rate` and
`duration_histogram` were added by hand to the guitarset, orchset and
rwc_popular cards. Recomputing those cards' stats drops them
(`AUDIO_KEYS` in `stats/card.py`).

### `stats/annotations.py`

Why: one loop reads every annotation with mirdata's own loaders, so the
stats show what mirdata users get. Remote and local runs differ only in where
the files come from.

There is one entry point per mode, and both call the same loop:

- `remote_stats` (remote mode): fetches the files (`remote.annotation_paths`,
  `remote.fetch`), runs `dataset_stats`, then sets the status. It adds
  `sources` (one line per remote) and `missing_files`.
- `local_stats` (local mode): `dataset_stats` on the local copy, then the
  status.
- `dataset_stats`: the loop (step 4 above). It loads each track, then each
  property separately, feeds each property's `Stat`, and collects
  `tracks_with`, `skipped`, `errors` and `annotation_errors`. Not to be
  confused with `audio.dataset_stats`, which is the whole audio part.

Helpers:

- `part_status`: turns problems and failures into `ok`, `incomplete` or
  `needs_local`.
- `index_notes`: log lines for index sections that are empty, such as
  Billboard's metadata.
- `quiet_logging`: silences mirdata's per-track warnings while loading.

### `stats/annotation_types.py`

Why: each annotation type is measured differently. One class per type keeps
those rules in one place, and each class reads only mirdata objects of its
own type.

- `Stat`: the base class. `add` unpacks dicts, MultiAnnotators and lists,
  refuses anything that is not the right mirdata class, and counts tracks,
  annotations and `parts` (dict keys or annotators). `summary` gives those
  counts.
- One subclass per type, each with `read` (collect one annotation) and
  `result` (its fields):

| Type | Class | Field | What it counts |
|---|---|---|---|
| BeatData | `Beats` | `meter` | tracks per beats per bar: each track's most common bar length (3/4 and 3/8 both give 3) |
| | | `tempo_from_beats` | one value per annotation: 60 / median beat gap (not annotated) |
| ChordData | `Chords` | `labels`, `qualities` | chord labels; their qualities (maj, min, 7, N...) |
| EventData | `Events` | `events` | event labels |
| F0Data | `F0` | `frequencies` | voiced frames: frequency > 0 and voicing > 0 (a likelihood from 0.5) |
| KeyData | `Keys` | `keys`, `modes` | key labels; their modes (after the ":") |
| LyricData | `Lyrics` | `lyric_unit` | annotations per lyric unit (words, syllables...) |
| | | `lyrics_per_track` | one value per track: its lyric entries over all its annotations |
| MultiF0Data | `MultiF0` | `frequencies` | every pitch of every frame |
| | | `polyphony` | frames per number of pitches at once; silent frames left out |
| NoteData | `Notes` | `pitches` | every note's pitch |
| SectionData | `Sections` | `labels` | section labels |
| | | `section_interval_seconds` | every section's length, in log-spaced bins |
| TempoData | `Tempo` | `tempo` | annotated BPM values |

  Histograms come from `histograms.histogram`, and pitches from
  `histograms.note_histogram`, one bin per note: every value is converted to
  MIDI first (`to_midi`, with mirdata's `convert_pitch_units`), as loaders
  give pitches in Hz, MIDI or note names, often just the unit their files or
  their mirdata version used. The gallery writes the note names and their
  Hz. Label
  counts keep the `TOP` (30) most common, with the rest under "(other)"
  (`top_counts`); `meter`, `polyphony` and `lyric_unit` keep every value.
  The gallery plots fewer.
- `STATS`: maps each type name to its class, checked against mirdata's own
  list (`ANNOTATION_TYPES`).
- Helpers: `unpack`, `is_empty`, `chord_quality`, `interval_lengths`,
  `bar_lengths`, `to_seconds`, `to_midi`, `top_counts`.

### `stats/remote.py`

Why: reading parts of a zip on a server without downloading it is what makes
remote mode possible: a 4 GB audio zip costs a few megabytes. mirdata's
loaders only read files on disk, so the annotation files are put there first.

- `Budget` and `RemoteLimit`: the megabyte and minute limits
  (`MAX_REMOTE_MB`, `MAX_REMOTE_MINUTES`). Every remote read checks them
  first, so a big download is refused before it starts.
- `HTTPFile`: makes a URL behave like a file. Each read becomes one HTTP
  range request, retried when the server rate-limits, and charged to the
  budget.
- `member_bytes`: one whole file inside the zip, CRC-checked.
- `match_members`: matches zip entries to index paths, handling the
  destination folder and the wrapper folders mirdata strips when unpacking.
- `http_session`, `ARCHIVE_EXTENSIONS`: the HTTP session and the list of
  non-zip archives.
- `annotation_paths`: every non-audio file the index lists, plus metadata.
  It skips multitrack member lists, and with `--limit` keeps only the
  selected tracks.
- `fetch`: gets those files. Each zip's file list is read first. A zip that
  holds annotation files is downloaded whole up to `MAX_ARCHIVE_MB` (200 MB)
  and read by range when bigger; plain files are downloaded whole. It
  reports problems: tar.gz archives, the limit reached.
- `open_zip`, `whole_zip`, `download_whole`: the download paths, with a
  fallback for servers without range support, such as GitHub's generated
  archives.

### `stats/histograms.py`

Why: every histogram on every card follows the same rules, so they can be
compared.

- `histogram`: numbers to `{unit, edges, counts}`, or None without values.
  One rule picks the bin width: the Freedman-Diaconis width rounded to 1, 2
  or 5 times a power of ten, but never narrower than what keeps it to
  `MAX_BINS` (25) bins. Without 2.5, widths from 1 up are whole numbers. With
  `log=True` it uses log-spaced edges, for lengths that span milliseconds to
  minutes.
- `note_histogram`: MIDI pitches to one bin per note, each value under its
  nearest whole note (edges at half notes: 59.5, 60.5, ...), so float noise
  such as 71.99996 for C5 cannot put a note in the next bin. Every note from
  the lowest to the highest gets a bin, more than `MAX_BINS` or not; the
  gallery trims the rare extremes when it draws them.
- `tidy_width`, `log_edges`: choose those widths and edges.
- `format_histogram`: the one-line terminal version.

### `stats/card.py`

Why: a card keeps only what the gallery shows or needs to decide on: the
numbers, the histograms, each part's status and problems, and counts of
errors instead of the error lists. Log lines and per-file details stay out.

- `result_to_card_stats`: the whole field, with a `computed` block saying how
  (`remote` or `local`), and from which index (its checksum).
- `audio_to_card`, `annotations_to_card`: what each part keeps
  (`AUDIO_KEYS`, `ANNOTATION_KEYS`). `meter` and `polyphony` stay keyed by
  numbers.
- `index_checksum`: the index's published MD5 checksum, read from
  mirdata without downloading the index. It changes exactly when mirdata's
  index for the dataset changes, which tells a later run whether the stats
  are still current.
- `is_current`, `choose`, `rank`: the keep-or-replace rules above.
- `status_line`: the short status shown by `generate_cards.py`.

The field's structure is checked by `tests/card_schema.py` (the `stats`
rule). `STATS_ANNOTATION_FIELDS` there lists each type's fields, and the
gallery plots them in that order.

### `stats/utils.py`

Why: both commands take the same stats flags and end with the same to-do
list.

- `print_to_do`: the closing list of datasets to rerun locally, incomplete
  or failed.
- `add_stats_arguments`: the stats flags both commands share.
- `select_datasets`, `positive_int`: the `--dataset` and `--exclude`
  choice, and argument checking.

### `docs/_ext/gallery.py` (where the stats end up)

Draws each card's stats as SVG bar charts on the docs page. It decides what
to show, so the cards keep every entry:

- the audio duration comes first, then one plot set per annotation type (the
  entry with the most annotations), then the other entries' plots. The
  first 3 plots are shown, the rest are behind "Show more";
- label counts show the 10 most common, the rest as "(other)";
- an annotated tempo (`TempoData`) replaces `tempo_from_beats`.

## Tests

Need to revisit.

The tests in `tests/` use a fake dataset (`fake_dataset.py`) and a fake
server (`fake_server.py`), so nothing touches the network.

| File | What it checks |
|---|---|
| `test_annotation_types.py` | one annotation type at a time: beats, F0, multi-F0, sections, lyrics, events |
| `test_histograms.py` | the bin-width rule and tidy edges |
| `test_local_dataset.py` | local mode: the fake dataset's stats, read from disk |
| `test_remote_dataset.py` | remote mode: the same numbers as a local run |
| `test_remote.py` | remote mode when something breaks, and the status that follows |
| `test_compute_stats.py` | what a `compute_stats.py` run leaves on disk |
| `test_generate_cards.py` | the card it writes, and when its stats are recomputed or kept |
| `test_to_card.py` | `stats/card.py` and the YAML form (`card_utils.py`) |
| `test_cards_schema.py` | every `cards/*.yaml` against `card_schema.py` |
| `test_gallery.py` | the gallery's plots |

Checks against real data (rwc_popular, guitarset, salami and others) were
done by hand during development.
