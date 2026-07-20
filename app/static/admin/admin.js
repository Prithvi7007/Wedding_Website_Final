"use strict";

const selectAll = (selector, scope = document) => (
    Array.from(scope.querySelectorAll(selector))
);

function initializeCopyButtons() {
    selectAll("[data-copy-value]").forEach((button) => {
        button.addEventListener("click", async () => {
            const value = button.getAttribute("data-copy-value") || "";
            if (!value) {
                return;
            }

            const originalText = button.textContent.trim();
            try {
                await navigator.clipboard.writeText(value);
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
            }

            button.textContent = "Copied";
            window.setTimeout(() => {
                button.textContent = originalText;
            }, 1800);
        });
    });
}

function initializeForms() {
    selectAll("form").forEach((form) => {
        form.addEventListener("submit", (event) => {
            const message = form.getAttribute("data-confirm-form");
            if (message && !window.confirm(message)) {
                event.preventDefault();
                return;
            }

            if (event.defaultPrevented || form.classList.contains("is-submitting")) {
                event.preventDefault();
                return;
            }

            window.setTimeout(() => {
                form.classList.add("is-submitting");
                form.setAttribute("aria-busy", "true");
                selectAll('button[type="submit"], input[type="submit"]', form)
                    .forEach((control) => {
                        control.disabled = true;
                    });
            }, 0);
        });
    });
}

function initializeAutoSubmitFilters() {
    selectAll("form[data-auto-submit]").forEach((form) => {
        selectAll("select", form).forEach((select) => {
            select.addEventListener("change", () => {
                if (form.classList.contains("is-submitting")) {
                    return;
                }
                if (typeof form.requestSubmit === "function") {
                    form.requestSubmit();
                } else {
                    form.submit();
                }
            });
        });
    });
}

function initializePermissionCards() {
    selectAll(".admin-permission-card").forEach((card) => {
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
}

function initializeRsvpForm() {
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
            const currentCount = Number.parseInt(
                guestCountField.value || "0",
                10,
            );
            if (Number.isFinite(currentCount) && currentCount > 0) {
                rememberedCount = currentCount;
            }
            guestCountField.value = "0";
            guestCountField.readOnly = true;
            guestCountField.setAttribute("aria-disabled", "true");
            return;
        }

        guestCountField.readOnly = false;
        guestCountField.removeAttribute("aria-disabled");
        if (
            statusField.value === "Yes"
            && Number.parseInt(guestCountField.value || "0", 10) < 1
        ) {
            guestCountField.value = String(Math.max(1, rememberedCount));
        }
    };

    statusField.addEventListener("change", syncGuestCount);
    syncGuestCount();
}

function initializeClickableRows() {
    selectAll("[data-row-href]").forEach((row) => {
        const openRow = () => {
            const destination = row.getAttribute("data-row-href");
            if (destination) {
                window.location.assign(destination);
            }
        };

        row.addEventListener("click", (event) => {
            if (event.target.closest(
                "a, button, input, select, textarea, summary, details",
            )) {
                return;
            }
            openRow();
        });

        row.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                openRow();
            }
        });
    });
}

function initializeFlashMessages() {
    selectAll("[data-admin-flash]").forEach((flash) => {
        let dismissed = false;
        const dismiss = () => {
            if (dismissed) {
                return;
            }
            dismissed = true;
            flash.classList.add("is-dismissing");
            window.setTimeout(() => flash.remove(), 220);
        };

        const button = flash.querySelector("[data-dismiss-flash]");
        if (button) {
            button.addEventListener("click", dismiss);
        }
        window.setTimeout(dismiss, 6500);
    });
}

document.addEventListener("DOMContentLoaded", () => {
    initializeCopyButtons();
    initializeForms();
    initializeAutoSubmitFilters();
    initializePermissionCards();
    initializeRsvpForm();
    initializeClickableRows();
    initializeFlashMessages();
});
