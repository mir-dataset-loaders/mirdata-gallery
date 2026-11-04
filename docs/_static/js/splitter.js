// The splitter between the list and the panel (layout.css, shown on hover):
// dragging it, or the arrow keys on it, set the list's width, from its
// narrowest (350px) up to its share of the page at its widest (687px of
// 687 + 850, page.css .container): the list and the panel trade width,
// but never leave a blank. So a laptop's list can widen enough to show
// License, and the widest page's, at that share by default, can narrow, the
// panel growing past its 850px (its charts with it). A double-click goes
// back to the default widths. The browser remembers the share; without
// storage it lasts this visit. Not in the narrow layout (no splitter there).
window.mirdataSplitter = function (shared) {
    const { container, splitter, listColumn, infoColumn, showPage } = shared;

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

    // The splitter's bar in the middle of the blank between the list's rows
    // and the panel: the list's scrollbar room (none for an overlay
    // scrollbar) and its right padding widen that blank, so the bar moves
    // left by half of them (layout.css, --bar-shift)
    const listRight = listColumn.offsetWidth - listColumn.clientWidth + parseFloat(getComputedStyle(listColumn).paddingRight);
    splitter.style.setProperty("--bar-shift", `${-listRight / 2}px`);

    // The list's narrowest and widest: 350px, and its share of the widest page
    function listBounds() {
        return [MIN_LIST, Math.max(MIN_LIST, Math.min(MAX_LIST, listRoom() * MAX_SHARE))];
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
            infoColumn.style.flexGrow = "";
            return;
        }
        listColumn.style.flex = `0 0 ${Math.min(max, Math.max(min, share * listRoom()))}px`;
        infoColumn.style.flexGrow = "1"; // the rest, past its 850px when the list is narrower than its default
    }

    function saveShare() {
        try {
            if (share === null) localStorage.removeItem(SHARE_KEY);
            else localStorage.setItem(SHARE_KEY, String(share));
        } catch (e) {
            // no storage: this visit only
        }
    }

    let resizing = 0;
    window.addEventListener("resize", () => {
        cancelAnimationFrame(resizing);
        resizing = requestAnimationFrame(() => {
            applyShare(); // the list's width dragged, for the new width
            showPage();
        });
    });

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
};
