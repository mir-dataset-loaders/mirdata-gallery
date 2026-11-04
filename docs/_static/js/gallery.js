// The gallery page's start: reads the panels gallery.py wrote, builds the columns
// and sets up each part in turn.
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

    // Read the annotation tags and the license from each panel's "At a glance" box
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

    // Build Layout: Container with Sidebar (Left) and Content Grid (Right)
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
    // the bar between them, dragged to widen the list (splitter.js)
    const splitter = document.createElement("div");
    splitter.className = "gallery-splitter";

    // Selection helper function
    function selectCard(item) {
        const shown = shared.activeItem && shared.activeItem.card.style.display !== "none" ? shared.activeItem : null;
        if (shared.activeItem) {
            shared.activeItem.btn.classList.remove("active");
            shared.activeItem.card.style.display = "none";
        }
        if (item) {
            shared.activeItem = item;
            item.btn.classList.add("active");
            item.card.style.display = "flex";
            if (item !== shown) flashScrollbar(infoColumn); // another dataset on show
        }
    }

    // Scrollbars: layout.css hides the filters', the list's and the panel's
    // until the pointer is over them; they also show for a moment when their
    // content changes (another dataset, a combination, a page of the list),
    // when they scroll, and when the page has loaded
    function flashScrollbar(el) {
        el.classList.add("scrollbar-shown");
        clearTimeout(el.scrollbarTimer);
        el.scrollbarTimer = setTimeout(() => el.classList.remove("scrollbar-shown"), 1200);
    }

    // What the parts need from each other: these, and what each part's setup adds
    // for the others. activeItem: the dataset on show, or the last one shown.
    // matched: the datasets the filters let through, in the list's order.
    const shared = {
        cards, cardData, container, sidebar, listColumn, infoColumn, splitter,
        selectCard, flashScrollbar, activeItem: null, matched: [],
    };

    mirdataFilters(shared);

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
    container.appendChild(splitter);
    container.appendChild(infoColumn);
    gallery.appendChild(container);

    // In this order: each part uses what the ones before it added to shared
    mirdataList(shared);
    mirdataCombinePanel(shared);
    shared.applyFilters();
    mirdataSplitter(shared); // measures the list, so after it is filled
    mirdataPanel(shared);

    const scrollers = [document.getElementById("left-sidebar"), listColumn, infoColumn].filter(Boolean);
    scrollers.forEach((el) => el.addEventListener("scroll", () => flashScrollbar(el), { passive: true }));
    window.addEventListener("load", () => scrollers.forEach(flashScrollbar));
});
