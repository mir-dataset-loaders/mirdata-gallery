document.addEventListener("DOMContentLoaded", function () {
    const gallery = document.getElementById("mirdata-gallery"); // the section of index.rst's title
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

        return { card, title, annotations, license, tracksText, tracks: isNaN(tracks) ? null : tracks };
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
    // Mount Column 1 to the theme's left sidebar, and Columns 2 & 3 to main area
    const themeSidebar = document.querySelector("#left-sidebar nav");
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
    // with one row per dataset (Dataset, Tracks, License, Annotation Types)
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
    ["Dataset", "Tracks", "License", "Annotation Types"].forEach((label) => {
        const cell = document.createElement("span");
        cell.textContent = label;
        header.appendChild(cell);
    });
    table.appendChild(header);
    listColumn.appendChild(table);

    const MAX_TAGS = 4; // the rest show as "+N"
    cardData.forEach((item) => {
        const btn = document.createElement("button");
        btn.className = "dataset-item-btn list-row";
        const name = document.createElement("span");
        name.className = "dataset-item-title";
        name.textContent = item.title;
        const tracks = document.createElement("span");
        tracks.className = "list-cell";
        tracks.textContent = item.tracksText;
        const license = document.createElement("span");
        license.className = "list-cell";
        license.textContent = item.license;
        const tags = document.createElement("span");
        tags.className = "list-tags";
        item.annotations.slice(0, MAX_TAGS).forEach((ann) => {
            const tag = document.createElement("span");
            tag.className = "list-tag";
            tag.setAttribute("data-ann", ann);
            tag.textContent = ann;
            tags.appendChild(tag);
        });
        if (item.annotations.length > MAX_TAGS) {
            const more = document.createElement("span");
            more.className = "list-tag list-tag-more";
            more.textContent = `+${item.annotations.length - MAX_TAGS}`;
            tags.appendChild(more);
        }
        btn.append(name, tracks, license, tags);
        btn.addEventListener("click", () => {
            selectCard(item);
        });
        item.btn = btn;
        table.appendChild(btn);
    });

    function sortRows() {
        cardData.sort(SORTS[sortSelect.value]);
        cardData.forEach((item) => table.appendChild(item.btn));
    }
    sortRows();
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
        // Keep current selection if visible, otherwise select first visible dataset
        if (currentActiveStillVisible && activeItem) {
            selectCard(activeItem);
        } else {
            selectCard(firstVisibleItem);
        }
    }
    applyFilters();
});