// The Statistics charts: every plot as an SVG bar chart, drawn in the page.
// gallery.py puts each panel's plots on its plot grid (data-plots), gallery.js
// draws them with plotGridHtml. A plot is {title, source, counted, data}: data
// is a histogram {unit, edges, counts} or a counts field as [label, count] pairs
// (and a combined one from combine.js has parts, and may have atLeast).
// Every function returns SVG or HTML text, so tests/charts.test.js runs in Node.
(function () {
    const UNIT_LABELS = { hz: "Hz", midi: "MIDI" }; // how a unit is written; others as stored

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
    function stacks(parts, countsOf) {
        const counts = parts.map((part) => countsOf(part.data));
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

    // A bar's hover text: tip, and with several datasets their counts, " (a 36, b 48)"
    function withPieces(tip, pieces) {
        if (!pieces || pieces.length < 2) return tip;
        const named = pieces.filter((p) => p.count).map((p) => `${p.name} ${GROUPED.format(p.count)}`);
        return `${tip} (${named.join(", ")})`;
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
    // combine-other).
    // Returns the SVG pieces (without the closing tag), the slot width and the y of the axis.
    function barsSvg(counts, tips, pieces = null) {
        const plotWidth = WIDTH - LEFT - RIGHT, plotHeight = HEIGHT - TOP - BOTTOM;
        const slot = plotWidth / counts.length;
        const barWidth = plotWidth / Math.max(counts.length, MIN_SLOTS);
        const highest = Math.max(...counts) || 1;
        const base = TOP + plotHeight;

        const out = [`<svg class="plot-svg" viewBox="0 0 ${WIDTH} ${HEIGHT}" role="img">`];
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
                `<rect class="${cls}" x="${(barX + 0.5).toFixed(1)}" y="${(bottom - height).toFixed(1)}"` +
                ` width="${Math.max(barWidth - 1, 0.5).toFixed(1)}" height="${height.toFixed(1)}"/>`;
            let bar = rect("plot-bar", base, (plotHeight * count) / highest);
            if (pieces) {
                let bottom = base;
                bar = "";
                for (const piece of pieces[i].filter((p) => p.count)) {
                    const height = (plotHeight * piece.count) / highest;
                    bar += rect(`plot-piece combine-${piece.slot == null ? "other" : `c${piece.slot}`}`, bottom, height);
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
    // stack the bars by dataset.
    function histogramSvg(hist, counted, parts = null) {
        const { edges, counts } = hist;
        const unit = UNIT_LABELS[hist.unit] ?? hist.unit;
        const plotWidth = WIDTH - LEFT - RIGHT;
        const pieces = parts && stacks(parts, (data) => data.counts);
        const tips = counts.map((count, i) =>
            withPieces(`${number(edges[i])}–${number(edges[i + 1])} ${unit}: ${GROUPED.format(count)} ${counted}`, pieces && pieces[i])
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
    // parts (combine.js, each a dataset's own pairs) stack the bars by dataset.
    function countsSvg(pairs, counted, atLeast = [], parts = null) {
        const bars = countBars(pairs);
        const unsure = new Set(atLeast.map(String));
        const pieces = parts && stacks(parts, (data) => countsUnder(bars, data));
        const tips = bars.map(([label, count], i) =>
            withPieces(`${label}: ${unsure.has(String(label)) ? "at least " : ""}${GROUPED.format(count)} ${counted}`, pieces && pieces[i])
        );
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

    function chartSvg(data, counted, atLeast, parts) {
        return Array.isArray(data) ? countsSvg(data, counted, atLeast, parts) : histogramSvg(data, counted, parts);
    }

    // The figures of a plot grid: each plot's title, its source and its chart.
    function plotGridHtml(plots) {
        return plots
            .map(
                (p) =>
                    `<figure class="plot"><figcaption><span class="plot-title">${escapeHtml(p.title)}</span>` +
                    `<span class="plot-source">${escapeHtml(p.source)}</span></figcaption>` +
                    `${chartSvg(p.data, p.counted, p.atLeast, p.parts)}</figure>`
            )
            .join("\n");
    }

    const charts = {
        WIDTH, LEFT, RIGHT, TOP, MAX_LABELS, MAX_LABEL_CHARS, MIN_SLOTS,
        escapeHtml, number, yTicks, shortNumber, histogramSvg, countBars, countsSvg, chartSvg, plotGridHtml,
    };
    if (typeof module !== "undefined" && module.exports) {
        module.exports = charts; // Node, for the tests
    } else {
        window.mirdataCharts = charts;
    }
})();
