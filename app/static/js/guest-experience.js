"use strict";
(() => {
    const preferenceKey = "wedding-solid-controls";
    const buttons = Array.from(document.querySelectorAll("[data-solid-controls]"));
    const forcedQueries = ["(max-width: 768px)", "(hover: none)", "(pointer: coarse)",
        "(prefers-reduced-transparency: reduce)", "(prefers-contrast: more)", "(forced-colors: active)"]
        .map(query => window.matchMedia(query));
    let solid = false;
    try { solid = localStorage.getItem(preferenceKey) === "true"; } catch (error) { /* Solid fallback remains available. */ }
    function applyEffects() {
        const forced = forcedQueries.some(query => query.matches);
        document.documentElement.dataset.experienceEffects = solid || forced ? "solid" : "glass";
        for (const button of buttons) {
            button.hidden = forced;
            button.setAttribute("aria-pressed", String(solid));
            button.textContent = "Solid controls";
        }
    }
    buttons.forEach(button => button.addEventListener("click", () => {
        solid = !solid;
        try { localStorage.setItem(preferenceKey, String(solid)); } catch (error) { /* Session-only preference. */ }
        applyEffects();
    }));
    forcedQueries.forEach(query => query.addEventListener("change", applyEffects));
    applyEffects();

    for (const form of document.querySelectorAll("[data-family-assignment-form]")) {
        const inputs = Array.from(form.querySelectorAll('input[name="invitation_ids"]'));
        const all = form.querySelector("[data-select-all]");
        const count = form.querySelector("[data-selection-count]");
        const submit = form.querySelector('button[type="submit"]');
        function updateSelection() {
            const selected = inputs.filter(input => input.checked).length;
            if (all) {
                all.checked = inputs.length > 0 && selected === inputs.length;
                all.indeterminate = selected > 0 && selected < inputs.length;
            }
            if (count) count.textContent = selected ? `${selected} ${selected === 1 ? "family" : "families"} selected` : "Select families above";
            if (submit) submit.disabled = selected === 0;
        }
        all?.addEventListener("change", () => {
            inputs.forEach(input => { input.checked = all.checked; });
            updateSelection();
        });
        inputs.forEach(input => input.addEventListener("change", updateSelection));
        updateSelection();
    }
})();
