// The dataset list: the toolbar, the table of datasets (or tiles), and its pages.
window.mirdataList = function (shared) {
    const { cardData, listColumn, selectCard, flashScrollbar } = shared;

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
        shared.applyFilters();
    });
    sortLabel.appendChild(sortSelect);
    const tools = document.createElement("div"); // the sort menu, then the view switch
    tools.className = "list-tools";
    tools.appendChild(sortLabel);
    toolbar.append(listCount, tools);
    listColumn.appendChild(toolbar);

    // The table: Dataset, Types (a dot per annotation type, its colour), Tracks,
    // License; list.css wraps the dots, then drops License, as the list gets
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
    // (type-colours.css), then the silver ones A–Z
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
        if (sorted.length) types.dataset.tip = sorted.join(", "); // shown at once on hover (panel.js)
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
            const { combine, combineBtn, toggleCombined } = shared;
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

    // The list / icon switch: the same rows, laid out as tiles by list.css
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
            showPage(); // another view fits another number
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

    // The list shows the datasets the filters let through a page at a time: as
    // many as fit its height without scrolling (paginate), so the pages follow
    // the window and the view. A change of filters or sort goes back to the
    // first page; the pager under the list moves between them.
    let pageStarts = [0]; // where each page starts in matched
    let page = 0;
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
        const end = pageStarts[page + 1] ?? shared.matched.length;
        const words = (text) => `<span class="pager-words">${text}</span>`;
        const range = end - start === 1 ? `${end}` : `${start + 1}–${end}`;
        const info = shared.matched.length
            ? `${words("Showing ")}${range} of ${shared.matched.length}${words(shared.matched.length === 1 ? " dataset" : " datasets")}`
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
        const onPage = new Set(shared.matched.slice(pageStarts[page], pageStarts[page + 1] ?? shared.matched.length));
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
        cardData.forEach((item) => (item.btn.style.display = shared.matched.includes(item) ? "" : "none"));
        const heights = shared.matched.map((item) => item.btn.offsetHeight);
        const style = getComputedStyle(listColumn);
        const gap = parseFloat(style.rowGap) || 0;
        const PAGER = pager.offsetHeight;
        const height = style.maxHeight === "none" ? listColumn.clientHeight : parseFloat(style.maxHeight);
        let room = height - parseFloat(style.paddingBottom) - PAGER - gap;
        [toolbar, shared.combineBar].forEach((el) => (room -= el.offsetHeight + gap));
        listColumn.style.overflowY = "";
        pageStarts = [0];
        if (table.classList.contains("icon-view")) {
            const tableStyle = getComputedStyle(table);
            const tileGap = parseFloat(tableStyle.rowGap) || 0;
            const perLine = tableStyle.gridTemplateColumns.split(" ").length;
            const lines = Math.max(1, Math.floor((room + tileGap) / (Math.max(0, ...heights) + tileGap)));
            for (let i = lines * perLine; i < shared.matched.length; i += lines * perLine) pageStarts.push(i);
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

    // The filters let another set of datasets through (filters.js). firstPage:
    // false keeps the page on show.
    function showMatched(firstPage) {
        if (firstPage) page = 0;
        showPage();
        listCount.textContent = shared.matched.length === 1 ? "1 Dataset" : `${shared.matched.length} Datasets`;
    }

    window.addEventListener("load", showPage); // again with the web fonts in

    pager.addEventListener("click", (e) => {
        const btn = e.target.closest("button[data-page]");
        if (!btn || btn.disabled) return;
        page = Number(btn.dataset.page);
        renderPage();
        listColumn.scrollTop = 0;
    });

    Object.assign(shared, { table, showPage, showMatched });
};
