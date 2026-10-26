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

    // Bar widths, smallest first: 1, 2 or 5 × 10ⁿ (scripts/stats/histograms.py's)
    function* tidyWidths() {
        for (let e = -10; e < 30; e++) for (const step of [1, 2, 5]) yield clean(step * 10 ** e);
    }

    // Bar widths for times in seconds, smallest first: 1, 2 or 5 × 10ⁿ under a
    // second, then by the clock: 1, 2, 5, 10, 15, 30 seconds, the same in minutes,
    // then 1, 2 or 5 × 10ⁿ hours
    function* clockWidths() {
        for (let e = -10; e < 0; e++) for (const step of [1, 2, 5]) yield clean(step * 10 ** e);
        for (const unit of [1, 60]) for (const step of [1, 2, 5, 10, 15, 30]) yield step * unit;
        for (let e = 0; e < 30; e++) for (const step of [1, 2, 5]) yield clean(step * 10 ** e * 3600);
    }

    // Edges a histogram can be pooled on, finest first. Evenly spaced ones
    // (scripts/stats/histograms.py) sit on multiples of their width: the
    // candidates are multiples of each of widths(), from the widest of the
    // histograms up. Log ones sit on 1, 2, 5 × 10ⁿ, or on whole decades.
    function* candidateEdges(hists, widths = tidyWidths) {
        const lo = Math.min(...hists.map((h) => h.edges[0]));
        const hi = Math.max(...hists.map((h) => h.edges.at(-1)));
        const even = (edges) => edges.every((e, i) => i < 2 || Math.abs(e - edges[i - 1] - (edges[1] - edges[0])) < 1e-9 * Math.max(1, Math.abs(e)));
        if (hists.every((h) => even(h.edges))) {
            const widest = Math.max(...hists.map((h) => h.edges[1] - h.edges[0]));
            for (const width of widths()) {
                if (!atMost(widest, width)) continue;
                const first = Math.floor(lo / width + 1e-9), last = Math.ceil(hi / width - 1e-9);
                if (last - first > MAX_BINS) continue; // too many bars: no need to list them
                yield Array.from({ length: Math.max(last - first, 1) + 1 }, (_, i) => clean((first + i) * width));
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
    function sharedBins(hists, widths = tidyWidths) {
        for (const edges of candidateEdges(hists, widths)) {
            if (edges.length - 1 > MAX_BINS) continue;
            const each = hists.map((h) => rebin(h, edges));
            if (!each.some((counts) => counts === null)) return { edges, each };
        }
        return null;
    }

    const SECONDS = { s: 1, min: 60, h: 3600 }; // the time units, in seconds

    // Histograms in different time units on shared bars: each in seconds (exact:
    // its edges times 60 or 3600), on clockWidths. In seconds when every value is
    // under 10 minutes (the last bar ends by 600 s), else in minutes. null when
    // they are not all times, or cannot be pooled exactly.
    function timeBins(hists) {
        if (!hists.every((h) => SECONDS[h.unit])) return null;
        const inSeconds = hists.map((h) => ({ ...h, edges: h.edges.map((e) => clean(e * SECONDS[h.unit])) }));
        const bins = sharedBins(inSeconds, clockWidths);
        if (!bins) return null;
        if (atMost(bins.edges.at(-1), 600)) return { unit: "s", ...bins };
        return { unit: "min", edges: bins.edges.map((e) => clean(e / 60)), each: bins.each };
    }

    // Histograms on shared bars, {unit, edges, each}: of one unit, on
    // sharedBins in that unit; of different time units, on timeBins. null
    // when they cannot be pooled exactly.
    function pooledBins(hists) {
        if (hists.every((h) => h.unit === hists[0].unit)) {
            const bins = sharedBins(hists);
            return bins && { unit: hists[0].unit, ...bins };
        }
        return timeBins(hists);
    }

    const addUp = (each) => each[0].map((_, i) => each.reduce((sum, counts) => sum + counts[i], 0));

    // Histograms added up, on pooledBins: no count is split or guessed. null
    // when they cannot be.
    function poolHistograms(hists) {
        const bins = pooledBins(hists);
        return bins && { unit: bins.unit, edges: bins.edges, counts: addUp(bins.each) };
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

    // The colour a dataset gets when it joins a combination: the first of 0 to
    // COLOURS - 1 that no dataset in it has (taken), 0 being the single panel's
    // purple; null, grey, when all are taken. It keeps that colour until it leaves.
    function nextColour(taken) {
        for (let slot = 0; slot < COLOURS; slot++) if (!taken.includes(slot)) return slot;
        return null;
    }

    const unitKey = (unit) => (SECONDS[unit] ? "time" : unit); // any time units match: timeBins
    const matchKey = (p) => [p.prop, p.type, p.field, Array.isArray(p.data) ? "" : unitKey(p.data.unit)].join("|");
    const typeRank = (p) => (p.type ? `1${p.type}` : "0"); // the audio's first, then the types A–Z

    // The plots of a combination, from each dataset's plots ({name, slot,
    // plots}, in the order selected; slot its colour, nextColour). Plots of the same property, type, field
    // and unit (any time units count as one: pooledBins) are pooled into one,
    // its source starting with how many datasets it holds when not all do; a
    // plot no other dataset has, or one that cannot be pooled exactly, is shown
    // on its own, in its own unit, its source starting with its dataset. Every plot has parts: each dataset's own data on the plot's bars,
    // with its colour, for charts.js to stack. In the single
    // panel's order: the audio's first, then the types A–Z, pooled ones first in
    // a type.
    function combinedPlots(datasets) {
        const groups = new Map();
        for (const { name, slot, plots } of datasets) {
            for (const plot of plots) {
                const key = matchKey(plot);
                if (!groups.has(key)) groups.set(key, []);
                groups.get(key).push({ name, slot, plot });
            }
        }
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
                    const bins = pooledBins(plots.map((p) => p.data));
                    if (bins) {
                        const on = (counts) => ({ unit: bins.unit, edges: bins.edges, counts });
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

    const combine = { glanceRows, namedNotes, poolHistograms, poolCounts, nextColour, combinedPlots };
    if (typeof module !== "undefined" && module.exports) {
        module.exports = combine; // Node, for the tests
    } else {
        window.mirdataCombine = combine;
    }
})();
