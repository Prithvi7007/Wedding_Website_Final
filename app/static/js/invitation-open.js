(() => {
    "use strict";

    const form = document.getElementById("open-invitation-form");
    const button = document.getElementById("open-invitation-btn");

    if (!form || !button) {
        return;
    }

    const label = button.querySelector(".btn-label");

    const resetButton = () => {
        button.disabled = false;
        button.classList.remove("is-loading");
        button.setAttribute("aria-busy", "false");

        if (label) {
            label.textContent = "Open Invitation";
        }
    };

    form.addEventListener("submit", () => {
        button.disabled = true;
        button.classList.add("is-loading");
        button.setAttribute("aria-busy", "true");

        if (label) {
            label.textContent = "Opening Invitation";
        }
    });

    window.addEventListener("pageshow", resetButton);
})();
