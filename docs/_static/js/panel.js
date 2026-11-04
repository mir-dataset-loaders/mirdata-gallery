// What a panel does: hover text, annotation type focus, and Statistics, larger.
window.mirdataPanel = function (shared) {
    const { cards, sidebar, listColumn, infoColumn, combine, combinedPanel, showSources, shownCombined, onCombinedClick } = shared;

    // Plot bars, the filters' AND / OR buttons and the list's type dots: show
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

    // Annotation type focus: a click on a type in a panel's At a glance (a
    // dataset's or the combination's) focuses that type alone: the panel's
    // Statistics shows only its plots and the other types dim; a click on the
    // only type focused shows them all again. Cmd-click or Ctrl-click adds a type
    // to the ones focused, or takes it out. The combination's are kept in
    // combine.typeFocus, as its panel is redrawn. The "Annotation types" title
    // gets a hint saying so.
    function focusTypes(panel, types) {
        panel.querySelectorAll(".glance-tags [data-ann]").forEach((tag) => {
            tag.setAttribute("role", "button");
            tag.tabIndex = 0;
            tag.setAttribute("aria-pressed", String(types.includes(tag.dataset.ann)));
        });
        const tags = panel.querySelector(".glance-tags");
        if (tags && tags.querySelector("[data-ann]")) {
            tags.classList.toggle("has-focus", types.length > 0);
            const title = tags.previousElementSibling;
            if (!title.querySelector(".box-hint")) {
                title.insertAdjacentHTML("beforeend", '<span class="box-hint">Click a type to focus it in the plots (⌘/Ctrl-click for several)</span>');
            }
        }
        const grid = panel.querySelector(".plot-grid");
        if (!grid) return;
        const plots = [...grid.querySelectorAll(".plot")];
        plots.forEach((fig) => {
            fig.style.display = !types.length || types.includes(fig.dataset.type) ? "" : "none";
        });
        // types without plots: a note, above the plots of the others
        const withoutPlots = types.filter((t) => !plots.some((fig) => fig.dataset.type === t));
        let empty = panel.querySelector(".type-empty");
        if (withoutPlots.length) {
            if (!empty) {
                empty = document.createElement("p");
                empty.className = "stats-note type-empty";
                grid.before(empty);
            }
            empty.textContent = `No ${withoutPlots.join(", ")} plots yet.`;
        } else if (empty) {
            empty.remove();
        }
    }
    cards.forEach((card) => focusTypes(card, []));
    infoColumn.addEventListener("click", (e) => {
        const tag = e.target.closest(".glance-tags [data-ann]");
        if (!tag) return;
        const panel = tag.closest(".gallery-cards-information > section");
        const focused = [...panel.querySelectorAll('.glance-tags [data-ann][aria-pressed="true"]')].map((t) => t.dataset.ann);
        const type = tag.dataset.ann;
        let types;
        if (e.metaKey || e.ctrlKey) {
            types = focused.includes(type) ? focused.filter((t) => t !== type) : [...focused, type];
        } else {
            types = focused.length === 1 && focused[0] === type ? [] : [type];
        }
        if (panel === combinedPanel) combine.typeFocus = types;
        focusTypes(panel, types);
    });
    // Enter or Space on a focused type clicks it, with Cmd or Ctrl if held
    infoColumn.addEventListener("keydown", (e) => {
        if ((e.key === "Enter" || e.key === " ") && e.target.matches(".glance-tags [data-ann]")) {
            e.preventDefault();
            e.target.dispatchEvent(new MouseEvent("click", { bubbles: true, metaKey: e.metaKey, ctrlKey: e.ctrlKey }));
        }
    });

    // Statistics, larger: a button at the end of a panel's Statistics title
    // (one with plots) opens the box in a pop-up over the page, at the pop-up's
    // width, so its plots scale up with it (charts.css, .stats-dialog). The
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

    // in the panel column, so the panel's styles and hover text (above) work in it too;
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
        const panel = combined ? combinedPanel : shared.activeItem && shared.activeItem.card;
        const grid = panel && panel.querySelector(".plot-grid");
        if (!grid) {
            statsDialog.close();
            return;
        }
        const copy = grid.closest(".panel-box").cloneNode(true);
        copy.querySelector(".stats-expand")?.remove();
        statsDialog.querySelector(".stats-dialog-title").textContent = combined ? `${shownCombined().length} Datasets Combined` : shared.activeItem.title;
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

    Object.assign(shared, { moveTips, focusTypes, addStatsButton, refreshStats });
};
