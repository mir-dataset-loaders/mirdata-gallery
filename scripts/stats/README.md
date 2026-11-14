```
generate_cards.py ── for each dataset
 ├─ stats.compute → annotations.dataset_stats → remote.fetch
 └─ when the stats are done, delete fetch_root/<name>

remote.fetch
  inputs   index   → wanted: the non-audio paths + metadata
                     audio:  the audio paths (to tell whether a zip holds audio)
           REMOTES → plain files / archives (zip, tar family)
  budget   8 GB per dataset, no time limit
  total    the bytes actually downloaded so far (① and ③ together)
  wanted files already in data_home are kept

① Every plain file (also files not in the index → destination_dir/filename)
   ├─ already on disk → kept, nothing downloaded
   ├─ size known      → [total + file size ≤ 8 GB?]
   │                       ├ yes → download
   │                       └ no  → ✗ refuse
   └─ size unknown    → count while downloading → ✗ stop when the total reaches 8 GB
   (a failed or stopped download leaves no partial file)

② Sort the archives (HEAD for the size)
   HEAD fails → not readable
   size unknown → ③-1 first,  size known → ③-2, smallest first

③ Each archive in that order
   (checked first every time: nothing missing → done, the rest is never opened;
    the budget ran out → logged "not read"; not a zip or a tar → skipped)

   ③-1 Size unknown (e.g. GitHub /archive/: no Range either)
       ├─ zip → count while downloading (temporary file on disk) → ✗ stop at 8 GB
       │        when done → read the list → match wanted → extract
       └─ tar → count while streaming → ✗ stop at 8 GB
                write only the wanted files, drop the rest
                ├─ every wanted file found → stop early
                └─ read to the end → [MD5 = REMOTES checksum?] no → not readable

   ③-2 Size known, smallest first
       ├─ zip → read the list by range
       │    ├─ 206 (Range works) → match wanted and audio
       │    │    ├─ no wanted file → skip
       │    │    ├─ no audio → [total + zip size ≤ 8 GB?]
       │    │    │              ├ yes → whole (temporary file on disk)
       │    │    │              └ no  → [total + wanted files' size ≤ 8 GB?]
       │    │    │                        ├ yes → only the wanted files, by range
       │    │    │                        └ no  → ✗ refuse
       │    │    └─ audio    → [total + wanted files' size ≤ 8 GB?]
       │    │                   ├ yes → only the wanted files, by range
       │    │                   └ no  → ✗ refuse
       │    └─ 200 (Range ignored) → [total + zip size ≤ 8 GB?]
       │                              ├ yes → whole (temporary file) → list → match → extract
       │                              └ no  → ✗ refuse
       │
       └─ tar → [total + tar size ≤ 8 GB?]
                  ├ yes → stream: write only the wanted files
                  │        ├─ every wanted file found → stop early
                  │        └─ read to the end → [MD5 = REMOTES checksum?] no → not readable
                  └ no  → ✗ refuse

✗ refuse / stop → the remaining remotes are not read → needs_local

④ Closing
   wanted paths that no readable remote held → errors
   status: problems → needs_local, failed files → incomplete, else ok
```
