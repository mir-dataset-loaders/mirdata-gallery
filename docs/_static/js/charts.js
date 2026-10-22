// The Statistics charts: every plot as an SVG bar chart, drawn in the page.
// gallery.py puts each panel's plots on its plot grid (data-plots), gallery.js
// draws them with plotGridHtml. A plot is {title, source, counted, data}: data
// is a histogram {unit, edges, counts} or a counts field as [label, count] pairs
// (and a combined one from combine.js has parts, and may have atLeast; it is
// stacked by dataset, or shows one dataset in focus against the whole).
// Every function returns SVG or HTML text, so tests/charts.test.js runs in Node.
(function () {
    // Size of every chart, in SVG units (the chart scales to the width it gets).
    // The margins leave room for the x labels and unit (bottom), for the y numbers
    // (left), and for the last x label to stick out past the bars (right).
    const WIDTH = 120, HEIGHT = 98;
    const LEFT = 21, RIGHT = 12, TOP = 6, BOTTOM = 32;
    const MAX_TICKS = 3; // edge values written under the x axis
    const MAX_Y_TICKS = 4; // round numbers written left of the bars, each with a grid line
    const MIN_SLOTS = 8; // a chart with fewer bars keeps the bar width of this many, with wider gaps
    const MAX_LABELS = 10; // text labels plotted per counts field; the rest join "(other)"
    const MAX_LABEL_CHARS = 7; // a longer label is cut under its bar; the hover text has it whole
    const CHAR_WIDTH = 4.7; // about how wide one character of a plot label is, in SVG units
    const OTHER = "(other)";

    const GROUPED = new Intl.NumberFormat("en-US"); // 1,000

    function escapeHtml(text) {
        return String(text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#x27;");
    }

    // Up to 6 significant digits, trailing zeros dropped: 12.5, 0.2, 1.5
    function shortest(x) {
        return String(Number(x.toPrecision(6)));
    }

    // An edge value as written on the axis: 1,000 or 12.5.
    function number(x) {
        return Number.isInteger(x) ? GROUPED.format(x) : shortest(x);
    }

    // The y ticks under the tallest bar: multiples of the smallest 1, 2 or 5 × 10ⁿ
    // step giving at most MAX_Y_TICKS, without 0.
    function yTicks(highest) {
        for (let e = 0; ; e++) {
            for (const m of [1, 2, 5]) {
                const step = m * 10 ** e;
                const n = Math.floor(highest / step);
                if (n <= MAX_Y_TICKS) return Array.from({ length: n }, (_, i) => step * (i + 1));
            }
        }
    }

    // A y tick as written: 500, 1.5k, 20k, 1.5M.
    function shortNumber(n) {
        if (n >= 1_000_000) return `${shortest(n / 1_000_000)}M`;
        if (n >= 1_000) return `${shortest(n / 1_000)}k`;
        return String(n);
    }

    // The pieces of each bar of a combined plot, bottom to top: its datasets'
    // counts (parts, combine.js), the ones with a colour in colour order, then the
    // others together, grey. countsOf(data) gives one part's count per bar.
    // With a dataset in focus (its name), just its count, then the rest of the
    // bar's total (totals), pale grey: all of it when the dataset is not in the plot.
    function stacks(parts, countsOf, totals, focus = null) {
        const counts = parts.map((part) => countsOf(part.data));
        if (focus != null) {
            const i = parts.findIndex((part) => part.name === focus);
            return totals.map((total, bar) => {
                const own = i < 0 ? 0 : counts[i][bar];
                return [{ slot: i < 0 ? null : parts[i].slot, name: focus, count: own }, { rest: true, count: total - own }];
            });
        }
        const coloured = parts.map((_, i) => i).filter((i) => parts[i].slot != null);
        coloured.sort((a, b) => parts[a].slot - parts[b].slot);
        const grey = parts.map((_, i) => i).filter((i) => parts[i].slot == null);
        return counts[0].map((_, bar) => {
            const pieces = coloured.map((i) => ({ slot: parts[i].slot, name: parts[i].name, count: counts[i][bar] }));
            if (grey.length) {
                const name = grey.length === 1 ? parts[grey[0]].name : "others";
                pieces.push({ slot: null, name, count: grey.reduce((sum, i) => sum + counts[i][bar], 0) });
            }
            return pieces;
        });
    }

    // A bar's hover text: what it is (its range or label) and its count,
    // "60–80 bpm: 84 tracks", "at least" when the count may miss some (atLeast).
    // With several datasets, their counts too, " (a 36, b 48)"; with one in
    // focus, its count of the whole instead, "60–80 bpm: a 36 of 84 tracks".
    function barTip(what, count, counted, pieces, atLeast = false) {
        const total = `${atLeast ? "at least " : ""}${GROUPED.format(count)} ${counted}`;
        if (pieces && pieces.at(-1).rest) return `${what}: ${pieces[0].name} ${GROUPED.format(pieces[0].count)} of ${total}`;
        if (!pieces || pieces.length < 2) return `${what}: ${total}`;
        const named = pieces.filter((p) => p.count).map((p) => `${p.name} ${GROUPED.format(p.count)}`);
        return named.length ? `${what}: ${total} (${named.join(", ")})` : `${what}: ${total}`;
    }

    // The part every chart shares: one bar per count, the x axis, and the y ticks
    // (yTicks), each a grid line behind the bars and a number; hovering shows the
    // exact counts.
    //
    // Each bar has an equal slot of the x axis and sits in its middle. With fewer
    // than MIN_SLOTS bars, a bar keeps the width it has in a chart of MIN_SLOTS
    // bars, so a few bars are spread out instead of filling the chart. The
    // tallest bar reaches the top. With pieces (stacks), a bar is drawn as its
    // pieces, each in its dataset's colour (custom.css, combine-c0 to c4, grey
    // combine-other), the rest of a bar with a dataset in focus pale grey
    // (combine-rest). gapless bars touch, so many thin ones read as one shape
    // (notesSvg).
    // Returns the SVG pieces (without the closing tag), the slot width and the y of the axis.
    function barsSvg(counts, tips, pieces = null, gapless = false) {
        const plotWidth = WIDTH - LEFT - RIGHT, plotHeight = HEIGHT - TOP - BOTTOM;
        const slot = plotWidth / counts.length;
        const barWidth = plotWidth / Math.max(counts.length, MIN_SLOTS);
        const highest = Math.max(...counts) || 1;
        const base = TOP + plotHeight;
        const gap = gapless ? 0 : 1;

        const out = [`<svg class="plot-svg${gapless ? " plot-notes" : ""}" viewBox="0 0 ${WIDTH} ${HEIGHT}" role="img">`];
        for (const tick of yTicks(Math.max(...counts))) {
            const y = (base - (plotHeight * tick) / highest).toFixed(1);
            out.push(
                `<line class="plot-gridline" x1="${LEFT}" y1="${y}" x2="${WIDTH - RIGHT}" y2="${y}"/>` +
                    `<text class="plot-label plot-y-label" x="${LEFT - 2}" y="${y}" text-anchor="end"` +
                    ` dominant-baseline="middle">${shortNumber(tick)}</text>`
            );
        }
        counts.forEach((count, i) => {
            const x = LEFT + i * slot;
            const barX = x + (slot - barWidth) / 2;
            const rect = (cls, bottom, height) =>
                `<rect class="${cls}" x="${(barX + gap / 2).toFixed(2)}" y="${(bottom - height).toFixed(1)}"` +
                ` width="${Math.max(barWidth - gap, 0.5).toFixed(2)}" height="${height.toFixed(1)}"/>`;
            let bar = rect("plot-bar", base, (plotHeight * count) / highest);
            if (pieces) {
                let bottom = base;
                bar = "";
                for (const piece of pieces[i].filter((p) => p.count)) {
                    const height = (plotHeight * piece.count) / highest;
                    const colour = piece.rest ? "rest" : piece.slot == null ? "other" : `c${piece.slot}`;
                    bar += rect(`plot-piece combine-${colour}`, bottom, height);
                    bottom -= height;
                }
            }
            out.push(
                `<g><title>${escapeHtml(tips[i])}</title>` +
                    `<rect class="plot-hit" x="${x.toFixed(1)}" y="${TOP}" width="${slot.toFixed(1)}" height="${plotHeight}"/>` +
                    `${bar}</g>`
            );
        });
        out.push(`<line class="plot-axis" x1="${LEFT}" y1="${base}" x2="${WIDTH - RIGHT}" y2="${base}"/>`);
        return { out, slot, base };
    }

    // One histogram {unit, edges, counts} as an SVG bar chart.
    //
    // The x axis shows up to MAX_TICKS edge values and the unit. Hovering a bar
    // shows its range and count. parts (combine.js, each on the same edges)
    // stack the bars by dataset, or show one dataset in focus (its name).
    // Pitches, one bar per note, are drawn by notesSvg.
    function histogramSvg(hist, counted, parts = null, focus = null) {
        if (isNotes(hist)) return notesSvg(hist, counted, parts, focus);
        const { edges, counts } = hist;
        const { unit } = hist;
        const plotWidth = WIDTH - LEFT - RIGHT;
        const pieces = parts && stacks(parts, (data) => data.counts, counts, focus);
        const tips = counts.map((count, i) =>
            barTip(`${number(edges[i])}–${number(edges[i + 1])} ${unit}`, count, counted, pieces && pieces[i])
        );
        const { out, slot, base } = barsSvg(counts, tips, pieces);
        const step = Math.ceil(counts.length / (MAX_TICKS - 1)); // every step-th edge, so labels are evenly spaced
        for (let i = 0; i < edges.length; i += step) {
            out.push(
                `<text class="plot-label" x="${(LEFT + i * slot).toFixed(1)}" y="${base + 10}"` +
                    ` text-anchor="middle">${number(edges[i])}</text>`
            );
        }
        out.push(
            `<text class="plot-unit" x="${(LEFT + plotWidth / 2).toFixed(1)}" y="${base + 20}"` +
                ` text-anchor="middle">${escapeHtml(unit)}</text>`
        );
        out.push("</svg>");
        return out.join("");
    }

    // --- Pitches: one bar per note ---------------------------------------------

    const NOTE_NAMES = ["C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B"];
    const TAIL = 0.0005; // the share of the values on each side a pitch chart may fold into its end bars

    // A pitch histogram from scripts/stats (note_histogram): MIDI, one bin per
    // note, its edges at half notes (59.5, 60.5, ...)
    function isNotes(hist) {
        const { unit, edges } = hist;
        return unit === "midi" && Math.abs(edges[0] - Math.floor(edges[0]) - 0.5) < 1e-9 && edges.every((e, i) => Math.abs(e - edges[0] - i) < 1e-9);
    }

    const noteName = (n) => `${NOTE_NAMES[n % 12]}${Math.floor(n / 12) - 1}`; // 60: C4
    const noteHz = (n) => GROUPED.format(Math.round(440 * 2 ** ((n - 69) / 12))); // 69: 440

    // The bars a pitch chart keeps, from..to: the rare extremes on each side,
    // at most TAIL of the values, are counted in the end bars instead, so a few
    // stray values (a pitch tracker's harmonics) do not stretch the axis
    function keptBars(counts) {
        const cut = counts.reduce((sum, count) => sum + count, 0) * TAIL;
        let from = 0, to = counts.length - 1, low = 0, high = 0;
        while (from < to && low + counts[from] <= cut) low += counts[from++];
        while (to > from && high + counts[to] <= cut) high += counts[to--];
        return { from, to };
    }

    // counts from..to, the ones before and after added to the first and last
    function fold(counts, from, to) {
        const kept = counts.slice(from, to + 1);
        kept[0] += counts.slice(0, from).reduce((sum, count) => sum + count, 0);
        kept[kept.length - 1] += counts.slice(to + 1).reduce((sum, count) => sum + count, 0);
        return kept;
    }

    // A pitch histogram (isNotes) as one bar per note, the bars touching. The
    // x axis names each C (C3, C4, ...), and an end bar that holds the folded
    // extremes (keptBars) its note with "≤" or "≥". Hovering a bar shows its
    // note, Hz and count: "A4 · 440 Hz: 120 values". parts and focus as in
    // histogramSvg.
    function notesSvg(hist, counted, parts = null, focus = null) {
        const first = Math.round(hist.edges[0] + 0.5); // the note of the first bin
        const { from, to } = keptBars(hist.counts);
        const counts = fold(hist.counts, from, to);
        const low = from > 0, high = to < hist.counts.length - 1; // extremes folded in
        const folded = parts && parts.map((part) => ({ ...part, data: { counts: fold(part.data.counts, from, to) } }));
        const pieces = folded && stacks(folded, (data) => data.counts, counts, focus);
        const last = counts.length - 1;
        const tips = counts.map((count, i) => {
            const n = first + from + i;
            let what = `${noteName(n)} · ${noteHz(n)} Hz`;
            if (i === 0 && low) what = `${noteName(n)} and below · ${noteHz(n)} Hz and below`;
            if (i === last && high) what = `${noteName(n)} and above · ${noteHz(n)} Hz and above`;
            return barTip(what, count, counted, pieces && pieces[i]);
        });
        const { out, slot, base } = barsSvg(counts, tips, pieces, true);
        const x = (i) => LEFT + (i + 0.5) * slot;
        const label = (i, text) => `<text class="plot-label" x="${x(i).toFixed(1)}" y="${base + 10}" text-anchor="middle">${escapeHtml(text)}</text>`;
        const ends = [...(low ? [[0, `≤${noteName(first + from)}`]] : []), ...(high ? [[last, `≥${noteName(first + to)}`]] : [])];
        const wide = (text) => Array.from(text).length * 5.5; // about how wide an axis label is, a little generous
        const clear = (i, text) => ends.every(([end, other]) => Math.abs(x(end) - x(i)) > (wide(text) + wide(other)) / 2 + 2);
        counts.forEach((_, i) => {
            const n = first + from + i;
            if (n % 12 || !clear(i, noteName(n))) return; // a C, clear of the end labels
            out.push(`<line class="plot-axis" x1="${x(i).toFixed(1)}" y1="${base}" x2="${x(i).toFixed(1)}" y2="${base + 2.5}"/>`, label(i, noteName(n)));
        });
        out.push(...ends.map(([i, text]) => label(i, text)), "</svg>");
        return out.join("");
    }

    // [label, count] per bar of a counts field (given as [label, count] pairs).
    //
    // Numbers (meter, polyphony) are all plotted, in order. Text labels are
    // plotted most common first, MAX_LABELS of them; the rest join "(other)".
    function countBars(pairs) {
        if (pairs.every(([label]) => typeof label === "number")) {
            return [...pairs].sort((a, b) => a[0] - b[0]);
        }
        const named = pairs
            .filter(([label]) => label !== OTHER)
            .map(([label, count]) => [String(label), count])
            .sort((a, b) => b[1] - a[1]); // stable: a tie keeps the stored order
        const other = pairs.find(([label]) => label === OTHER);
        const rest = named.slice(MAX_LABELS).reduce((sum, [, count]) => sum + count, 0) + (other ? other[1] : 0);
        return named.slice(0, MAX_LABELS).concat(rest ? [[OTHER, rest]] : []);
    }

    // One counts field ([label, count] pairs) as an SVG bar chart, the same chart as a histogram.
    //
    // Every bar has its label under it: flat when every label fits under its
    // bar, else tilted, smaller and cut to MAX_LABEL_CHARS. Hovering a bar shows
    // the whole label and its count, "at least" for the labels in atLeast (a
    // pooled count that may miss some of a dataset's "(other)", combine.js).
    // parts (combine.js, each a dataset's own pairs) stack the bars by dataset,
    // or show one dataset in focus (its name); when the label may hide in that
    // dataset's "(other)", its count is unknown and the hover says so.
    function countsSvg(pairs, counted, atLeast = [], parts = null, focus = null) {
        const bars = countBars(pairs);
        const unsure = new Set(atLeast.map(String));
        const pieces = parts && stacks(parts, (data) => countsUnder(bars, data), bars.map(([, count]) => count), focus);
        const focused = focus != null && parts && parts.find((part) => part.name === focus);
        const tips = bars.map(([label, count], i) => {
            const tip = barTip(String(label), count, counted, pieces && pieces[i], unsure.has(String(label)));
            if (!focused || label === OTHER || !mayHide(focused.data, label)) return tip;
            return `${label}: at least ${GROUPED.format(count)} ${counted}; ${focus}'s may be in its ${OTHER}`;
        });
        const { out, slot, base } = barsSvg(
            bars.map(([, count]) => count),
            tips,
            pieces
        );
        const labels = bars.map(([label]) => Array.from(String(label))); // characters, as Python counts them
        const flat = labels.every((chars) => chars.length * CHAR_WIDTH <= slot);
        labels.forEach((chars, i) => {
            const x = (LEFT + (i + 0.5) * slot).toFixed(1);
            const label = chars.join("");
            if (flat) {
                out.push(
                    `<text class="plot-label" x="${x}" y="${base + 10}"` +
                        ` text-anchor="middle">${escapeHtml(label)}</text>`
                );
                return;
            }
            const text = chars.length <= MAX_LABEL_CHARS ? label : chars.slice(0, MAX_LABEL_CHARS - 1).join("") + "…";
            const y = base + 3;
            out.push(
                `<text class="plot-label plot-label-tilted" x="${x}" y="${y}" text-anchor="end"` +
                    ` dominant-baseline="middle" transform="rotate(-60 ${x} ${y})">${escapeHtml(text)}</text>`
            );
        });
        out.push("</svg>");
        return out.join("");
    }

    // One dataset's count under each bar of a counts chart (bars from countBars):
    // its count of the bar's label, and under "(other)" the rest of its total
    function countsUnder(bars, pairs) {
        const own = new Map(pairs.map(([label, count]) => [String(label), count]));
        const total = pairs.reduce((sum, [, count]) => sum + count, 0);
        const named = bars.filter(([label]) => label !== OTHER).reduce((sum, [label]) => sum + (own.get(String(label)) || 0), 0);
        return bars.map(([label]) => (label === OTHER ? total - named : own.get(String(label)) || 0));
    }

    // Whether a dataset's pairs may hide label in their "(other)": they have one, but not the label
    function mayHide(pairs, label) {
        return pairs.some(([l, count]) => l === OTHER && count > 0) && !pairs.some(([l]) => String(l) === String(label));
    }

    function chartSvg(data, counted, atLeast, parts, focus) {
        return Array.isArray(data) ? countsSvg(data, counted, atLeast, parts, focus) : histogramSvg(data, counted, parts, focus);
    }

    // The figures of a plot grid: each plot's title, its source and its chart,
    // with focus (a dataset's name, Combine mode) showing that dataset's part
    // of every combined plot.
    function plotGridHtml(plots, focus = null) {
        return plots
            .map(
                (p) =>
                    `<figure class="plot"><figcaption><span class="plot-title">${escapeHtml(p.title)}</span>` +
                    `<span class="plot-source">${escapeHtml(p.source)}</span></figcaption>` +
                    `${chartSvg(p.data, p.counted, p.atLeast, p.parts, focus)}</figure>`
            )
            .join("\n");
    }

    const charts = {
        WIDTH, LEFT, RIGHT, TOP, MAX_LABELS, MAX_LABEL_CHARS, MIN_SLOTS,
        escapeHtml, number, yTicks, shortNumber, isNotes, histogramSvg, countBars, countsSvg, chartSvg, plotGridHtml,
    };
    if (typeof module !== "undefined" && module.exports) {
        module.exports = charts; // Node, for the tests
    } else {
        window.mirdataCharts = charts;
    }
})();
