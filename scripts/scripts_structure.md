# Stats scripts: structure

The stats code is a `stats` package used by two commands. The package does
the work and returns plain dicts; the commands read the arguments and print.

- `scripts/generate_cards.py` puts the stats into each card's `stats` field
  (see "Stats in the cards" below).
- `scripts/compute_stats.py` is for looking at the stats: it prints
  everything, including the logs and per-file errors a card leaves out, and
  never writes a card.

Apart from the cards, nothing is written to disk except, in remote mode, the
fetched annotation files in a temporary folder.

```
scripts/
  generate_cards.py         # the cards, including their stats field
  compute_stats.py          # inspection: prints the full stats, writes nothing
  stats/
    __init__.py
    common.py               # shared: budget, status, index loading, dataset selection
    dataset.py              # both parts for one dataset (used by both commands)
    to_card.py              # a result -> the card's "stats" field; keep or replace
    histograms.py           # numbers -> {unit, edges, counts}
    remote_zip.py           # reading parts of a zip on a server (HTTP range requests)
    audio/
      __init__.py           # dataset_stats: source -> read -> summarize -> status
      headers.py            # duration and sample rate from the first 64 KB of a file
      sources.py            # reading those headers remotely or locally
      summary.py            # per-file results -> dataset numbers
    annotations/
      __init__.py           # dataset_stats, remote_stats, local_stats
      properties.py         # which track properties are official mirdata annotations
      types.py              # one Stat class per annotation type
      remote_files.py       # getting the annotation files out of the remotes
```

## Stats in the cards

`generate_cards.py` builds every card with `build_card`, whose last field is
`stats`. Like the summary, the stats are only recomputed when needed:

