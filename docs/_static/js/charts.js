// The Statistics charts: every plot as an SVG bar chart, or a chord or key
// field as a circle of fifths, drawn in the page.
// gallery.py puts each panel's plots on its plot grid (data-plots), gallery.js
// draws them with plotGridHtml. A plot is {title, source, counted, data, circle}: data
// is a grid {unit, width, counts as [start, count] pairs}, a counts field as
// [label, count] pairs, or a histogram {unit, edges, counts} (the audio durations)
// (and a combined one from combine.js has parts; it is
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
    const THIN = 3; // bars in a slot narrower than this touch, so many thin bars read as one shape
    const UNIT_NAMES = { hz: "Hz", midi: "MIDI" }; // a unit as a chart writes it; any other as stored (s, bpm, ...)
    const MAX_BINS = 25; // most bars a grid is drawn with (barWidth)
    const VALUE_UNITS = new Set(["midi"]); // grids whose bins are one value each (notes, rounded): a bar per bin
    const OTHER = "(other)";

    // The chord and key circles (circleSvg): a slice per root, fifths clockwise
    // from C at the top, and a ring per chord quality or key mode, inside out.
    // Each quality or mode goes on its ring (of), any other on "other", and a
    // label without one ("C", "C/3") on the first.
    const FIFTHS = ["C", "G", "D", "A", "E", "B", "F#", "Db", "Ab", "Eb", "Bb", "F"];
    const NATURALS = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 }; // each letter's pitch class
    const CIRCLES = {
        chords: {
            rings: ["maj", "min", "7", "maj7", "min7", "dim", "sus", "other"],
            of: {
                maj: "maj", maj6: "maj", min: "min", min6: "min",
                7: "7", 9: "7", 11: "7", 13: "7",
                maj7: "maj7", maj9: "maj7", maj11: "maj7", maj13: "maj7",
                min7: "min7", min9: "min7", min11: "min7", min13: "min7",
                dim: "dim", dim7: "dim", hdim7: "dim", sus2: "sus", sus4: "sus",
            },
        },
        keys: {
            rings: ["major", "minor", "other"],
            of: { major: "major", maj: "major", minor: "minor", min: "minor" },
        },
    };
    // A circle's size, two bar charts wide as it spans two columns (custom.css);
    // its middle, its outer radius (room left around it for the root names) and
    // its empty middle's radius
    const CIRCLE_WIDTH = 2 * WIDTH, CIRCLE_HEIGHT = 170;
    const CX = CIRCLE_WIDTH / 2, CY = CIRCLE_HEIGHT / 2, OUTER = CIRCLE_HEIGHT / 2 - 17, HOLE = 16;
    const RING_NAMES_AT = -15; // the angle the ring names are written along, over the cells: between F and C
    const FAINTEST = 0.08; // the shade of a cell used least, so it never looks unused
    const MAX_CELL_LABELS = 10; // labels a cell's hover text lists; the rest as "… and 4 more"

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
    // "60–80 bpm: 84 tracks". With several datasets, their counts too,
    // " (a: 36, b: 48)"; with one in focus, its count of the whole instead,
    // "60–80 bpm: a 36 of 84 tracks".
    function barTip(what, count, counted, pieces) {
        const total = `${GROUPED.format(count)} ${counted}`;
        if (pieces && pieces.at(-1).rest) return `${what}: ${pieces[0].name} ${GROUPED.format(pieces[0].count)} of ${total}`;
        if (!pieces || pieces.length < 2) return `${what}: ${total}`;
        const named = pieces.filter((p) => p.count).map((p) => `${p.name}: ${GROUPED.format(p.count)}`);
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
    // (combine-rest). Bars in a slot narrower than THIN touch (a grid's many
    // bins), so many thin ones read as one shape.
    // Returns the SVG pieces (without the closing tag), the slot width and the y of the axis.
    function barsSvg(counts, tips, pieces = null) {
        const plotWidth = WIDTH - LEFT - RIGHT, plotHeight = HEIGHT - TOP - BOTTOM;
        const slot = plotWidth / counts.length;
        const barWidth = plotWidth / Math.max(counts.length, MIN_SLOTS);
        const highest = Math.max(...counts) || 1;
        const base = TOP + plotHeight;
        const gapless = slot < THIN;
        const gap = gapless ? 0 : 1;

        const out = [`<svg class="plot-svg${gapless ? " plot-gapless" : ""}" viewBox="0 0 ${WIDTH} ${HEIGHT}" role="img">`];
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
                    bar += rect(pieceClass(piece), bottom, height);
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

    // The class of a piece of a bar or a circle's cell (stacks): its dataset's
    // colour, grey for the others, pale grey for the rest of a dataset in focus
    function pieceClass(piece) {
        const colour = piece.rest ? "rest" : piece.slot == null ? "other" : `c${piece.slot}`;
        return `plot-piece combine-${colour}`;
    }

    // One histogram {unit, edges, counts} as an SVG bar chart.
    //
    // The x axis shows up to MAX_TICKS edge values and the unit. Hovering a bar
    // shows its range and count. parts (combine.js, each on the same edges)
    // stack the bars by dataset, or show one dataset in focus (its name).
    function histogramSvg(hist, counted, parts = null, focus = null) {
        const { edges, counts } = hist;
        const unit = UNIT_NAMES[hist.unit] || hist.unit;
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
        out.push(unitSvg(unit, base));
        out.push("</svg>");
        return out.join("");
    }

    // The unit written under the x axis (at base, barsSvg's), in the middle
    function unitSvg(unit, base) {
        return (
            `<text class="plot-unit" x="${(LEFT + (WIDTH - LEFT - RIGHT) / 2).toFixed(1)}" y="${base + 20}"` +
            ` text-anchor="middle">${escapeHtml(unit)}</text>`
        );
    }

    // One grid {unit, width, counts as [start, count] pairs, lowest first} as an
    // SVG bar chart: its bins merged into bars barWidth wide, from the bar
    // holding the lowest bin to the one holding the highest (barStarts).
    //
    // A bar is a range, "60–70 bpm", with round numbers at its edges
    // (numberStep); in a grid of VALUE_UNITS it is one value, "64 MIDI", named
    // under its middle. Hovering a bar shows it and its count. parts
    // (combine.js, each a dataset's own grid) stack the bars by dataset, or show
    // one dataset in focus (its name), on the same bars.
    function gridSvg(grid, counted, parts = null, focus = null) {
        const unit = UNIT_NAMES[grid.unit] || grid.unit;
        const values = VALUE_UNITS.has(grid.unit);
        const width = values ? grid.width : barWidth(grid);
        const starts = barStarts(grid, width);
        const counts = barCounts(grid, starts, width);
        const pieces = parts && stacks(parts, (data) => barCounts(data, starts, width), counts, focus);
        const name = (start) => (values ? number(start) : `${number(start)}–${number(start + width)}`);
        const tips = starts.map((start, i) => barTip(`${name(start)} ${unit}`, counts[i], counted, pieces && pieces[i]));
        const { out, slot, base } = barsSvg(counts, tips, pieces);
        // [number, where on the axis, in bars]: a value bar's middle, or every edge of the range bars
        const marks = values
            ? starts.map((start, i) => [start, i + 0.5])
            : [...starts, starts.at(-1) + width].map((edge, i) => [edge, i]);
        const step = numberStep(marks.map(([value]) => Array.from(number(value))), slot, width);
        for (const [value, at] of marks) {
            if (Math.round(value / width) % Math.round(step / width)) continue; // the hover still has it
            out.push(
                `<text class="plot-label" x="${(LEFT + at * slot).toFixed(1)}" y="${base + 10}"` +
                    ` text-anchor="middle">${number(value)}</text>`
            );
        }
        out.push(unitSvg(unit, base));
        out.push("</svg>");
        return out.join("");
    }

    // The width a grid's bins are merged into bars of: the Freedman-Diaconis
    // width (2 × IQR / n^⅓, the quartiles read off the counts) rounded to the
    // closest of barWidths, or, when wider, the narrowest of those giving at
    // most MAX_BINS bars. e.g. guitarset tempo on its 1 bpm grid: IQR 98–141
    // bpm, 360 tracks → 12.1 → 10 bpm, 15 bars.
    function barWidth(grid) {
        const total = grid.counts.reduce((sum, [, count]) => sum + count, 0);
        const fd = (2 * (quartile(grid, 0.75, total) - quartile(grid, 0.25, total))) / Math.cbrt(total);
        const closest = closestWidth(grid, fd);
        const lowest = grid.counts[0][0], highest = grid.counts.at(-1)[0];
        for (const width of barWidths(grid)) {
            if (width >= closest && barOf(highest, width) - barOf(lowest, width) + 1 <= MAX_BINS) return width;
        }
    }

    // The widths a grid's bins can be merged into, narrowest first: its own
    // width times 1, 2 or 5 × 10ⁿ, so a bar is always a whole number of bins
    function* barWidths(grid) {
        for (let e = 0; ; e++) for (const m of [1, 2, 5]) yield grid.width * m * 10 ** e;
    }

    // The width of barWidths closest to x in ratio: 12.1 → 10, 16 → 20; the grid's own when x is smaller
    function closestWidth(grid, x) {
        let best = grid.width;
        for (const width of barWidths(grid)) {
            if (Math.abs(Math.log(width / x)) < Math.abs(Math.log(best / x))) best = width;
            if (width >= x) return best;
        }
    }

    // The start of the bin where a grid's running count reaches share of its total (0.25: the lower quartile)
    function quartile(grid, share, total) {
        let sum = 0;
        for (const [start, count] of grid.counts) {
            sum += count;
            if (sum >= share * total) return start;
        }
    }

    // Which bar, width wide, holds the bin starting at start (1e-9: float noise)
    const barOf = (start, width) => Math.floor(start / width + 1e-9);

    // The starts of a grid's bars, width wide, from the bar holding its lowest
    // bin to the one holding its highest, the empty bars too, so they are
    // evenly spaced along the axis
    function barStarts(grid, width) {
        const first = barOf(grid.counts[0][0], width), last = barOf(grid.counts.at(-1)[0], width);
        return Array.from({ length: last - first + 1 }, (_, i) => (first + i) * width);
    }

    // A grid's count in each bar starting at starts (barStarts, width wide):
    // the counts of the bins it holds added up, 0 in an empty bar
    function barCounts(grid, starts, width) {
        const own = new Map();
        for (const [start, count] of grid.counts) {
            const bar = barOf(start, width);
            own.set(bar, (own.get(bar) || 0) + count);
        }
        return starts.map((start) => own.get(barOf(start, width)) || 0);
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
            .map(([label, count]) => [String(label), count])
            .sort((a, b) => b[1] - a[1]); // stable: a tie keeps the stored order
        const rest = named.slice(MAX_LABELS).reduce((sum, [, count]) => sum + count, 0);
        return named.slice(0, MAX_LABELS).concat(rest ? [[OTHER, rest]] : []);
    }

    // Which number labels a chart writes when they do not all fit under their
    // bars, one number per bar, width apart (a grid's width; 1 for a counts
    // field's numbers): the multiples of the smallest step of 1, 2 or 5 × 10ⁿ
    // bars that puts them far enough apart, e.g. 40, 50, 60 MIDI, or 1,000,
    // 2,000 Hz on a 10 Hz grid
    function numberStep(labels, slot, width = 1) {
        const widest = Math.max(...labels.map((chars) => chars.length)) * CHAR_WIDTH;
        for (let e = 0; ; e++) {
            for (const m of [1, 2, 5]) {
                const bars = m * 10 ** e;
                if (bars * slot >= widest + 2) return bars * width;
            }
        }
    }

    // One counts field ([label, count] pairs) as an SVG bar chart, the same chart as a histogram.
    //
    // Every bar has its label under it: flat when every label fits under its
    // bar, else tilted, smaller and cut to MAX_LABEL_CHARS; numbers that do not
    // fit (a wide polyphony) are written flat, only every few (numberStep).
    // Hovering a bar shows the whole label and its count. parts (combine.js,
    // each a dataset's own pairs) stack the bars by dataset, or show one
    // dataset in focus (its name).
    function countsSvg(pairs, counted, parts = null, focus = null) {
        const bars = countBars(pairs);
        const pieces = parts && stacks(parts, (data) => countsUnder(bars, data), bars.map(([, count]) => count), focus);
        const tips = bars.map(([label, count], i) => barTip(String(label), count, counted, pieces && pieces[i]));
        const { out, slot, base } = barsSvg(
            bars.map(([, count]) => count),
            tips,
            pieces
        );
        const labels = bars.map(([label]) => Array.from(String(label))); // characters, as Python counts them
        const flat = labels.every((chars) => chars.length * CHAR_WIDTH <= slot);
        const numbers = bars.every(([label]) => typeof label === "number");
        const step = numbers && !flat ? numberStep(labels, slot) : 1;
        labels.forEach((chars, i) => {
            const x = (LEFT + (i + 0.5) * slot).toFixed(1);
            const label = chars.join("");
            if (step > 1 && bars[i][0] % step) return; // the hover still has it
            if (flat || numbers) {
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

    // A chord or key field ([label, count] pairs) as a circle of fifths
    // (CIRCLES[circle]): a cell per root (slice) and quality or mode (ring),
    // shaded by its count, linear, the most used cell darkest and a used one
    // never fainter than FAINTEST. A cell no label falls in is left blank. The
    // rings have equal areas (ringEdges), so only the shade says how much; each
    // ring's name and share are written over it (RING_NAMES_AT). Labels
    // without a root (N, X) are written in the middle.
    //
    // Hovering a cell shows its count and its labels, most common first.
    // parts (combine.js, each a dataset's own pairs) split each cell's arc by
    // dataset, or show one dataset in focus (its name), as the bars' stacks.
    function circleSvg(pairs, circle, counted, parts = null, focus = null) {
        const { rings } = CIRCLES[circle];
        const edges = ringEdges(rings.length);
        const { cells, rootless } = circleCells(pairs, circle);
        const total = pairs.reduce((sum, [, count]) => sum + count, 0);
        const highest = Math.max(...cells.map((cell) => cell.count), 1);
        const counts = cells.map((cell) => cell.count);
        const pieces = parts
            ? stacks(parts, (data) => countsIn(cells, data, circle), counts, focus)
            : counts.map((count) => [{ slot: 0, count }]); // one dataset: its colour, as a combination's first
        // each dataset's own label counts, for the hover text of a combined circle
        const own = parts && parts.length > 1 ? parts.map(({ name, data }) => ({ name, counts: new Map(data.map(([label, count]) => [String(label), count])) })) : null;

        const out = [`<svg class="plot-svg plot-circle-svg" viewBox="0 0 ${CIRCLE_WIDTH} ${CIRCLE_HEIGHT}" role="img">`];
        for (let slice = 0; slice < FIFTHS.length; slice++) {
            for (let ring = 0; ring < rings.length; ring++) {
                out.push(`<path class="circle-cell" d="${sectorPath(edges[ring], edges[ring + 1], slice * 30 - 15, slice * 30 + 15)}"/>`);
            }
            const [x, y] = pointAt(OUTER + 7, slice * 30);
            out.push(
                `<text class="plot-label circle-root" x="${x}" y="${y}" text-anchor="middle"` +
                    ` dominant-baseline="middle">${FIFTHS[slice]}</text>`
            );
        }
        cells.forEach((cell, i) => {
            const shade = Math.max(FAINTEST, cell.count / highest).toFixed(3);
            let start = cell.slice * 30 - 15;
            const drawn = pieces[i]
                .filter((piece) => piece.count)
                .map((piece) => {
                    const end = start + (30 * piece.count) / cell.count;
                    const path = sectorPath(edges[cell.ring], edges[cell.ring + 1], start, end);
                    start = end;
                    return `<path class="${pieceClass(piece)}" fill-opacity="${shade}" d="${path}"/>`;
                })
                .join("");
            const name = `${FIFTHS[cell.slice]} ${rings[cell.ring]} (${percent(cell.count, total)})`;
            const tip = [barTip(name, cell.count, counted, pieces[i]), ...labelLines(cell.labels, own)].join("\n");
            out.push(`<g><title>${escapeHtml(tip)}</title>${drawn}</g>`);
        });
        // each ring's name and share, over its cells along RING_NAMES_AT
        rings.forEach((ring, i) => {
            const share = percent(cells.filter((cell) => cell.ring === i).reduce((sum, cell) => sum + cell.count, 0), total);
            const [x, y] = pointAt((edges[i] + edges[i + 1]) / 2, RING_NAMES_AT);
            out.push(
                `<text class="plot-label circle-ring" x="${x}" y="${y}" text-anchor="middle"` +
                    ` dominant-baseline="middle">${escapeHtml(ring)} ${share}</text>`
            );
        });
        // the labels without a root: two written in the middle ("+3 more"), all in its hover text
        if (rootless.length) {
            const rootlessTotal = rootless.reduce((sum, [, count]) => sum + count, 0);
            const tip = [`No root: ${GROUPED.format(rootlessTotal)} ${counted}`, ...labelLines(rootless, own)].join("\n");
            const lines = rootless.slice(0, 2).map(([label, count]) => `${label} ${percent(count, total)}`);
            if (rootless.length > 2) lines.push(`+${rootless.length - 2} more`);
            const texts = lines.map((line, i) => {
                const y = (CY + (i - (lines.length - 1) / 2) * 9).toFixed(1);
                return `<text class="plot-label circle-middle" x="${CX}" y="${y}" text-anchor="middle" dominant-baseline="middle">${escapeHtml(line)}</text>`;
            });
            out.push(`<g><title>${escapeHtml(tip)}</title><circle class="plot-hit" cx="${CX}" cy="${CY}" r="${HOLE}"/>${texts.join("")}</g>`);
        }
        out.push("</svg>");
        return out.join("");
    }

    // A label's root and quality (a key's mode): "A:min7(9)/5" → ["A", "min7"],
    // "C/3" → ["C", null] (no quality written), "C:(1,5)" → ["C", ""] (only notes)
    function rootAndQuality(label) {
        const [root, quality] = String(label).split("/")[0].split(":");
        return [root, quality === undefined ? null : quality.split("(")[0]];
    }

    // A root's pitch class, 0 (C) to 11: its letter moved a semitone by each # or
    // b, "Cb" → 11; null when it is not a note (N, X)
    function pitchClass(root) {
        const match = /^([A-G])([#b]*)$/.exec(root);
        if (!match) return null;
        const moves = Array.from(match[2]).reduce((sum, sign) => sum + (sign === "#" ? 1 : -1), 0);
        return (((NATURALS[match[1]] + moves) % 12) + 12) % 12;
    }

    // The [slice, ring] a label falls in on a circle (CIRCLES[circle]), or null when it has no root
    function cellOf(label, circle) {
        const [root, quality] = rootAndQuality(label);
        const pc = pitchClass(root);
        if (pc === null) return null;
        const { rings, of } = CIRCLES[circle];
        const slice = FIFTHS.findIndex((name) => pitchClass(name) === pc);
        return [slice, quality === null ? 0 : rings.indexOf(of[quality] || "other")];
    }

    // A circle's used cells, each {slice, ring, count, labels} (labels as
    // [label, count] pairs, most common first), and the labels with no root
    function circleCells(pairs, circle) {
        const cells = new Map(), rootless = [];
        for (const [label, count] of pairs) {
            const cell = cellOf(label, circle);
            if (!cell) {
                rootless.push([String(label), count]);
                continue;
            }
            const key = cell.join();
            if (!cells.has(key)) cells.set(key, { slice: cell[0], ring: cell[1], count: 0, labels: [] });
            cells.get(key).count += count;
            cells.get(key).labels.push([String(label), count]);
        }
        const mostFirst = (a, b) => b[1] - a[1];
        for (const cell of cells.values()) cell.labels.sort(mostFirst);
        return { cells: [...cells.values()], rootless: rootless.sort(mostFirst) };
    }

    // One dataset's count in each cell (circleCells' cells), from its own pairs
    function countsIn(cells, pairs, circle) {
        const own = new Map();
        for (const [label, count] of pairs) {
            const cell = cellOf(label, circle);
            if (cell) own.set(cell.join(), (own.get(cell.join()) || 0) + count);
        }
        return cells.map((cell) => own.get([cell.slice, cell.ring].join()) || 0);
    }

    // The radii of a circle's ring edges, inside out, from HOLE to OUTER: rings of equal area
    function ringEdges(n) {
        return Array.from({ length: n + 1 }, (_, i) => Math.sqrt(HOLE ** 2 + (i * (OUTER ** 2 - HOLE ** 2)) / n));
    }

    // The point at radius r from the circle's middle, at angle degrees clockwise from the top
    function pointAt(r, angle) {
        const a = (angle * Math.PI) / 180;
        return [(CX + r * Math.sin(a)).toFixed(2), (CY - r * Math.cos(a)).toFixed(2)];
    }

    // The path of a ring's piece: between radii r0 and r1, from angle a0 to a1 (clockwise from the top)
    function sectorPath(r0, r1, a0, a1) {
        const [p, q, s, t] = [pointAt(r1, a0), pointAt(r1, a1), pointAt(r0, a1), pointAt(r0, a0)];
        return `M${p} A${r1} ${r1} 0 0 1 ${q} L${s} A${r0} ${r0} 0 0 0 ${t}Z`;
    }

    // A count's share of total, as a circle writes it: 49%, 1.5%, 0.4%, <0.1%
    function percent(count, total) {
        const share = (100 * count) / total;
        if (!count) return "0%";
        return share >= 10 ? `${Math.round(share)}%` : share >= 0.1 ? `${share.toFixed(1)}%` : "<0.1%";
    }

    // Labels for a hover text, one a line, "G:7: 80", at most MAX_CELL_LABELS,
    // then "… and 4 more"; with each dataset's own counts (own, a combined
    // circle's) that have the label, "G:7: 80 (rwc_popular: 50, guitarset: 30)"
    function labelLines(labels, own = null) {
        const lines = labels.slice(0, MAX_CELL_LABELS).map(([label, count]) => {
            const line = `${label}: ${GROUPED.format(count)}`;
            if (!own) return line;
            const each = own.filter((d) => d.counts.get(label)).map((d) => `${d.name}: ${GROUPED.format(d.counts.get(label))}`);
            return `${line} (${each.join(", ")})`;
        });
        const more = labels.length - MAX_CELL_LABELS;
        return more > 0 ? [...lines, `… and ${more} more`] : lines;
    }

    // A plot's chart: a circle when gallery.py names its rings (circle), else
    // by the shape of its data: counts pairs, a grid (it has a width), or a histogram
    function chartSvg(data, counted, parts, focus, circle) {
        if (circle) return circleSvg(data, circle, counted, parts, focus);
        if (Array.isArray(data)) return countsSvg(data, counted, parts, focus);
        return "width" in data ? gridSvg(data, counted, parts, focus) : histogramSvg(data, counted, parts, focus);
    }

    // The figures of a plot grid: each plot's title, its source and its chart,
    // with focus (a dataset's name, Combine mode) showing that dataset's part
    // of every combined plot.
    function plotGridHtml(plots, focus = null) {
        return plots
            .map(
                (p) =>
                    // data-type: the annotation type ("" for the audio's), for gallery.js's type focus
                    `<figure class="plot${p.circle ? " plot-circle" : ""}" data-type="${escapeHtml(p.type || "")}">` +
                    `<figcaption><span class="plot-title">${escapeHtml(p.title)}</span>` +
                    `<span class="plot-source">${escapeHtml(p.source)}</span>${picksHtml(p)}</figcaption>` +
                    `${chartSvg(p.data, p.counted, p.parts, focus, p.circle)}</figure>`
            )
            .join("\n");
    }

    // A combined plot's buttons (combine.js, choices): for each dataset with
    // several properties it could add to the plot, one per property, the one it
    // adds pressed; a click swaps it in (gallery.js)
    function picksHtml(p) {
        if (!p.choices) return "";
        const sets = p.choices.map(({ name, props, pick }) => {
            const buttons = props.map(
                (prop) =>
                    `<button class="plot-pick" data-key="${escapeHtml(p.pickKey)}" data-name="${escapeHtml(name)}"` +
                    ` data-prop="${escapeHtml(prop)}" aria-pressed="${prop === pick}">${escapeHtml(prop)}</button>`
            );
            return `<span class="plot-pick-set">${escapeHtml(name)}: ${buttons.join("")}</span>`;
        });
        return `<span class="plot-picks">${sets.join("")}</span>`;
    }

    const charts = {
        WIDTH, LEFT, RIGHT, TOP, MAX_LABELS, MAX_LABEL_CHARS, MIN_SLOTS,
        escapeHtml, number, yTicks, shortNumber, histogramSvg, gridSvg, countBars, countsSvg, circleSvg, cellOf, chartSvg, plotGridHtml,
    };
    if (typeof module !== "undefined" && module.exports) {
        module.exports = charts; // Node, for the tests
    } else {
        window.mirdataCharts = charts;
    }
})();
