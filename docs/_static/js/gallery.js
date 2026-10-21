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

        return { card, title, annotations, license, tracksText, tracks: isNaN(tracks) ? null : tracks, facts, plots };
    });



    // 2. Collect unique annotation types and licenses with counts
    const annCounts = {};
    const licenseCounts = {};
    cardData.forEach((d) => {
        d.annotations.forEach((a) => (annCounts[a] = (annCounts[a] || 0) + 1));
        licenseCounts[d.license] = (licenseCounts[d.license] || 0) + 1;
    });

    // 3. State tracking
    const state = {
        selectedAnnotations: new Set(),
        selectedLicense: null,
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
        state.selectedLicense = null;
        state.searchQuery = "";
        search.value = "";
        sidebar.querySelectorAll(".filter-pill.active").forEach((p) => p.classList.remove("active"));
        applyFilters();
    });
    headerBar.appendChild(counter);
    headerBar.appendChild(resetBtn);
    sidebar.appendChild(headerBar);

    // Annotation Filters Section
    const annTitle = document.createElement("h4");
    annTitle.textContent = "ANNOTATION TYPES";
    sidebar.appendChild(annTitle);

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
    const licTitle = document.createElement("h4");
    licTitle.textContent = "LICENSES";
    licTitle.style.marginTop = "20px";
    sidebar.appendChild(licTitle);

    const licContainer = document.createElement("div");
    licContainer.className = "filter-pills-group";

    Object.keys(licenseCounts)
        .sort()
        .forEach((lic) => {
            const pill = document.createElement("button");
            pill.className = "filter-pill";
            pill.innerHTML = `${lic} <span class="count">${licenseCounts[lic]}</span>`;
            pill.addEventListener("click", () => {
                if (state.selectedLicense === lic) {
                    state.selectedLicense = null;
                    pill.classList.remove("active");
                } else {
                    licContainer.querySelectorAll(".filter-pill").forEach((p) => p.classList.remove("active"));
                    state.selectedLicense = lic;
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
    container.appendChild(infoColumn);
    gallery.appendChild(container);
    // Selection helper function
    let activeItem = null;
    function selectCard(item) {
        if (activeItem) {
            activeItem.btn.classList.remove("active");
            activeItem.card.style.display = "none";
        }
        if (item) {
            activeItem = item;
            item.btn.classList.add("active");
            item.card.style.display = "flex";
        }
    }
    // The middle column: the number of datasets and a sort menu, above a table
    // with one row per dataset (Dataset, Tracks)
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
    toolbar.append(listCount, sortLabel);
    listColumn.appendChild(toolbar);

    const table = document.createElement("div");
    table.className = "list-table";
    const header = document.createElement("div");
    header.className = "list-row list-header";
    ["Dataset", "Tracks"].forEach((label) => {
        const cell = document.createElement("span");
        cell.textContent = label;
        header.appendChild(cell);
    });
    table.appendChild(header);
    listColumn.appendChild(table);

    cardData.forEach((item) => {
        const btn = document.createElement("button");
        btn.className = "dataset-item-btn list-row";
        const name = document.createElement("span");
        name.className = "dataset-item-title";
        name.textContent = item.title;
        const tracks = document.createElement("span");
        tracks.className = "list-cell";
        tracks.textContent = item.tracksText;
        btn.append(name, tracks);
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

    // Combine mode: the Combine button switches what a click on a dataset does.
    // Off, the click shows that dataset; on, it adds the dataset to the
    // combination or removes it, and the panel shows the combination
    // (combine.js works out its text). Cmd-click or Ctrl-click switches it on
    // too. A combination of one shows that dataset's own panel, and removing
    // datasets down to one switches Combine off, on that one. Filters only
    // change the list: a dataset they hide stays in the combination.
    // colours: each selected dataset's colour, given when it joins (combine.js, nextColour)
    // focus: the dataset whose part of each plot is shown (its chip's name clicked), or null: stacked
    const combine = { on: false, selected: [], colours: new Map(), lastClicked: null, focus: null };
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
            applyFilters(); // the first visible one instead, if the filters hide it
        }
    });

    // A dataset joins the combination with the first free colour, and leaves it
    // with its colour, free for the next one to join; the others keep theirs.
    // The focused one leaving takes the focus with it: the plots stack again.
    function join(item) {
        combine.colours.set(item, mirdataCombine.nextColour([...combine.colours.values()]));
        combine.selected.push(item);
    }

    function leave(item) {
        combine.colours.delete(item);
        combine.selected.splice(combine.selected.indexOf(item), 1);
        if (combine.focus === item) combine.focus = null;
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

    // The combined panel: its title and datasets (a chip each: a click on its
    // name focuses it, one more shows them all again, and × removes it; its dot
    // is the dataset's colour in the plots, so the chips are the legend), At a
    // glance, and Statistics: each dataset's notes, and the plots pooled from
    // theirs (combine.js), stacked by dataset or showing the focused one's part
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
        const plots = mirdataCombine.combinedPlots(datasets);
        if (!plots.length) notes.push("Nothing to plot yet.");
        combinedPanel.innerHTML =
            `<h2>${selected.length} datasets combined</h2>` +
            `<div class="combine-chips">${chips}</div>` +
            '<p class="combine-chips-hint">Click a name to focus it in the plots</p>' +
            '<div class="panel-box"><div class="box-title">At a glance</div>' +
            `<div class="glance-grid">${rows}</div>` +
            `<div class="box-title">Annotation types</div><div class="glance-tags">${tags || "—"}</div></div>` +
            '<div class="panel-box"><div class="box-title">Statistics</div>' +
            notes.map((text) => `<p class="stats-note">${escape(text)}</p>`).join("") +
            (plots.length ? `<div class="plot-grid">${mirdataCharts.plotGridHtml(plots, combine.focus && combine.focus.title)}</div>` : "") +
            "</div>";
        moveTips(combinedPanel);
    }

    combinedPanel.addEventListener("click", (e) => {
        const name = e.target.closest(".combine-name");
        if (name) {
            const item = combine.selected[Number(name.dataset.index)];
            combine.focus = combine.focus === item ? null : item;
            fillCombinedPanel(combine.selected);
            return;
        }
        const remove = e.target.closest(".combine-remove");
        if (remove) removeCombined(combine.selected[Number(remove.dataset.index)]);
    });

    // 5. Apply filtering logic
    function applyFilters() {
        let visibleCount = 0;
        let firstVisibleItem = null;
        let currentActiveStillVisible = false;
        cardData.forEach((item) => {
            const matchesSearch =
                !state.searchQuery ||
                item.title.toLowerCase().includes(state.searchQuery) ||
                item.annotations.some((a) => a.toLowerCase().includes(state.searchQuery));
            const matchesAnn =
                state.selectedAnnotations.size === 0 ||
                Array.from(state.selectedAnnotations).some((a) => item.annotations.includes(a));
            const matchesLic = !state.selectedLicense || item.license === state.selectedLicense;
            const isVisible = matchesSearch && matchesAnn && matchesLic;
            item.btn.style.display = isVisible ? "" : "none";
            if (isVisible) {
                visibleCount++;
                if (!firstVisibleItem) firstVisibleItem = item;
                if (activeItem === item) currentActiveStillVisible = true;
            }
        });
        counter.textContent = `Showing ${visibleCount} of ${cardData.length}`;
        listCount.textContent = visibleCount === 1 ? "1 dataset" : `${visibleCount} datasets`;
        if (combine.on) return; // Combine mode: the filters only change the list
        // Keep current selection if visible, otherwise select first visible dataset
        if (currentActiveStillVisible && activeItem) {
            selectCard(activeItem);
        } else {
            selectCard(firstVisibleItem);
        }
    }
    applyFilters();

    // 6. Plot bars: show their hover text at once, in a box above the cursor.
    // The browser's own <title> tooltip waits about a second, so the text moves
    // from each bar's <title> to data-tip.
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
        const bar = e.target.closest(".plot-svg g[data-tip]");
        if (!bar) {
            tip.style.display = "none";
            return;
        }
        tip.textContent = bar.dataset.tip;
        tip.style.display = "block";
        // centred above the cursor, kept inside the window
        const x = Math.min(Math.max(e.clientX - tip.offsetWidth / 2, 4), window.innerWidth - tip.offsetWidth - 4);
        tip.style.left = `${x}px`;
        tip.style.top = `${e.clientY - tip.offsetHeight - 10}px`;
    }
    const hideTip = () => (tip.style.display = "none");
    infoColumn.addEventListener("pointermove", showTip);
    infoColumn.addEventListener("pointerdown", showTip); // a tap on a touch screen
    infoColumn.addEventListener("pointerleave", hideTip);
    infoColumn.addEventListener("scroll", hideTip);
});