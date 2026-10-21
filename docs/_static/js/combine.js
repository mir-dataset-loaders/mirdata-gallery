// Combine mode: the panel of several datasets together. gallery.js builds the
// panel; these functions work out its text from each card's facts (gallery.py,
// combine_facts: tracks, seconds, sample_rate, tasks, notes) and its plots
// pooled from each card's (gallery.py, plot_grid; charts.js draws them). Every
// function returns plain values, so tests/combine.test.js runs in Node.
(function () {
    const GROUPED = new Intl.NumberFormat("en-US"); // 1,000

    // " (2 of 3 datasets)" when only some of the datasets know a value
    function coverage(known, total) {
        return known < total ? ` (${known} of ${total} datasets)` : "";
    }

    // '6.7 hours' from one hour up, else '23.6 min' (as gallery.py's duration)
    function duration(seconds) {
        return seconds >= 3600 ? `${(seconds / 3600).toFixed(1)} hours` : `${(seconds / 60).toFixed(1)} min`;
    }

    // The At a glance rows of a combination, as [label, value] pairs. A value
    // adds up (or lists) what the datasets know, and says how many know it when
    // not all do; null when none does.
    function glanceRows(facts) {
        const n = facts.length;
        const known = (key) => facts.map((f) => f[key]).filter((v) => v != null);
        const sum = (values) => values.reduce((total, v) => total + v, 0);
        const tracks = known("tracks");
        const rates = known("sample_rate");
        const seconds = known("seconds");
        const withTasks = facts.filter((f) => f.tasks.length);
        const tasks = [...new Set(withTasks.flatMap((f) => f.tasks))];
        const kHz = [...new Set(rates)].sort((a, b) => a - b).map((rate) => rate / 1000);
        return [
            ["Tracks", tracks.length ? GROUPED.format(sum(tracks)) + coverage(tracks.length, n) : null],
            ["Sample rate", rates.length ? `${kHz.join(", ")} kHz` + coverage(rates.length, n) : null],
            ["Total duration", seconds.length ? duration(sum(seconds)) + coverage(seconds.length, n) : null],
            ["Tasks", tasks.length ? tasks.join(", ") + coverage(withTasks.length, n) : null],
        ];
    }

    // Each dataset's notes, with its name in front: "orchset: no statistics yet."
    function namedNotes(datasets) {
        return datasets.flatMap(({ name, notes }) =>
            notes.map((text) => `${name}: ${text.charAt(0).toLowerCase()}${text.slice(1)}`)
        );
    }

    // --- Pooled plots ---------------------------------------------------------

    const MAX_BINS = 25; // as scripts/stats/histograms.py: a pooled histogram has no more bars either
    const OTHER = "(other)";
    const clean = (x) => Number(x.toFixed(10)); // float noise off: 0.6000000000000001 -> 0.6
    const atMost = (a, b) => a <= b + 1e-9 * Math.max(1, Math.abs(a), Math.abs(b));

    // Edges a histogram can be pooled on, finest first. Evenly spaced ones
    // (scripts/stats/histograms.py) sit on multiples of a width of 1, 2 or 5 × 10ⁿ:
    // the candidates are such widths, from the widest of the histograms up. Log
    // ones sit on 1, 2, 5 × 10ⁿ, or on whole decades.
    function* candidateEdges(hists) {
        const lo = Math.min(...hists.map((h) => h.edges[0]));
        const hi = Math.max(...hists.map((h) => h.edges.at(-1)));
        const even = (edges) => edges.every((e, i) => i < 2 || Math.abs(e - edges[i - 1] - (edges[1] - edges[0])) < 1e-9 * Math.max(1, Math.abs(e)));
        if (hists.every((h) => even(h.edges))) {
            const widest = Math.max(...hists.map((h) => h.edges[1] - h.edges[0]));
            for (let e = Math.floor(Math.log10(widest)); e < 30; e++) {
                for (const step of [1, 2, 5]) {
                    const width = clean(step * 10 ** e);
                    if (!atMost(widest, width)) continue;
                    const first = Math.floor(lo / width + 1e-9), last = Math.ceil(hi / width - 1e-9);
                    yield Array.from({ length: Math.max(last - first, 1) + 1 }, (_, i) => clean((first + i) * width));
                }
            }
        } else if (lo > 0) {
            for (const steps of [[1, 2, 5], [1]]) {
                const grid = [];
                for (let e = Math.floor(Math.log10(lo)) - 1; e <= Math.ceil(Math.log10(hi)); e++) {
                    grid.push(...steps.map((step) => clean(step * 10 ** e)));
                }
                const start = Math.max(...grid.filter((g) => atMost(g, lo)));
                const end = Math.min(...grid.filter((g) => atMost(hi, g)));
                yield grid.filter((g) => atMost(start, g) && atMost(g, end));
            }
        }
    }

    // The counts of hist on the given edges, or null when one of its bars would be split
    function rebin(hist, edges) {
        const counts = edges.slice(1).map(() => 0);
        let j = 0;
        for (let i = 0; i < hist.counts.length; i++) {
            const a = hist.edges[i], b = hist.edges[i + 1];
            while (j < counts.length && atMost(edges[j + 1], a)) j++; // to the bar that holds a
            if (j === counts.length || !atMost(edges[j], a) || !atMost(b, edges[j + 1])) return null;
            counts[j] += hist.counts[i];
        }
        return counts;
    }

    // The finest edges every bar of each histogram fits into whole, at most
    // MAX_BINS bars, and each histogram's counts on them; null when there are none
    function sharedBins(hists) {
        for (const edges of candidateEdges(hists)) {
            if (edges.length - 1 > MAX_BINS) continue;
            const each = hists.map((h) => rebin(h, edges));
            if (!each.some((counts) => counts === null)) return { edges, each };
        }
        return null;
    }

    const addUp = (each) => each[0].map((_, i) => each.reduce((sum, counts) => sum + counts[i], 0));

    // Histograms of one unit added up, on sharedBins: no count is split or
    // guessed. null when they cannot be.
    function poolHistograms(hists) {
        const bins = sharedBins(hists);
        return bins && { unit: hists[0].unit, edges: bins.edges, counts: addUp(bins.each) };
    }

    // Counts fields ([label, count] pairs) added up, label by label. A dataset
    // keeps only its most common text labels, the rest in "(other)": a label it
    // did not keep may hide in there, so its pooled count is "at least" (atLeast).
    function poolCounts(fields) {
        const total = new Map();
        for (const pairs of fields) {
            for (const [label, count] of pairs) total.set(label, (total.get(label) || 0) + count);
        }
        const folded = fields.filter((pairs) => pairs.some(([label, count]) => label === OTHER && count > 0));
        const atLeast = [...total.keys()].filter(
            (label) => label !== OTHER && folded.some((pairs) => !pairs.some(([l]) => l === label))
        );
        return { pairs: [...total], atLeast };
    }

    const COLOURS = 5; // datasets with a colour of their own; the others share grey

    // Each dataset's colour ({tracks} each): 0 to COLOURS - 1 for the ones with
    // the most tracks, 0 the most (a tie keeps the order selected); null, grey,
    // for the rest. One colour per dataset for the whole panel.
    function colourSlots(datasets) {
        const byTracks = datasets.map((_, i) => i).sort((a, b) => (datasets[b].tracks ?? -1) - (datasets[a].tracks ?? -1));
        const slots = datasets.map(() => null);
        byTracks.slice(0, COLOURS).forEach((i, slot) => (slots[i] = slot));
        return slots;
    }

    const matchKey = (p) => [p.prop, p.type, p.field, Array.isArray(p.data) ? "" : p.data.unit].join("|");
    const typeRank = (p) => (p.type ? `1${p.type}` : "0"); // the audio's first, then the types A–Z

    // The plots of a combination, from each dataset's plots ({name, tracks,
    // plots}, in the order selected). Plots of the same property, type, field
    // and unit are pooled into one, its source starting with how many datasets
    // it holds when not all do; a plot no other dataset has, or one that cannot
    // be pooled exactly, is shown on its own, its source starting with its
    // dataset. Every plot has parts: each dataset's own data on the plot's bars,
    // with its colour (colourSlots), for charts.js to stack. In the single
    // panel's order: the audio's first, then the types A–Z, pooled ones first in
    // a type.
    function combinedPlots(datasets) {
        const slots = colourSlots(datasets);
        const groups = new Map();
        datasets.forEach(({ name, plots }, i) => {
            for (const plot of plots) {
                const key = matchKey(plot);
                if (!groups.has(key)) groups.set(key, []);
                groups.get(key).push({ name, slot: slots[i], plot });
            }
        });
        const out = [];
        for (const members of groups.values()) {
            const plots = members.map((m) => m.plot);
            const part = (m, data) => ({ name: m.name, slot: m.slot, data });
            let merged = null; // {data, atLeast, parts}
            if (members.length > 1) {
                if (Array.isArray(plots[0].data)) {
                    const { pairs, atLeast } = poolCounts(plots.map((p) => p.data));
                    merged = { data: pairs, atLeast, parts: members.map((m) => part(m, m.plot.data)) };
                } else {
                    const bins = sharedBins(plots.map((p) => p.data));
                    if (bins) {
                        const on = (counts) => ({ unit: plots[0].data.unit, edges: bins.edges, counts });
                        merged = { data: on(addUp(bins.each)), atLeast: [], parts: members.map((m, i) => part(m, on(bins.each[i]))) };
                    }
                }
            }
            if (merged) {
                const counted = plots.every((p) => p.counted === plots[0].counted) ? plots[0].counted : "values";
                const coverage = members.length < datasets.length ? `${members.length} of ${datasets.length} · ` : "";
                out.push({ ...plots[0], ...merged, counted, source: coverage + plots[0].source, pooled: true });
            } else {
                for (const m of members) {
                    out.push({ ...m.plot, source: `${m.name} · ${m.plot.source}`, pooled: false, parts: [part(m, m.plot.data)] });
                }
            }
        }
        // Array sort is stable: the first-seen order stays inside a rank
        return out.sort((a, b) => {
            const [ra, rb] = [typeRank(a), typeRank(b)];
            return ra < rb ? -1 : ra > rb ? 1 : b.pooled - a.pooled;
        });
    }

    const combine = { glanceRows, namedNotes, poolHistograms, poolCounts, colourSlots, combinedPlots };
    if (typeof module !== "undefined" && module.exports) {
        module.exports = combine; // Node, for the tests
    } else {
        window.mirdataCombine = combine;
    }
})();