- the card has no stats yet, or the dataset's index changed (the card stores
  the index fingerprint), or `--force-stats` or `--local` is given;
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
python scripts/generate_cards.py --max-mb 2000 --max-minutes 30 # larger remote limits
```

## How one run flows

`python scripts/compute_stats.py --dataset rwc_popular`

1. `compute_stats.py` reads the arguments and picks the datasets
   (`select_datasets` in `common.py`).
2. For each dataset it calls `mirdata.initialize`, then runs two independent
   parts:
   - **Audio**: `stats.audio.dataset_stats` reads only the first bytes of each
     audio file, from the remote zips or from your disk, and adds up
     durations and sample rates.
   - **Annotations**: in remote mode, `stats.annotations.remote_stats` first
     copies the annotation files into a temporary folder (`remote_files.py`). Then
     mirdata's own loaders read every track, and one `Stat` object per
     annotation property turns them into histograms.
3. Each part returns a dict with a `status`: `ok`, `incomplete` or
   `needs_local`.
4. `compute_stats.py` prints each part and ends with the list of datasets to
   rerun with `--local`. With `--json` it prints the dicts instead.

The result per dataset is `{"name", "audio", "annotations"}`.

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
python scripts/compute_stats.py --max-mb 2000 --max-minutes 30           # larger remote limits
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

A remote run has one budget per dataset, shared by both parts: `--max-mb`
(default 4000) counts only the annotation files downloaded, since the audio
part reads headers only, and `--max-minutes` (default 10) counts the time of
both parts. Local runs have no limits.

## What each file holds, and why it is needed

### `scripts/compute_stats.py`

The inspection command. It prints the full result of each part and never
writes a card.

- `parse_args`, `main`: the flags and the loop over datasets.
- `compute`: one dataset, through `stats/dataset.py`, printing each part as
  it finishes.
- `print_audio`, `print_annotations`, `print_part`, `fmt`: the terminal output.
- `print_table`: the summary table after several datasets. The closing list
  of what to rerun locally is `print_to_do` in `stats/common.py`, shared with
  `generate_cards.py`.

### `scripts/generate_cards.py` (the stats part)

- `build_card`: every card field, `stats` last.
- `card_stats`: decides the stats of one card: keep the old ones, or compute
  (`stats/dataset.py`), convert (`stats/to_card.py`) and keep the more complete.
- `generate`: prints each card's stats status and ends with the list of
  datasets to complete with `--local` (`print_to_do`, shared with
  `compute_stats.py`).

The stats flags (`--local`, `--datasets-dir`, `--max-mb`, `--max-minutes`)
and the `--dataset` check are the same functions in both commands
(`add_stats_arguments`, `select_datasets` in `stats/common.py`).

### `stats/dataset.py`

The one place that runs both parts for a dataset, so the two commands
compute exactly the same thing.

- `compute`: checks the local copy exists (local mode), initializes the
  dataset once with the folder its files are read from (local) or fetched
  into (remote), loads its index once for both parts, then runs each part in
  its own try, so a failing part does not stop the other. A remote run gets
  one `Budget` for both parts (the audio part sees it through
  `Budget.time_only`, so its header reads do not count toward the MB limit);
  local runs have none.
- `audio_part`, `annotations_part`: call `stats.audio` and
  `stats.annotations` in local or remote mode.

### `stats/common.py`

What both parts share.

- `Budget` and `RemoteLimit`: the megabyte and minute limits. Every remote
  read checks them first, so a big download is refused before it starts.
- `part_status`: turns problems and failures into `ok`, `incomplete` or
  `needs_local`.
- `load_index`: gets a dataset's index file, never the whole dataset. Some
  mirdata loaders download gigabytes when their own download is called.
- `remote_problems`: the closing problems of a remote read (the limit, or
  the files no readable remote held), worded the same for audio and
  annotations.
- `print_to_do`: the closing list of datasets to rerun locally, incomplete
  or failed; used by both commands.
- `add_stats_arguments`: the stats flags both commands share.
- `select_datasets`, `positive_int`, `hms`: the `--dataset` and `--exclude`
  choice, argument checking, and time formatting.

### `stats/to_card.py`

Turns a `compute_stats` result into the card's `stats` field. A card keeps
what the gallery shows or needs to decide on: the numbers, the histograms,
each part's status and problems, and counts of errors instead of the error
lists. Log lines and per-file details stay out.

- `card_stats`: the whole field, with a `computed` block saying how
  (`remote` or `local`), from which index (its fingerprint) and when.
- `audio_card`, `annotations_card`: what each part keeps.
- `index_fingerprint`: the index's published MD5 checksum, read from
  mirdata without downloading the index. It changes exactly when mirdata's
  index for the dataset changes, which tells a later run whether the stats
  are still current.
- `needs_compute`, `choose`, `rank`: the keep-or-replace rules above.
- `status_line`: the short status shown by `generate_cards.py`.

The field's structure is checked by `tests/card_schema.py` (the `stats`
rule). In the YAML, lists of numbers are written on one line
(`cards_io.py`), so a histogram takes three lines.

### `stats/histograms.py`

Turns lists of numbers into `{unit, edges, counts}` for the cards. One shared
module means every histogram on every card follows the same rules.

- `histogram`: picks a bin width from the data (Freedman-Diaconis rule,
  rounded to 1, 2, 2.5 or 5 times a power of ten, at most 20 bins). With
  `log=True` it uses log-spaced edges, for lengths that span milliseconds to
  minutes.
- `step_width`, `next_step_width`, `log_edges`: choose those widths and edges.
- `duration_histogram`: seconds, or minutes when the median track is over
  2 minutes.
- `format_histogram`: the one-line terminal version.

### `stats/remote_zip.py`

Reads parts of a zip on a server without downloading it. This is what makes
remote mode possible: a 4 GB audio zip costs a few megabytes.

- `HTTPFile`: makes a URL behave like a file. Each read becomes one HTTP
  range request, retried when the server rate-limits, and charged to the
  budget.
- `member_head`: the first bytes of one file inside the zip (what audio
  needs).
- `member_bytes`: one whole file inside the zip, CRC-checked (what
  annotations need).
- `match_members`: matches zip entries to index paths, handling the
  destination folder and the wrapper folders mirdata strips when unpacking.
- `session`, `ARCHIVE_EXTENSIONS`: the HTTP session and the list of
  non-zip archives, shared by the audio and annotation remote readers.

### `stats/audio/`

- **`headers.py`**: duration and sample rate from the first 64 KB of a file,
  without decoding any audio. `wav_header`, `flac_header`, `mp3_header` parse
  each format; `read_member` reads from a remote zip, `read_file` from disk.
- **`sources.py`**: the two ways of getting at those files.
  `remote_durations` opens each zip remote, reads the matching audio files in
  parallel, and collects the problems that mean "run locally".
  `local_durations` reads the same headers from a local copy, and raises an
  error if there is no copy.
- **`summary.py`**: per-file results to dataset numbers. `track_audio_paths`
  finds which index entries are audio (keys containing "audio"); `summarize`
  computes track counts, total duration, the duration histogram and sample
  rates.
- **`__init__.py`**: `dataset_stats` ties the three together: choose a
  source, read, summarize, add the status.

### `stats/annotations/`

- **`properties.py`**: `annotation_properties` looks at a dataset's Track
  class and keeps the properties of the 10 official mirdata annotation types,
  with the same detection as the card's `annotations` field.
- **`types.py`**: what to measure for each annotation type.
  - `Stat`: the base class. `add` unpacks dicts, MultiAnnotators and lists,
    refuses anything that is not the right mirdata class, and counts tracks
    and annotations.
  - One subclass per type: `Beats`, `Chords`, `F0`, `MultiF0`, `Notes`,
    `Sections`, `Keys`, `Lyrics`, `Events`, `Tempo`. Each has `read` (collect
    one annotation) and `result` (histograms and label counts). `Beats` also
    derives the tempo.
  - `STATS`: maps each type name to its class, checked against mirdata's own
    list.
  - Helpers: `unpack`, `is_empty`, `chord_quality`, `interval_lengths`,
    `to_seconds`, `top_counts`.
- **`remote_files.py`**: remote mode for annotations. mirdata's loaders only read
  files on disk, so the files have to be put there first.
  - `annotation_paths`: every non-audio file the index lists, plus metadata.
    It skips multitrack member lists, and with `--limit` keeps only the
    selected tracks.
  - `fetch`: gets those files. Zips up to 200 MB are downloaded whole, bigger
    ones are read by range, plain files are downloaded whole. It reports
    problems: tar.gz archives, the limit reached.
  - `open_zip`, `download_whole`: the download paths, with a fallback for
    servers without range support, such as GitHub's generated archives.
  - `index_notes`: logs index sections that are empty, such as Billboard's
    metadata.
- **`__init__.py`**: runs the annotation part.
  - `dataset_stats`: loads each track, then each property separately, so one
    broken file only costs that annotation. It feeds each property's `Stat`
    and collects `tracks_with`, `skipped` and `annotation_errors`.
  - `remote_stats`: fetch, then `dataset_stats`, then the status.
  - `local_stats`: the same on a local copy.
  - `quiet_logging`: silences mirdata's per-track warnings while loading.

## Tests

The tests in `tests/` mirror the modules, one file per module, for example
`test_histograms.py`, `test_remote_files.py` and `test_compute_stats.py`.
They use fake servers and fake datasets, so nothing touches the network.
Checks against real data (rwc_popular, guitarset, salami and others) were
done by hand during development.
