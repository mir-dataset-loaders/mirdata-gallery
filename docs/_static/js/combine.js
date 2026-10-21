// Combine mode: the panel of several datasets together. gallery.js builds the
// panel; these functions work out its text from each card's facts (gallery.py,
// combine_facts: tracks, seconds, sample_rate, tasks, notes). Every function
// returns plain values, so tests/combine.test.js runs in Node.
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

    const combine = { glanceRows, namedNotes };
    if (typeof module !== "undefined" && module.exports) {
        module.exports = combine; // Node, for the tests
    } else {
        window.mirdataCombine = combine;
    }
})();
