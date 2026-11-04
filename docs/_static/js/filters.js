// The filters in the left sidebar: the search, the AND / OR switches and the
// pills, and the datasets they let through (applyFilters).
window.mirdataFilters = function (shared) {
    const { cardData, sidebar, selectCard } = shared;

    // Collect unique annotation types, tasks and licenses with counts
    const annCounts = {};
    const taskCounts = {};
    const licenseCounts = {};
    cardData.forEach((d) => {
        d.annotations.forEach((a) => (annCounts[a] = (annCounts[a] || 0) + 1));
        d.facts.tasks.forEach((t) => (taskCounts[t] = (taskCounts[t] || 0) + 1));
        d.licenses.forEach((l) => (licenseCounts[l] = (licenseCounts[l] || 0) + 1));
    });

    // State tracking
    const state = {
        selectedAnnotations: new Set(),
        annMatch: "all", // a dataset needs "all" of the selected types (AND), or "any" of them (OR)
        selectedTasks: new Set(),
        taskMatch: "any", // the same for the selected tasks
        selectedLicenses: new Set(),
        licMatch: "any", // the same for the selected licenses (OR: a dataset has one license for now)
        searchQuery: "",
    };

    // Search Input
    const search = document.createElement("input");
    search.type = "text";
    search.placeholder = "Search dataset name...";
    search.className = "filter-search";
    search.addEventListener("input", (e) => {
        state.searchQuery = e.target.value.toLowerCase().trim();
        applyFilters();
    });
    sidebar.appendChild(search);

    // Results Counter & Reset
    const headerBar = document.createElement("div");
    headerBar.className = "filter-header-bar";
    const counter = document.createElement("span");
    counter.className = "filter-counter";
    const resetBtn = document.createElement("button");
    resetBtn.textContent = "Clear filters";
    resetBtn.className = "filter-reset-btn";
    resetBtn.addEventListener("click", () => {
        state.selectedAnnotations.clear();
        state.selectedTasks.clear();
        state.selectedLicenses.clear();
        state.searchQuery = "";
        search.value = "";
        sidebar.querySelectorAll(".filter-pill.active").forEach((p) => p.classList.remove("active"));
        pillRedraws.forEach((draw) => draw());
        applyFilters();
    });
    headerBar.appendChild(counter);
    headerBar.appendChild(resetBtn);
    sidebar.appendChild(headerBar);

    // A filter section's title, with an AND / OR switch beside it that sets
    // state[matchKey]: a dataset needs all of the selected pills, or any
    function filterHead(title, matchKey, what) {
        const head = document.createElement("div");
        head.className = "filter-section-head";
        const h4 = document.createElement("h4");
        h4.textContent = title;
        const options = document.createElement("div");
        options.className = "match-options";
        [
            ["all", "AND", `Intersection: datasets with all the selected ${what}`],
            ["any", "OR", `Union: datasets with at least one of the selected ${what}`],
        ].forEach(([mode, text, hint]) => {
            const btn = document.createElement("button");
            btn.textContent = text;
            btn.dataset.tip = hint; // shown at once on hover, as the plot bars' (panel.js)
            btn.setAttribute("aria-label", `${text}: ${hint}`);
            btn.setAttribute("aria-pressed", String(mode === state[matchKey]));
            btn.addEventListener("click", () => {
                state[matchKey] = mode;
                options.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b === btn)));
                applyFilters();
            });
            options.appendChild(btn);
        });
        head.append(h4, options);
        return head;
    }

    // A pill group collapsed to its first rows and its selected pills, with a
    // button to show the rest. The rows come from the layout, so they are found
    // again when the group's width or the font changes.
    const COLLAPSED_ROWS = 4;
    const pillRedraws = [];
    function collapsePills(group) {
        const pills = [...group.querySelectorAll(".filter-pill")];
        const more = document.createElement("button");
        more.className = "filter-more-btn";
        group.appendChild(more);
        let open = false;
        function draw() {
            pills.forEach((p) => p.classList.remove("pill-hidden"));
            const tops = pills.map((p) => p.offsetTop);
            const rows = [...new Set(tops)];
            pills.forEach((p, i) => {
                const past = tops[i] > rows[COLLAPSED_ROWS - 1];
                p.classList.toggle("pill-hidden", !open && past && !p.classList.contains("active"));
            });
            more.hidden = rows.length <= COLLAPSED_ROWS;
            more.textContent = open ? "Show fewer" : `Show all ${pills.length}`;
            more.setAttribute("aria-expanded", String(open));
        }
        // a pill's own click handler has run by now: its active class is up to date
        group.addEventListener("click", (e) => {
            if (e.target === more) open = !open;
            draw();
        });
        let width = 0;
        new ResizeObserver(() => {
            if (group.clientWidth !== width) {
                width = group.clientWidth;
                draw();
            }
        }).observe(group);
        document.fonts.ready.then(draw);
        pillRedraws.push(draw);
    }

    // Annotation Filters Section
    sidebar.appendChild(filterHead("ANNOTATION TYPES", "annMatch", "types"));

    const annContainer = document.createElement("div");
    annContainer.className = "filter-pills-group";

    Object.keys(annCounts)
        .sort()
        .forEach((ann) => {
            const pill = document.createElement("button");
            pill.className = "filter-pill";
            pill.setAttribute("data-ann", ann); // Tag sidebar filter pills
            pill.textContent = ann;
            pill.addEventListener("click", () => {
                if (state.selectedAnnotations.has(ann)) {
                    state.selectedAnnotations.delete(ann);
                    pill.classList.remove("active");
                } else {
                    state.selectedAnnotations.add(ann);
                    pill.classList.add("active");
                }
                applyFilters();
            });
            annContainer.appendChild(pill);
        });
    sidebar.appendChild(annContainer);

    // Task Filters Section: the most used first, as only the first rows show
    const taskHead = filterHead("TASKS", "taskMatch", "tasks");
    taskHead.style.marginTop = "20px";
    sidebar.appendChild(taskHead);

    const taskContainer = document.createElement("div");
    taskContainer.className = "filter-pills-group";

    Object.keys(taskCounts)
        .sort((a, b) => taskCounts[b] - taskCounts[a] || a.localeCompare(b))
        .forEach((task) => {
            const pill = document.createElement("button");
            pill.className = "filter-pill";
            pill.textContent = task;
            pill.addEventListener("click", () => {
                if (state.selectedTasks.has(task)) {
                    state.selectedTasks.delete(task);
                    pill.classList.remove("active");
                } else {
                    state.selectedTasks.add(task);
                    pill.classList.add("active");
                }
                applyFilters();
            });
            taskContainer.appendChild(pill);
        });
    collapsePills(taskContainer);
    sidebar.appendChild(taskContainer);

    // License Filters Section: the most used first, as only the first rows show
    const licHead = filterHead("LICENSES", "licMatch", "licenses");
    licHead.style.marginTop = "20px";
    sidebar.appendChild(licHead);

    const licContainer = document.createElement("div");
    licContainer.className = "filter-pills-group";

    Object.keys(licenseCounts)
        .sort((a, b) => licenseCounts[b] - licenseCounts[a] || a.localeCompare(b))
        .forEach((lic) => {
            const pill = document.createElement("button");
            pill.className = "filter-pill";
            pill.textContent = lic;
            pill.addEventListener("click", () => {
                if (state.selectedLicenses.has(lic)) {
                    state.selectedLicenses.delete(lic);
                    pill.classList.remove("active");
                } else {
                    state.selectedLicenses.add(lic);
                    pill.classList.add("active");
                }
                applyFilters();
            });
            licContainer.appendChild(pill);
        });
    collapsePills(licContainer);
    sidebar.appendChild(licContainer);

    // Whether a dataset passes one pill filter: nothing selected, or any / all
    // of the selected pills (mode) among its own values
    function matchesPills(selected, values, mode) {
        const has = (v) => values.includes(v);
        return selected.size === 0 || (mode === "all" ? [...selected].every(has) : [...selected].some(has));
    }

    // firstPage: false keeps the page on show (Combine switching off)
    function applyFilters(firstPage = true) {
        shared.matched = cardData.filter((item) => {
            const matchesSearch =
                !state.searchQuery ||
                item.title.toLowerCase().includes(state.searchQuery) ||
                item.annotations.some((a) => a.toLowerCase().includes(state.searchQuery)) ||
                item.facts.tasks.some((t) => t.toLowerCase().includes(state.searchQuery));
            const matchesAnn = matchesPills(state.selectedAnnotations, item.annotations, state.annMatch);
            const matchesTask = matchesPills(state.selectedTasks, item.facts.tasks, state.taskMatch);
            const matchesLic = matchesPills(state.selectedLicenses, item.licenses, state.licMatch);
            return matchesSearch && matchesAnn && matchesTask && matchesLic;
        });
        shared.showMatched(firstPage);
        counter.textContent = `Showing ${shared.matched.length} of ${cardData.length}`;
        // Combine mode: the combined datasets the filters let through; otherwise
        // keep the dataset on show if they let it through (on whatever page),
        // or show the first one
        if (shared.combine.on) shared.showCombination();
        else selectCard(shared.activeItem && shared.matched.includes(shared.activeItem) ? shared.activeItem : shared.matched[0] || null);
    }

    shared.applyFilters = applyFilters;
};
