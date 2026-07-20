"use strict";

document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-copy-value]").forEach((button) => {
        button.addEventListener("click", async () => {
            const value = button.getAttribute("data-copy-value") || "";
            if (!value) {
                return;
            }

            const originalText = button.textContent;
            try {
                await navigator.clipboard.writeText(value);
                button.textContent = "Copied";
            } catch (_error) {
                const input = document.createElement("textarea");
                input.value = value;
                input.setAttribute("readonly", "");
                input.style.position = "fixed";
                input.style.opacity = "0";
                document.body.appendChild(input);
                input.select();
                document.execCommand("copy");
                input.remove();
                button.textContent = "Copied";
            }

            window.setTimeout(() => {
                button.textContent = originalText;
            }, 1800);
        });
    });

    document.querySelectorAll("[data-confirm-form]").forEach((form) => {
        form.addEventListener("submit", (event) => {
            const message = form.getAttribute("data-confirm-form");
            if (message && !window.confirm(message)) {
                event.preventDefault();
            }
        });
    });

    document.querySelectorAll(".admin-permission-card").forEach((card) => {
        const toggle = card.querySelector("[data-permission-toggle]");
        const count = card.querySelector("[data-permission-count]");

        if (!toggle || !count) {
            return;
        }

        const syncState = () => {
            count.disabled = !toggle.checked;
            card.classList.toggle(
                "admin-permission-disabled",
                !toggle.checked,
            );
        };

        toggle.addEventListener("change", syncState);
        syncState();
    });
});

document.addEventListener("DOMContentLoaded", () => {
    const statusField = document.querySelector("[data-rsvp-status]");
    const guestCountField = document.querySelector("[data-rsvp-guest-count]");

    if (!statusField || !guestCountField) {
        return;
    }

    let rememberedCount = Number.parseInt(guestCountField.value || "1", 10);
    if (!Number.isFinite(rememberedCount) || rememberedCount < 1) {
        rememberedCount = 1;
    }

    const syncGuestCount = () => {
        if (statusField.value === "No") {
            const currentCount = Number.parseInt(guestCountField.value || "0", 10);
            if (Number.isFinite(currentCount) && currentCount > 0) {
                rememberedCount = currentCount;
            }
            guestCountField.value = "0";
            guestCountField.readOnly = true;
            guestCountField.setAttribute("aria-disabled", "true");
        } else {
            guestCountField.readOnly = false;
            guestCountField.removeAttribute("aria-disabled");
            if (statusField.value === "Yes"
                && Number.parseInt(guestCountField.value || "0", 10) < 1) {
                guestCountField.value = String(Math.max(1, rememberedCount));
            }
        }
    };

    statusField.addEventListener("change", syncGuestCount);
    syncGuestCount();
});
