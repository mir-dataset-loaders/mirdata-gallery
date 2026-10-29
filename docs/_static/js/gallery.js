document.addEventListener("DOMContentLoaded", function () {
    const gallery = document.getElementById("mirdata-gallery"); // the section of gallery.rst's title
    if (!gallery) return;

    const cards = Array.from(gallery.querySelectorAll(":scope > section"));
    if (cards.length === 0) return;

    // Helper to group licenses into clean categories (like your brainstorm mockup)
    function normalizeLicense(raw) {
        if (!raw) return "Not specified";
        const text = raw.toLowerCase();

        if (text.includes("not specified") || text.includes("couldn't find") || text.includes("unavailable")) {
            return "Not specified";
        }
        if (text.includes("mit")) {
            return "MIT";
        }
        if (text.includes("zero") || text.includes("cc0") || text.includes("public domain")) {
            return "CC0 (Public Domain)";
        }
        if (text.includes("no derivatives") || text.includes("by-nc-nd")) {
            return "CC BY-NC-ND 4.0";
        }
        if (text.includes("non-commercial") || text.includes("non commercial") || text.includes("noncommercial")) {
            if (text.includes("share alike") || text.includes("sharealike") || text.includes("sa")) {
                return "CC BY-NC-SA 4.0";
            }
            return "CC BY-NC 4.0";
        }
        if (text.includes("share alike") || text.includes("sharealike") || text.includes("by-sa")) {
            return "CC BY-SA 4.0";
        }
        if (text.includes("creative commons") || text.includes("cc by")) {
            return "CC BY 4.0";
        }
        if (text.includes("free of charge") || text.includes("research purposes") || text.includes("pledge") || text.includes("copyright") || text.includes("custom")) {
            return "Custom / Research only";
        }
        return "Other";
    }

    // 1. Read the annotation tags and the license from each panel's "At a glance" box
    const cardData = cards.map((card) => {
        const annotations = Array.from(card.querySelectorAll(".glance-tags code")).map((el) =>
            el.getAttribute("data-ann")
        );

        // FIXME: the keyword guess mislabels about 10 licenses (e.g. "submitted" -> MIT)
        const licenseCell = card.querySelector(".glance-value[data-license]");
        const rawLicense = licenseCell ? licenseCell.getAttribute("data-license") : "";
        const license = normalizeLicense(rawLicense);
        if (licenseCell && rawLicense) licenseCell.textContent = license;
        const h2 = card.querySelector("h2");
        let title = card.id;
        if (h2) {
            const clone = h2.cloneNode(true);
            const headerlink = clone.querySelector(".headerlink");
            if (headerlink) headerlink.remove();
            title = clone.textContent.trim();
        }


        const tracksRow = Array.from(card.querySelectorAll(".glance-row")).find(
            (row) => row.querySelector(".glance-label").textContent === "Tracks"
        );
        const tracksText = tracksRow ? tracksRow.querySelector(".glance-value").textContent.trim() : "—";
        const tracks = parseInt(tracksText.replace(/,/g, ""), 10); // NaN for "—"
        // what Combine mode adds up (gallery.py, combine_facts)
        const facts = JSON.parse(card.querySelector(".panel-facts").dataset.facts);
        // the plots gallery.py put on the plot grid: drawn here (charts.js), and
        // kept for Combine mode, which also shows the combined_only ones
        const grid = card.querySelector(".plot-grid[data-plots]");
        const plots = grid ? JSON.parse(grid.dataset.plots) : [];
        if (grid) grid.innerHTML = mirdataCharts.plotGridHtml(plots.filter((p) => !p.combined_only));

        // a list, for datasets with several licenses (the label above gives one for now)
        const licenses = [license];
        return { card, title, annotations, licenses, tracksText, tracks: isNaN(tracks) ? null : tracks, facts, plots };
    });



    // 2. Collect unique annotation types and licenses with counts
    const annCounts = {};
    const licenseCounts = {};
    cardData.forEach((d) => {
        d.annotations.forEach((a) => (annCounts[a] = (annCounts[a] || 0) + 1));
        d.licenses.forEach((l) => (licenseCounts[l] = (licenseCounts[l] || 0) + 1));
    });

    // 3. State tracking
    const state = {
        selectedAnnotations: new Set(),
        annMatch: "all", // a dataset needs "all" of the selected types (AND), or "any" of them (OR)
        selectedLicenses: new Set(),
        licMatch: "any", // the same for the selected licenses (OR: a dataset has one license for now)
        searchQuery: "",
    };

    // 4. Build Layout: Container with Sidebar (Left) and Content Grid (Right)
    const container = document.createElement("div");
    container.className = "gallery-layout";
    // Column 1: Filters Sidebar (placed in the theme's left sidebar)
    const sidebar = document.createElement("aside");
    sidebar.className = "gallery-filter-sidebar";
    // Column 2: Middle List of Dataset Buttons
    const listColumn = document.createElement("div");
    listColumn.className = "gallery-datasets-list";
    // Column 3: Right Information Card Panel
    const infoColumn = document.createElement("div");
    infoColumn.className = "gallery-cards-information";

    // Search Input
    const search = document.createElement("input");
    search.type = "text";
    search.placeholder = "Search datasets...";
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
        state.selectedLicenses.clear();
        state.searchQuery = "";
        search.value = "";
        sidebar.querySelectorAll(".filter-pill.active").forEach((p) => p.classList.remove("active"));
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
            btn.dataset.tip = hint; // shown at once on hover, as the plot bars' (6. below)
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

    // License Filters Section
    const licHead = filterHead("LICENSES", "licMatch", "licenses");
    licHead.style.marginTop = "20px";
    sidebar.appendChild(licHead);

    const licContainer = document.createElement("div");
    licContainer.className = "filter-pills-group";

    Object.keys(licenseCounts)
        .sort()
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
    sidebar.appendChild(licContainer);

    // Move existing cards into the right info column and hide them
    cards.forEach((c) => {
        c.style.display = "none";
        infoColumn.appendChild(c);
    });
    // Mount Column 1 to the theme's left sidebar, and Columns 2 & 3 to main area.
    // The filters replace the sidebar's last nav, the page list; a nav before it
    // holds the header links for small screens.
    const themeSidebar = document.querySelector("#left-sidebar nav:last-of-type");
    if (themeSidebar) {
        themeSidebar.innerHTML = "";
        themeSidebar.appendChild(sidebar);
    } else {
        container.appendChild(sidebar);
    }
    container.appendChild(listColumn);
    // the bar between them, dragged to widen the list (after 5. below)
    const splitter = document.createElement("div");
    splitter.className = "gallery-splitter";
    container.appendChild(splitter);
    container.appendChild(infoColumn);
    gallery.appendChild(container);
    // Selection helper function
    let activeItem = null;
    function selectCard(item) {
        const shown = activeItem && activeItem.card.style.display !== "none" ? activeItem : null;
        if (activeItem) {
            activeItem.btn.classList.remove("active");
            activeItem.card.style.display = "none";
        }
        if (item) {
            activeItem = item;
            item.btn.classList.add("active");
            item.card.style.display = "flex";
            if (item !== shown) flashScrollbar(infoColumn); // another dataset on show (8. below)
        }
    }
    // The middle column: the number of datasets, a sort menu and the list / icon
    // switch, above a table with one row per dataset (or a tile, as icons)
    const toolbar = document.createElement("div");
    toolbar.className = "list-toolbar";
    const listCount = document.createElement("span");
    listCount.className = "list-count";
    const sortLabel = document.createElement("label");
    sortLabel.className = "list-sort";
    sortLabel.textContent = "Sort by";
    const sortSelect = document.createElement("select");
    const SORTS = {
        "Name (A–Z)": (a, b) => a.title.localeCompare(b.title),
        "Name (Z–A)": (a, b) => b.title.localeCompare(a.title),
        "Tracks (most first)": (a, b) => (b.tracks ?? -1) - (a.tracks ?? -1),
        "Tracks (fewest first)": (a, b) => (a.tracks ?? Infinity) - (b.tracks ?? Infinity),
    };
    Object.keys(SORTS).forEach((name) => {
        const option = document.createElement("option");
        option.textContent = name;
        sortSelect.appendChild(option);
    });
    sortSelect.addEventListener("change", () => {
        sortRows();
        applyFilters();
    });
    sortLabel.appendChild(sortSelect);
    const tools = document.createElement("div"); // the sort menu, then the view switch
    tools.className = "list-tools";
    tools.appendChild(sortLabel);
    toolbar.append(listCount, tools);
    listColumn.appendChild(toolbar);

    // The table: Dataset, Types (a dot per annotation type, its colour), Tracks,
    // License; custom.css wraps the dots, then drops License, as the list gets
    // narrower
    const table = document.createElement("div");
    table.className = "list-table";
    const header = document.createElement("div");
    header.className = "list-row list-header";
    [
        ["Dataset", "list-name"],
        ["Types", "list-types"],
        ["Tracks", "list-tracks"],
        ["License", "list-license"],
    ].forEach(([label, cls]) => {
        const cell = document.createElement("span");
        cell.className = cls;
        cell.textContent = label;
        header.appendChild(cell);
    });
    table.appendChild(header);
    listColumn.appendChild(table);

    // The dots' order: the coloured types by family, the darker shade first
    // (custom.css), then the silver ones A–Z
    const TYPE_ORDER = ["BeatData", "TempoData", "ChordData", "KeyData", "NoteData", "F0Data", "MultiF0Data",
        "SectionData", "LyricData", "EventData", "EventDataExtended"];
    const typeRank = (t) => (TYPE_ORDER.includes(t) ? TYPE_ORDER.indexOf(t) : TYPE_ORDER.length);

    cardData.forEach((item) => {
        const btn = document.createElement("button");
        btn.className = "dataset-item-btn list-row";
        const name = document.createElement("span");
        name.className = "dataset-item-title list-name";
        name.textContent = item.title;
        const types = document.createElement("span");
        types.className = "list-types";
        const sorted = [...item.annotations].sort((a, b) => typeRank(a) - typeRank(b) || a.localeCompare(b));
        sorted.forEach((t) => {
            const dot = document.createElement("span");
            dot.className = "ann-dot";
            dot.dataset.ann = t;
            types.appendChild(dot);
        });
        if (sorted.length) types.dataset.tip = sorted.join(", "); // shown at once on hover (6. below)
        const tracks = document.createElement("span");
        tracks.className = "list-cell list-tracks";
        tracks.textContent = item.tracksText;
        if (item.tracks !== null) {
            // "360 tracks" on an icon; the list's column header says it
            const unit = document.createElement("span");
            unit.className = "tracks-unit";
            unit.textContent = item.tracks === 1 ? " track" : " tracks";
            tracks.appendChild(unit);
        }
        const license = document.createElement("span");
        license.className = "list-cell list-license";
        license.textContent = license.title = item.licenses.join(", ");
        btn.append(name, types, tracks, license);
        btn.addEventListener("click", (e) => {
            // Cmd-click (Mac) or Ctrl-click: Combine mode's click, switching it on first
            if ((e.metaKey || e.ctrlKey) && !combine.on) {
                combineBtn.click();
                if (combine.selected.includes(item)) return; // the dataset on show: already in
            }
            if (combine.on) toggleCombined(item);
            else selectCard(item);
        });
        item.btn = btn;
        table.appendChild(btn);
    });

    function sortRows() {
        cardData.sort(SORTS[sortSelect.value]);
        cardData.forEach((item) => table.appendChild(item.btn));
    }
    sortRows();

    // The list / icon switch: the same rows, laid out as tiles by custom.css
    // (title, type dots, tracks, license). The browser remembers the choice;
    // without storage it starts as the list.
    const VIEW_KEY = "mirdata-gallery-view";
    const VIEWS = [
        ["list", "List view", '<path d="M2 4h12M2 8h12M2 12h12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'],
        ["icon", "Icon view", '<g fill="currentColor"><rect x="2" y="2" width="5" height="5" rx="1"/><rect x="9" y="2" width="5" height="5" rx="1"/>' +
            '<rect x="2" y="9" width="5" height="5" rx="1"/><rect x="9" y="9" width="5" height="5" rx="1"/></g>'],
    ];
    const viewToggle = document.createElement("div");
    viewToggle.className = "view-toggle";
    VIEWS.forEach(([view, label, icon]) => {
        const btn = document.createElement("button");
        btn.dataset.view = view;
        btn.dataset.tip = label;
        btn.setAttribute("aria-label", label);
        btn.innerHTML = `<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">${icon}</svg>`;
        btn.addEventListener("click", () => {
            setView(view);
            showPage(); // another view fits another number (5. below)
        });
        viewToggle.appendChild(btn);
    });
    tools.appendChild(viewToggle);

    function setView(view) {
        table.classList.toggle("icon-view", view === "icon");
        viewToggle.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.view === view)));
        try {
            localStorage.setItem(VIEW_KEY, view);
        } catch (e) {
            // no storage (private window, blocked): the choice lasts this visit
        }
    }
    let savedView = null;
    try {
        savedView = localStorage.getItem(VIEW_KEY);
    } catch (e) {
        // no storage: the list
    }
    setView(savedView === "icon" ? "icon" : "list");

    // Combine mode: the Combine button switches what a click on a dataset does.
    // Off, the click shows that dataset; on, it adds the dataset to the
    // combination or removes it, and the panel shows the combination
    // (combine.js works out its text). Cmd-click or Ctrl-click switches it on
    // too. A combination of one shows that dataset's own panel, and removing
    // datasets down to one switches Combine off, on that one. Filters only
    // change the list: a dataset they hide stays in the combination.
    // colours: each selected dataset's colour, given when it joins (combine.js, nextColour)
    // focus: the dataset whose part of each plot is shown (its chip's name clicked), or null: stacked
    // typeFocus: the annotation type whose plots alone are shown (7. below), or null: all
    // picks: the property a dataset adds to a combined plot, picked in the plot's sources bubble
    // (charts.js, sourcesHtml), {plot's pickKey: {dataset title: property}}; one not picked adds
    // its first (combine.js)
    // openSources: the pickKey of the plot whose sources bubble is open (showSources), or null
    const combine = { on: false, selected: [], colours: new Map(), lastClicked: null, focus: null, typeFocus: null, picks: {}, openSources: null };
    const combineBar = document.createElement("div");
    combineBar.className = "combine-bar";
    const combineBtn = document.createElement("button");
    combineBtn.className = "combine-btn";
    combineBtn.textContent = "Combine";
    combineBtn.setAttribute("aria-pressed", "false");
    const combineHint = document.createElement("span");
    const OFF_HINT = "Show several together (or ⌘/Ctrl-click)";
    combineHint.textContent = OFF_HINT;
    combineBar.append(combineBtn, combineHint);
    listColumn.insertBefore(combineBar, table);

    const combinedPanel = document.createElement("section");
    combinedPanel.className = "combined-panel";
    combinedPanel.style.display = "none";
    infoColumn.appendChild(combinedPanel);

    combineBtn.addEventListener("click", () => {
        combine.on = !combine.on;
        combineBtn.setAttribute("aria-pressed", String(combine.on));
        combineBtn.classList.toggle("active", combine.on);
        combineHint.textContent = combine.on ? "Click datasets to add or remove them" : OFF_HINT;
        combine.selected = [];
        combine.colours.clear();
        combine.focus = null;
        combine.typeFocus = null;
        combine.picks = {};
        combine.openSources = null;
        if (combine.on) {
            // the dataset on show is the first one of the combination, purple as in its panel
            if (activeItem && activeItem.card.style.display !== "none") join(activeItem);
            combine.lastClicked = null;
            showCombination();
        } else {
            // back to one dataset: the last one clicked
            const last = combine.lastClicked || activeItem;
            combinedPanel.style.display = "none";
            cardData.forEach((d) => d.btn.classList.remove("active"));
            selectCard(last);
            applyFilters(false); // the first visible one instead, if the filters hide it
            refreshStats(); // the pop-up, when open, shows that one's Statistics now
        }
    });

    // A dataset joins the combination with the first free colour, and leaves it
    // with its colour, free for the next one to join; the others keep theirs.
    // The focused one leaving takes the focus with it: the plots stack again;
    // its picks go with it too.
    function join(item) {
        combine.colours.set(item, mirdataCombine.nextColour([...combine.colours.values()]));
        combine.selected.push(item);
    }

    function leave(item) {
        combine.colours.delete(item);
        combine.selected.splice(combine.selected.indexOf(item), 1);
        if (combine.focus === item) combine.focus = null;
        for (const key in combine.picks) delete combine.picks[key][item.title];
    }

    function toggleCombined(item) {
        combine.lastClicked = item;
        if (combine.selected.includes(item)) {
            removeCombined(item);
            return;
        }
        join(item);
        showCombination();
    }

    // One left after a dataset leaves: Combine off, showing that one
    function removeCombined(item) {
        leave(item);
        if (combine.selected.length === 1) {
            combine.lastClicked = combine.selected[0];
            combineBtn.click();
        } else {
            showCombination();
        }
    }

    function showCombination() {
        const selected = combine.selected;
        if (selected.length > 1) {
            selectCard(null); // hides the dataset on show
            fillCombinedPanel(selected);
            combinedPanel.style.display = "flex";
        } else {
            // one (Combine just switched on): its own panel; none: nothing
            combinedPanel.style.display = "none";
            selectCard(selected[0] || null);
        }
        cardData.forEach((d) => d.btn.classList.toggle("active", selected.includes(d)));
    }

    // The combined panel: its title and the datasets' names, At a glance, and
    // Statistics: the datasets again (a chip each: a click on its name focuses
    // it, one more shows them all again, and × removes it; its dot is the
    // dataset's colour in the plots, so the chips are the legend), each
    // dataset's notes, and the plots pooled from theirs (combine.js), stacked
    // by dataset or showing the focused one's part
    function fillCombinedPanel(selected) {
        const escape = mirdataCharts.escapeHtml;
        const datasets = selected.map((d) => ({ name: d.title, slot: combine.colours.get(d), plots: d.plots }));
        const slots = datasets.map((d) => d.slot);
        const chips = selected
            .map((d, i) => {
                const colour = `combine-${slots[i] == null ? "other" : `c${slots[i]}`}`;
                const focused = combine.focus === d;
                return (
                    `<span class="combine-chip${focused ? ` focused ${colour}` : ""}">` +
                    `<button class="combine-name" data-index="${i}" aria-pressed="${focused}"` +
                    ` title="${focused ? "Show all datasets" : `Focus ${escape(d.title)}`}">` +
                    `<span class="combine-dot ${colour}"></span>${escape(d.title)}</button>` +
                    `<button class="combine-remove" data-index="${i}" title="Remove ${escape(d.title)}"` +
                    ` aria-label="Remove ${escape(d.title)}">×</button></span>`
                );
            })
            .join("");
        const rows = mirdataCombine
            .glanceRows(selected.map((d) => d.facts))
            .map(
                ([label, value]) =>
                    `<div class="glance-row"><span class="glance-label">${label}</span>` +
                    `<span class="glance-value">${escape(value ?? "—")}</span></div>`
            )
            .join("");
        const types = [...new Set(selected.flatMap((d) => d.annotations))].sort();
        const tags = types.map((t) => `<code data-ann="${escape(t)}">${escape(t)}</code>`).join("");
        const notes = mirdataCombine.namedNotes(selected.map((d) => ({ name: d.title, notes: d.facts.notes })));
        const plots = mirdataCombine.combinedPlots(datasets, combine.picks);
        if (!plots.length) notes.push("Nothing to plot yet.");
        combinedPanel.innerHTML =
            `<h2>${selected.length} Datasets Combined</h2>` +
            `<p class="combine-names">${selected.map((d) => escape(d.title)).join(", ")}</p>` +
            '<div class="panel-box"><div class="box-title">At a glance</div>' +
            `<div class="glance-grid">${rows}</div>` +
            `<div class="box-title">Annotation types</div><div class="glance-tags">${tags || "—"}</div></div>` +
            '<div class="panel-box"><div class="box-title">Statistics</div>' +
            `<div class="combine-chips">${chips}</div>` +
            '<p class="combine-chips-hint">Click a name to focus it in the plots</p>' +
            notes.map((text) => `<p class="stats-note">${escape(text)}</p>`).join("") +
            (plots.length ? `<div class="plot-grid">${mirdataCharts.plotGridHtml(plots, combine.focus && combine.focus.title)}</div>` : "") +
            "</div>";
        moveTips(combinedPanel);
        flashScrollbar(infoColumn);
        if (!types.includes(combine.typeFocus)) combine.typeFocus = null; // its datasets all removed
        focusType(combinedPanel, combine.typeFocus);
        addStatsButton(combinedPanel);
        showSources(combinedPanel);
        refreshStats();
    }

    // Opens the sources bubble of the plot combine.openSources names in root
    // (the combined panel, or the pop-up's copy), the others closed. One that
    // would run past its plot grid's right edge opens leftwards instead.
    function showSources(root) {
        root.querySelectorAll(".plot[data-pick-key]").forEach((fig) => {
            const open = fig.dataset.pickKey === combine.openSources;
            const bubble = fig.querySelector(".plot-sources");
            bubble.hidden = !open;
            fig.querySelector(".plot-sources-btn").setAttribute("aria-expanded", String(open));
            if (!open) return;
            bubble.classList.remove("leftwards");
            if (bubble.getBoundingClientRect().right > fig.closest(".plot-grid").getBoundingClientRect().right) {
                bubble.classList.add("leftwards");
            }
        });
    }

    // The open sources bubble closes on a click anywhere outside it, or Esc
    function closeSources() {
        combine.openSources = null;
        showSources(combinedPanel);
        refreshStats();
    }
    document.addEventListener("pointerdown", (e) => {
        if (combine.openSources !== null && !e.target.closest(".plot-sources, .plot-sources-btn")) closeSources();
    });
    document.addEventListener("keydown", (e) => {
        if (e.key !== "Escape" || combine.openSources === null) return;
        e.preventDefault(); // just the bubble, not the pop-up around it too
        closeSources();
    });

    // A click in the combination's Statistics, on its panel or in the pop-up (9. below)
    function onCombinedClick(e) {
        // a plot's sources button: its bubble opens, or closes
        const sources = e.target.closest(".plot-sources-btn");
        if (sources) {
            const key = sources.closest(".plot").dataset.pickKey;
            combine.openSources = combine.openSources === key ? null : key;
            showSources(combinedPanel);
            refreshStats();
            return;
        }
        // a property's button in the bubble: that dataset adds it to the plot
        const pick = e.target.closest(".plot-pick");
        if (pick) {
            const { key, name, prop } = pick.dataset;
            combine.picks[key] = { ...combine.picks[key], [name]: prop };
            fillCombinedPanel(combine.selected);
            return;
        }
        const name = e.target.closest(".combine-name");
        if (name) {
            const item = combine.selected[Number(name.dataset.index)];
            combine.focus = combine.focus === item ? null : item;
            fillCombinedPanel(combine.selected);
            return;
        }
        const remove = e.target.closest(".combine-remove");
        if (remove) removeCombined(combine.selected[Number(remove.dataset.index)]);
    }
    combinedPanel.addEventListener("click", onCombinedClick);

    // 5. Apply filtering logic
    // Whether a dataset passes one pill filter: nothing selected, or any / all
    // of the selected pills (mode) among its own values
    function matchesPills(selected, values, mode) {
        const has = (v) => values.includes(v);
        return selected.size === 0 || (mode === "all" ? [...selected].every(has) : [...selected].some(has));
    }

    // The list shows the datasets the filters let through a page at a time: as
    // many as fit its height without scrolling (paginate), so the pages follow
    // the window and the view. A change of filters or sort goes back to the
    // first page; the pager under the list moves between them.
    let pageStarts = [0]; // where each page starts in matched
    let page = 0;
    let matched = []; // the datasets the filters let through, in the list's order
    const pager = document.createElement("nav");
    pager.className = "list-pager";
    pager.setAttribute("aria-label", "Pages of datasets");
    listColumn.appendChild(pager);

    // Which datasets are on show ("Showing 1–8 of 23 datasets", without the
    // words if the line is too long), then ‹, the page numbers and ›: the first,
    // the last and the ones beside this one (the first three or the last three
    // near an end), … for the rest; a … for a single page shows its number
    const CHEVRON = (d) =>
        `<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path d="${d}" fill="none" ` +
        'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    function drawPager(pages) {
        const start = pageStarts[page];
        const end = pageStarts[page + 1] ?? matched.length;
        const words = (text) => `<span class="pager-words">${text}</span>`;
        const range = end - start === 1 ? `${end}` : `${start + 1}–${end}`;
        const info = matched.length
            ? `${words("Showing ")}${range} of ${matched.length}${words(matched.length === 1 ? " dataset" : " datasets")}`
            : "No datasets match the filters";
        const parts = [];
        if (pages > 1) {
            const shown = (i) =>
                i === 0 || i === pages - 1 || Math.abs(i - page) <= 1 || (page <= 1 && i <= 2) || (page >= pages - 2 && i >= pages - 3);
            parts.push(`<button data-page="${page - 1}" aria-label="Previous page"${page === 0 ? " disabled" : ""}>${CHEVRON("M10 3 5 8l5 5")}</button>`);
            for (let i = 0; i < pages; i++) {
                if (shown(i) || (shown(i - 1) && shown(i + 1))) {
                    parts.push(`<button data-page="${i}"${i === page ? ' aria-current="page"' : ""}>${i + 1}</button>`);
                } else if (!parts.at(-1).includes("pager-gap")) {
                    parts.push('<span class="pager-gap">…</span>');
                }
            }
            parts.push(`<button data-page="${page + 1}" aria-label="Next page"${page === pages - 1 ? " disabled" : ""}>${CHEVRON("M6 3l5 5-5 5")}</button>`);
        }
        pager.innerHTML = `<span class="pager-info">${info}</span><span class="pager-pages">${parts.join("")}</span>`;
        // too long for one line: "1–8 of 23"
        pager.classList.remove("compact");
        if (pager.scrollWidth > pager.clientWidth) pager.classList.add("compact");
    }

    function renderPage() {
        page = Math.min(page, pageStarts.length - 1);
        const onPage = new Set(matched.slice(pageStarts[page], pageStarts[page + 1] ?? matched.length));
        cardData.forEach((item) => (item.btn.style.display = onPage.has(item) ? "" : "none"));
        drawPager(pageStarts.length);
        flashScrollbar(listColumn);
    }

    // Splits matched into pages that fit the list's height (the window's under
    // the header, or its max-height above the panel in the narrow layout; less
    // the toolbar, the Combine bar and the pager's room): list rows by their own
    // heights (a long name takes two lines), or whole lines of icons (all as
    // tall as the tallest); at least one row or line a page. Every dataset is
    // shown meanwhile, to be measured, with no scrollbar (as on a page).
    function paginate() {
        listColumn.style.overflowY = "hidden";
        cardData.forEach((item) => (item.btn.style.display = matched.includes(item) ? "" : "none"));
        const heights = matched.map((item) => item.btn.offsetHeight);
        const style = getComputedStyle(listColumn);
        const gap = parseFloat(style.rowGap) || 0;
        const PAGER = pager.offsetHeight;
        const height = style.maxHeight === "none" ? listColumn.clientHeight : parseFloat(style.maxHeight);
        let room = height - parseFloat(style.paddingBottom) - PAGER - gap;
        [toolbar, combineBar].forEach((el) => (room -= el.offsetHeight + gap));
        listColumn.style.overflowY = "";
        pageStarts = [0];
        if (table.classList.contains("icon-view")) {
            const tableStyle = getComputedStyle(table);
            const tileGap = parseFloat(tableStyle.rowGap) || 0;
            const perLine = tableStyle.gridTemplateColumns.split(" ").length;
            const lines = Math.max(1, Math.floor((room + tileGap) / (Math.max(0, ...heights) + tileGap)));
            for (let i = lines * perLine; i < matched.length; i += lines * perLine) pageStarts.push(i);
        } else {
            const rowsRoom = room - (table.offsetHeight - table.clientHeight) - header.offsetHeight;
            let used = 0;
            heights.forEach((h, i) => {
                if (used > 0 && used + h > rowsRoom) {
                    pageStarts.push(i);
                    used = 0;
                }
                used += h;
            });
        }
    }

    // The pages again (another window height, view or set of datasets), on the
    // page holding the dataset that was first on show
    function showPage() {
        const first = pageStarts[Math.min(page, pageStarts.length - 1)];
        paginate();
        page = Math.max(0, pageStarts.findLastIndex((start) => start <= first));
        renderPage();
    }
    let resizing = 0;
    window.addEventListener("resize", () => {
        cancelAnimationFrame(resizing);
        resizing = requestAnimationFrame(() => {
            applyShare(); // the list's width dragged (the splitter, below), for the new width
            showPage();
        });
    });
    window.addEventListener("load", showPage); // again with the web fonts in

    pager.addEventListener("click", (e) => {
        const btn = e.target.closest("button[data-page]");
        if (!btn || btn.disabled) return;
        page = Number(btn.dataset.page);
        renderPage();
        listColumn.scrollTop = 0;
    });

    // firstPage: false keeps the page on show (Combine switching off)
    function applyFilters(firstPage = true) {
        matched = cardData.filter((item) => {
            const matchesSearch =
                !state.searchQuery ||
                item.title.toLowerCase().includes(state.searchQuery) ||
                item.annotations.some((a) => a.toLowerCase().includes(state.searchQuery));
            const matchesAnn = matchesPills(state.selectedAnnotations, item.annotations, state.annMatch);
            const matchesLic = matchesPills(state.selectedLicenses, item.licenses, state.licMatch);
            return matchesSearch && matchesAnn && matchesLic;
        });
        if (firstPage) page = 0;
        showPage();
        counter.textContent = `Showing ${matched.length} of ${cardData.length}`;
        listCount.textContent = matched.length === 1 ? "1 Dataset" : `${matched.length} Datasets`;
        if (combine.on) return; // Combine mode: the filters only change the list
        // Keep the dataset on show if the filters let it through (on whatever
        // page), otherwise show the first one
        selectCard(activeItem && matched.includes(activeItem) ? activeItem : matched[0] || null);
    }
    applyFilters();

    // The splitter between the list and the panel (custom.css, shown on hover):
    // dragging it, or the arrow keys on it, set the list's width, from its
    // default (350px, or what the panel's 850px leaves it) up to the share of
    // the width a 27" monitor gives it (687px of 687 + 850): the list takes
    // width from the panel, and gives it back, but never leaves a blank. So a
    // laptop's list can widen enough to show License; a window where both are
    // at their widest has nothing to drag (the splitter idle). A double-click
    // goes back to the default widths. The browser remembers the share;
    // without storage it lasts this visit. Not in the narrow layout (no
    // splitter there).
    const SHARE_KEY = "mirdata-gallery-list-share";
    const MIN_LIST = 350;
    const MAX_LIST = 687;
    const MAX_SHARE = MAX_LIST / (MAX_LIST + 850);
    let share = null; // the list's share of the list and the panel's width, or null: the default
    try {
        share = parseFloat(localStorage.getItem(SHARE_KEY)) || null;
    } catch (e) {
        // no storage: the default
    }
    splitter.setAttribute("role", "separator");
    splitter.setAttribute("aria-orientation", "vertical");
    splitter.setAttribute("aria-label", "Drag to resize the dataset list; double-click to reset");
    splitter.tabIndex = 0;

    const listRoom = () => container.clientWidth - splitter.offsetWidth; // the list's and the panel's

    // The list's narrowest and widest: its default, and the 27" share
    function listBounds() {
        const room = listRoom();
        const panel = parseFloat(getComputedStyle(infoColumn).flexBasis) || 850; // its widest (custom.css)
        const min = Math.max(MIN_LIST, Math.min(MAX_LIST, room - panel));
        return [min, Math.max(min, Math.min(MAX_LIST, room * MAX_SHARE))];
    }

    // The list at its share, within its bounds; the default flex without one,
    // with nothing to drag (the splitter idle), or in the narrow layout
    function applyShare() {
        const [min, max] = listBounds();
        const idle = getComputedStyle(splitter).display === "none" || max - min < 1;
        splitter.classList.toggle("idle", idle);
        splitter.tabIndex = idle ? -1 : 0;
        if (share === null || idle) {
            listColumn.style.flex = "";
            return;
        }
        listColumn.style.flex = `0 0 ${Math.min(max, Math.max(min, share * listRoom()))}px`;
    }

    function saveShare() {
        try {
            if (share === null) localStorage.removeItem(SHARE_KEY);
            else localStorage.setItem(SHARE_KEY, String(share));
        } catch (e) {
            // no storage: this visit only
        }
    }

    // A new width for the list: its share, kept within bounds, and its pages again
    function resizeList(width) {
        share = width / listRoom();
        applyShare();
        share = listColumn.offsetWidth / listRoom(); // as it came out, within bounds
        cancelAnimationFrame(resizing);
        resizing = requestAnimationFrame(showPage);
    }

    // A drag: from a press on the splitter to the button's release, wherever
    // that is told: the release itself (on the splitter, which holds the
    // pointer, or anywhere in the window), the pointer lost or cancelled, the
    // window left, or a move with no button down (a release outside the window
    // the browser never told of)
    splitter.addEventListener("pointerdown", (e) => {
        if (e.button !== 0) return;
        e.preventDefault(); // no text selection or native drag starting
        try {
            splitter.setPointerCapture(e.pointerId);
        } catch (err) {
            // not capturable: the window's events below still end the drag
        }
        splitter.classList.add("dragging");
        document.body.style.userSelect = "none";
    });
    splitter.addEventListener("pointermove", (e) => {
        if (!splitter.classList.contains("dragging")) return;
        if (e.buttons === 0) {
            endDrag();
            return;
        }
        resizeList(e.clientX - listColumn.getBoundingClientRect().left - splitter.offsetWidth / 2);
    });
    function endDrag() {
        if (!splitter.classList.contains("dragging")) return;
        splitter.classList.remove("dragging");
        document.body.style.userSelect = "";
        saveShare();
    }
    ["pointerup", "pointercancel", "lostpointercapture"].forEach((type) => splitter.addEventListener(type, endDrag));
    window.addEventListener("pointerup", endDrag);
    window.addEventListener("blur", endDrag);
    splitter.addEventListener("dblclick", () => {
        share = null;
        applyShare();
        saveShare();
        showPage();
    });
    splitter.addEventListener("keydown", (e) => {
        const step = { ArrowLeft: -20, ArrowRight: 20 }[e.key];
        if (!step) return;
        e.preventDefault();
        resizeList(listColumn.offsetWidth + step);
        saveShare();
    });
    applyShare();
    if (share !== null) showPage();

    // 6. Plot bars, the filters' AND / OR buttons and the list's type dots: show
    // their hover text at once, in a box right of the cursor. The browser's own <title> tooltip waits
    // about a second, so the text moves from each bar's <title> to data-tip.
    const tip = document.createElement("div");
    tip.className = "plot-tip";
    document.body.appendChild(tip);
    // (moveTips runs again on every combined panel drawn)
    function moveTips(root) {
        root.querySelectorAll(".plot-svg g").forEach((bar) => {
            const title = bar.querySelector("title");
            if (!title) return;
            bar.dataset.tip = title.textContent;
            bar.setAttribute("aria-label", title.textContent);
            title.remove();
        });
    }
    moveTips(infoColumn);
    function showTip(e) {
        const bar = e.target.closest("[data-tip]");
        if (!bar) {
            tip.style.display = "none";
            return;
        }
        tip.textContent = bar.dataset.tip;
        tip.style.display = "block";
        // right of the cursor, its middle level with it, kept inside the window:
        // left of the cursor when there is no room on the right
        const right = e.clientX + 14;
        const x = right + tip.offsetWidth <= window.innerWidth - 4 ? right : Math.max(e.clientX - 14 - tip.offsetWidth, 4);
        const y = Math.min(Math.max(e.clientY - tip.offsetHeight / 2, 4), window.innerHeight - tip.offsetHeight - 4);
        tip.style.left = `${x}px`;
        tip.style.top = `${y}px`;
    }
    const hideTip = () => (tip.style.display = "none");
    [infoColumn, sidebar, listColumn].forEach((el) => {
        el.addEventListener("pointermove", showTip);
        el.addEventListener("pointerdown", showTip); // a tap on a touch screen
        el.addEventListener("pointerleave", hideTip);
    });
    infoColumn.addEventListener("scroll", hideTip);
    listColumn.addEventListener("scroll", hideTip);

    // 7. Annotation type focus: a click on a type in a panel's At a glance (a
    // dataset's or the combination's) shows only that type's plots in its
    // Statistics and dims the other types; one more click shows them all again.
    // The combination's is kept in combine.typeFocus, as its panel is redrawn.
    // The "Annotation types" title gets a hint saying so.
    function focusType(panel, type) {
        panel.querySelectorAll(".glance-tags [data-ann]").forEach((tag) => {
            tag.setAttribute("role", "button");
            tag.tabIndex = 0;
            tag.setAttribute("aria-pressed", String(tag.dataset.ann === type));
        });
        const tags = panel.querySelector(".glance-tags");
        if (tags && tags.querySelector("[data-ann]")) {
            tags.classList.toggle("has-focus", Boolean(type));
            const title = tags.previousElementSibling;
            if (!title.querySelector(".box-hint")) {
                title.insertAdjacentHTML("beforeend", '<span class="box-hint">Click a type to focus it in the plots</span>');
            }
        }
        const grid = panel.querySelector(".plot-grid");
        if (!grid) return;
        let shown = 0;
        grid.querySelectorAll(".plot").forEach((fig) => {
            const show = !type || fig.dataset.type === type;
            fig.style.display = show ? "" : "none";
            shown += show;
        });        // a type without plots: a note instead
        let empty = panel.querySelector(".type-empty");
        if (type && !shown) {
            if (!empty) {
                empty = document.createElement("p");
                empty.className = "stats-note type-empty";
                grid.before(empty);
            }
            empty.textContent = `No ${type} plots yet.`;
        } else if (empty) {
            empty.remove();
        }
    }
    cards.forEach((card) => focusType(card, null));
    infoColumn.addEventListener("click", (e) => {
        const tag = e.target.closest(".glance-tags [data-ann]");
        if (!tag) return;
        const panel = tag.closest(".gallery-cards-information > section");
        const type = tag.getAttribute("aria-pressed") === "true" ? null : tag.dataset.ann;
        if (panel === combinedPanel) combine.typeFocus = type;
        focusType(panel, type);
    });
    // Enter or Space on a focused type clicks it
    infoColumn.addEventListener("keydown", (e) => {
        if ((e.key === "Enter" || e.key === " ") && e.target.matches(".glance-tags [data-ann]")) {
            e.preventDefault();
            e.target.click();
        }
    });

    // 8. Scrollbars: custom.css hides the filters', the list's and the panel's
    // until the pointer is over them; they also show for a moment when their
    // content changes (another dataset, a combination, a page of the list),
    // when they scroll, and when the page has loaded
    function flashScrollbar(el) {
        el.classList.add("scrollbar-shown");
        clearTimeout(el.scrollbarTimer);
        el.scrollbarTimer = setTimeout(() => el.classList.remove("scrollbar-shown"), 1200);
    }
    const scrollers = [document.getElementById("left-sidebar"), listColumn, infoColumn].filter(Boolean);
    scrollers.forEach((el) => el.addEventListener("scroll", () => flashScrollbar(el), { passive: true }));
    window.addEventListener("load", () => scrollers.forEach(flashScrollbar));

    // 9. Statistics, larger: a button at the end of a panel's Statistics title
    // (one with plots) opens the box in a pop-up over the page, at the pop-up's
    // width, so its plots scale up with it (custom.css, .stats-dialog). The
    // pop-up always shows a copy of the Statistics on show (refreshStats, run
    // whenever the combination's are redrawn and when Combine switches off):
    // clicks in it work as on the combined panel (onCombinedClick). ×, Esc or a
    // click outside it closes it.
    function addStatsButton(panel) {
        const grid = panel.querySelector(".plot-grid");
        if (!grid || !grid.children.length) return;
        grid.closest(".panel-box")
            .querySelector(".box-title")
            .insertAdjacentHTML("beforeend", '<button class="stats-expand" title="Show larger" aria-label="Show the statistics larger">⤢</button>');
    }
    cards.forEach(addStatsButton);

    // in the panel column, so the panel's styles and hover text (6. above) work in it too;
    // shown open, a dialog is drawn over the whole page wherever it is
    const statsDialog = document.createElement("dialog");
    statsDialog.className = "stats-dialog";
    statsDialog.innerHTML =
        '<div class="stats-dialog-head"><span class="stats-dialog-title"></span>' +
        '<button class="stats-close" title="Close" aria-label="Close">×</button></div>' +
        '<div class="stats-dialog-body"></div>';
    infoColumn.appendChild(statsDialog);

    // The pop-up's copy of the Statistics on show (the combination's, or the
    // dataset's), under its name; closes the pop-up when there are none
    function refreshStats() {
        if (!statsDialog.open) return;
        const combined = combinedPanel.style.display !== "none";
        const panel = combined ? combinedPanel : activeItem && activeItem.card;
        const grid = panel && panel.querySelector(".plot-grid");
        if (!grid) {
            statsDialog.close();
            return;
        }
        const copy = grid.closest(".panel-box").cloneNode(true);
        copy.querySelector(".stats-expand")?.remove();
        statsDialog.querySelector(".stats-dialog-title").textContent = combined ? `${combine.selected.length} Datasets Combined` : activeItem.title;
        statsDialog.querySelector(".stats-dialog-body").replaceChildren(copy);
        showSources(copy); // placed again: the pop-up is wider
    }

    infoColumn.addEventListener("click", (e) => {
        if (!e.target.closest(".stats-expand")) return;
        statsDialog.append(tip); // the hover box shows over the pop-up only from inside it
        statsDialog.showModal();
        refreshStats();
    });
    statsDialog.addEventListener("click", (e) => {
        // the dialog itself is hit only outside its content: the backdrop
        if (e.target === statsDialog || e.target.closest(".stats-close")) statsDialog.close();
        else onCombinedClick(e);
    });
    statsDialog.addEventListener("close", () => {
        hideTip();
        document.body.appendChild(tip);
    });
    statsDialog.querySelector(".stats-dialog-body").addEventListener("scroll", hideTip);
});