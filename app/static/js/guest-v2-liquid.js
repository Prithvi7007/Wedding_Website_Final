/* Guest V2, preview only: user-controlled transparency.
   System accessibility media queries always override this preference. */
(() => {
    "use strict";

    const toggle = document.querySelector("[data-v2-transparency-toggle]");
    if (!toggle) return;
    const root = document.body;

    function update(opaque) {
        root.dataset.v2Transparency = opaque ? "opaque" : "glass";
        toggle.setAttribute("aria-pressed", String(opaque));
        toggle.textContent = opaque ? "Frosted glass" : "Solid glass";
        toggle.setAttribute(
            "aria-label",
            opaque ? "Enable frosted glass" : "Reduce glass transparency",
        );
    }

    update(false);
    toggle.addEventListener("click", () => {
        update(toggle.getAttribute("aria-pressed") !== "true");
    });
})();
