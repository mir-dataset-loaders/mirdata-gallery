// The Statistics charts: every plot as an SVG bar chart, drawn in the page.
// gallery.py puts each panel's plots on its plot grid (data-plots), gallery.js
// draws them with plotGridHtml. A plot is {title, source, counted, data}: data
// is a histogram {unit, edges, counts} or a counts field as [label, count] pairs.
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

    // The part every chart shares: one bar per count, the x axis, and the y ticks
    // (yTicks), each a grid line behind the bars and a number; hovering shows the
    // exact counts.
    //
    // Each bar has an equal slot of the x axis and sits in its middle. With fewer
    // than MIN_SLOTS bars, a bar keeps the width it has in a chart of MIN_SLOTS
    // bars, so a few bars are spread out instead of filling the chart. The
    // tallest bar reaches the top.
    // Returns the SVG pieces (without the closing tag), the slot width and the y of the axis.
    function barsSvg(counts, tips) {
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
            const height = (plotHeight * count) / highest;
            out.push(
                `<g><title>${escapeHtml(tips[i])}</title>` +
                    `<rect class="plot-hit" x="${x.toFixed(1)}" y="${TOP}" width="${slot.toFixed(1)}" height="${plotHeight}"/>` +
                    `<rect class="plot-bar" x="${(barX + 0.5).toFixed(1)}" y="${(base - height).toFixed(1)}"` +
                    ` width="${Math.max(barWidth - 1, 0.5).toFixed(1)}" height="${height.toFixed(1)}"/></g>`
            );
        });
        out.push(`<line class="plot-axis" x1="${LEFT}" y1="${base}" x2="${WIDTH - RIGHT}" y2="${base}"/>`);
        return { out, slot, base };
    }

    // One histogram {unit, edges, counts} as an SVG bar chart.
    //
    // The x axis shows up to MAX_TICKS edge values and the unit. Hovering a bar
    // shows its range and count.
    function histogramSvg(hist, counted) {
        const { edges, counts } = hist;
        const unit = UNIT_LABELS[hist.unit] ?? hist.unit;
        const plotWidth = WIDTH - LEFT - RIGHT;
        const tips = counts.map(
            (count, i) => `${number(edges[i])}–${number(edges[i + 1])} ${unit}: ${GROUPED.format(count)} ${counted}`
        );
        const { out, slot, base } = barsSvg(counts, tips);
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
    // the whole label and its count.
    function countsSvg(pairs, counted) {
        const bars = countBars(pairs);
        const tips = bars.map(([label, count]) => `${label}: ${GROUPED.format(count)} ${counted}`);
        const { out, slot, base } = barsSvg(
            bars.map(([, count]) => count),
            tips
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

    function chartSvg(data, counted) {
        return Array.isArray(data) ? countsSvg(data, counted) : histogramSvg(data, counted);
    }

    // The figures of a plot grid: each plot's title, its source and its chart.
    function plotGridHtml(plots) {
        return plots
            .map(
                (p) =>
                    `<figure class="plot"><figcaption><span class="plot-title">${escapeHtml(p.title)}</span>` +
                    `<span class="plot-source">${escapeHtml(p.source)}</span></figcaption>` +
                    `${chartSvg(p.data, p.counted)}</figure>`
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
