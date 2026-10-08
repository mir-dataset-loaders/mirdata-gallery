document.addEventListener("DOMContentLoaded", function () {
    const gallery = document.getElementById("mirdata-dataset-gallery");
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

    // 1. Extract metadata specifically from "Annotations:" and "License:"
    const cardData = cards.map((card) => {
        let annotations = [];
        let rawLicense = "Not specified";

        card.querySelectorAll("li").forEach((li) => {
            const strong = li.querySelector("strong");
            const label = strong ? strong.textContent.trim() : "";

            // Only grab real annotations (ignores Downloadable Remotes, README, etc.)
            if (label.startsWith("Annotations")) {
                const annEls = li.querySelectorAll("code");
                annotations = Array.from(annEls).map((el) => {
                    const val = el.textContent.trim();
                    el.setAttribute("data-ann", val); //Tag each card badge
                    return val;
                });
            } else if (label.startsWith("License")) {
                const clone = li.cloneNode(true);
                const st = clone.querySelector("strong");
                if (st) st.remove();
                const licText = clone.textContent.trim();
                if (licText) rawLicense = licText;
            }
        });

        const license = normalizeLicense(rawLicense);
        const h2 = card.querySelector("h2");
        let title = card.id;
        if (h2) {
            const clone = h2.cloneNode(true);
            const headerlink = clone.querySelector(".headerlink");
            if (headerlink) headerlink.remove();
            title = clone.textContent.trim();
        }


        return { card, title, annotations, license };
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
    // Column 1: Filters Sidebar (injected into RTD navigation menu)
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
    search.placeholder = "Search annotations...";
    search.className = "filter-search";
    search.addEventListener("input", (e) => {
        state.searchQuery = e.target.value.toLowerCase().trim();
        // add live filter to the annotation menu:

        annContainer.querySelectorAll(".filter-pill").forEach((pill) => {
            const tag = pill.textContent.toLowerCase();
            pill.style.display = !state.searchQuery || tag.includes(state.searchQuery) ? "" : "none";
        });
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
            pill.innerHTML = `${ann} <span class="count">${annCounts[ann]}</span>`;
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
    // Mount Column 1 to RTD sidebar, and Columns 2 & 3 to main area
    const wyMenu = document.querySelector(".wy-menu-vertical");
    if (wyMenu) {
        wyMenu.innerHTML = "";
        wyMenu.appendChild(sidebar);
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
    // Build the clickable buttons in the middle column
    cardData.forEach((item) => {
        const btn = document.createElement("button");
        btn.className = "dataset-item-btn";
        const titleSpan = document.createElement("span");
        titleSpan.className = "dataset-item-title";
        titleSpan.textContent = item.title;
        btn.appendChild(titleSpan);
        const metaDiv = document.createElement("div");
        metaDiv.className = "dataset-item-meta";
        if (item.license && item.license !== "Not specified") {
            const licBadge = document.createElement("span");
            licBadge.className = "dataset-badge-license";
            licBadge.textContent = item.license;
            metaDiv.appendChild(licBadge);
        }
        const annBadge = document.createElement("span");
        annBadge.className = "dataset-badge-ann";
        const count = item.annotations.length;
        annBadge.textContent = count === 1 ? "1 annotation" : `${count} annotations`;
        metaDiv.appendChild(annBadge);
        btn.appendChild(metaDiv);
        btn.addEventListener("click", () => {
            selectCard(item);
        });
        item.btn = btn;
        listColumn.appendChild(btn);
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
            item.btn.style.display = isVisible ? "flex" : "none";
            if (isVisible) {
                visibleCount++;
                if (!firstVisibleItem) firstVisibleItem = item;
                if (activeItem === item) currentActiveStillVisible = true;
            }
        });
        counter.textContent = `Showing ${visibleCount} of ${cardData.length}`;
        // Keep current selection if visible, otherwise select first visible dataset
        if (currentActiveStillVisible && activeItem) {
            selectCard(activeItem);
        } else {
            selectCard(firstVisibleItem);
        }
    }
    applyFilters();
});