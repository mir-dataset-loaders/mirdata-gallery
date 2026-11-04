// Combine mode's button and panel.
window.mirdataCombinePanel = function (shared) {
    const { cardData, listColumn, infoColumn, table, selectCard, flashScrollbar } = shared;

    // Combine mode: the Combine button switches what a click on a dataset does.
    // Off, the click shows that dataset; on, it adds the dataset to the
    // combination or removes it, and the panel shows the combination
    // (combine.js works out its text). Cmd-click or Ctrl-click switches it on
    // too. A combination of one shows that dataset's own panel, and removing
    // datasets down to one switches Combine off, on that one. A dataset the
    // filters hide leaves the panel too, but stays in the combination with its
    // colour and picks, back when the filters let it through again
    // (shownCombined).
    // colours: each selected dataset's colour, given when it joins (combine.js, nextColour)
    // focus: the dataset whose part of each plot is shown (its chip's name clicked), or null: stacked
    // typeFocus: the annotation types whose plots alone are shown (panel.js); none: all
    // picks: the property a dataset adds to a combined plot, picked in the plot's sources bubble
    // (charts.js, sourcesHtml), {plot's pickKey: {dataset title: property}}; one not picked adds
    // its first (combine.js)
    // openSources: the pickKey of the plot whose sources bubble is open (showSources), or null
    const combine = { on: false, selected: [], colours: new Map(), lastClicked: null, focus: null, typeFocus: [], picks: {}, openSources: null };
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
        combine.typeFocus = [];
        combine.picks = {};
        combine.openSources = null;
        if (combine.on) {
            // the dataset on show is the first one of the combination, purple as in its panel
            if (shared.activeItem && shared.activeItem.card.style.display !== "none") join(shared.activeItem);
            combine.lastClicked = null;
            showCombination();
        } else {
            // back to one dataset: the last one clicked
            const last = combine.lastClicked || shared.activeItem;
            combinedPanel.style.display = "none";
            cardData.forEach((d) => d.btn.classList.remove("active"));
            selectCard(last);
            shared.applyFilters(false); // the first visible one instead, if the filters hide it
            shared.refreshStats(); // the pop-up, when open, shows that one's Statistics now
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

    // The combined datasets the filters let through: the ones the panel shows
    function shownCombined() {
        return combine.selected.filter((d) => shared.matched.includes(d));
    }

    function showCombination() {
        const shown = shownCombined();
        if (shown.length > 1) {
            selectCard(null); // hides the dataset on show
            fillCombinedPanel();
            combinedPanel.style.display = "flex";
        } else {
            // one (Combine just switched on, or the filters hide the rest): its own panel; none: nothing
            combinedPanel.style.display = "none";
            selectCard(shown[0] || null);
            shared.refreshStats();
        }
        cardData.forEach((d) => d.btn.classList.toggle("active", combine.selected.includes(d)));
    }

    // The combined panel: its title and the datasets' names, At a glance, and
    // Statistics: the datasets again (a chip each: a click on its name focuses
    // it, one more shows them all again, and × removes it; its dot is the
    // dataset's colour in the plots, so the chips are the legend), the ones the
    // filters hide, each dataset's notes, and the plots pooled from theirs
    // (combine.js), stacked by dataset or showing the focused one's part (none
    // while the filters hide it)
    function fillCombinedPanel() {
        const escape = mirdataCharts.escapeHtml;
        const selected = shownCombined();
        const hidden = combine.selected.filter((d) => !selected.includes(d));
        const focus = selected.includes(combine.focus) ? combine.focus.title : null;
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
            (hidden.length ? `<p class="combine-hidden">Hidden by the filters: ${hidden.map((d) => escape(d.title)).join(", ")}</p>` : "") +
            '<p class="combine-chips-hint">Click a name to focus it in the plots</p>' +
            notes.map((text) => `<p class="stats-note">${escape(text)}</p>`).join("") +
            (plots.length ? `<div class="plot-grid">${mirdataCharts.plotGridHtml(plots, focus)}</div>` : "") +
            "</div>";
        shared.moveTips(combinedPanel);
        flashScrollbar(infoColumn);
        combine.typeFocus = combine.typeFocus.filter((t) => types.includes(t)); // not those whose datasets are all removed
        shared.focusTypes(combinedPanel, combine.typeFocus);
        shared.addStatsButton(combinedPanel);
        showSources(combinedPanel);
        shared.refreshStats();
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
        shared.refreshStats();
    }
    document.addEventListener("pointerdown", (e) => {
        if (combine.openSources !== null && !e.target.closest(".plot-sources, .plot-sources-btn")) closeSources();
    });
    document.addEventListener("keydown", (e) => {
        if (e.key !== "Escape" || combine.openSources === null) return;
        e.preventDefault(); // just the bubble, not the pop-up around it too
        closeSources();
    });

    // A click in the combination's Statistics, on its panel or in the pop-up (panel.js)
    function onCombinedClick(e) {
        // a plot's sources button: its bubble opens, or closes
        const sources = e.target.closest(".plot-sources-btn");
        if (sources) {
            const key = sources.closest(".plot").dataset.pickKey;
            combine.openSources = combine.openSources === key ? null : key;
            showSources(combinedPanel);
            shared.refreshStats();
            return;
        }
        // a property's button in the bubble: that dataset adds it to the plot
        const pick = e.target.closest(".plot-pick");
        if (pick) {
            const { key, name, prop } = pick.dataset;
            combine.picks[key] = { ...combine.picks[key], [name]: prop };
            fillCombinedPanel();
            return;
        }
        // a chip's index: its place among the datasets shown
        const name = e.target.closest(".combine-name");
        if (name) {
            const item = shownCombined()[Number(name.dataset.index)];
            combine.focus = combine.focus === item ? null : item;
            fillCombinedPanel();
            return;
        }
        const remove = e.target.closest(".combine-remove");
        if (remove) removeCombined(shownCombined()[Number(remove.dataset.index)]);
    }
    combinedPanel.addEventListener("click", onCombinedClick);

    Object.assign(shared, {
        combine, combineBar, combineBtn, combinedPanel,
        toggleCombined, showCombination, shownCombined, showSources, onCombinedClick,
    });
};
