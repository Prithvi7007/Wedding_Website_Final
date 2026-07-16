const palettes = {
    haldi: [
        ["#f4bd2f", "#ffe58f", "#bf720d"],
        ["#e89a18", "#ffd56a", "#a95c08"],
        ["#ffd45b", "#fff0ad", "#d48714"],
    ],
    hindu: [
        ["#a90f2d", "#ef667a", "#650719"],
        ["#c51f3d", "#f27a8d", "#7e0b24"],
        ["#d43a50", "#f699a5", "#8d1428"],
    ],
    christian: [
        ["#fff5e7", "#ffffff", "#c9aa7f"],
        ["#f2dfc5", "#fffaf2", "#b99a70"],
        ["#f5e4ea", "#fffafd", "#c9a7b0"],
        ["#e4c996", "#fff0c9", "#aa8147"],
    ],
    neutral: [["#efd39b", "#fff7e7", "#9d7440"]],
};

const focusableSelector = [
    "a[href]",
    "button:not([disabled])",
    "input:not([disabled]):not([type='hidden'])",
    "textarea:not([disabled])",
    "select:not([disabled])",
    "[tabindex]:not([tabindex='-1'])",
].join(",");

function isIos() {
    return /iP(?:hone|ad|od)/.test(navigator.userAgent)
        || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}

function burstPetals(eventId) {
    const container = document.getElementById("rsvp-petal-container");
    const card = document.getElementById(`event-card-${eventId}`);
    if (!container || !card || matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const theme = card.dataset.eventTheme || "neutral";
    const palette = palettes[theme] || palettes.neutral;
    const compact = window.innerWidth <= 700;
    const count = isIos() ? 24 : (compact ? 34 : 58);
    const releaseWindow = isIos() ? 520 : (compact ? 680 : 920);
    const burstId = `${Date.now()}-${Math.random()}`;
    container.dataset.burstId = burstId;
    container.replaceChildren();

    for (let index = 0; index < count; index += 1) {
        window.setTimeout(() => {
            if (container.dataset.burstId !== burstId) return;
            const petal = document.createElement("span");
            const [color, highlight, shadow] = palette[Math.floor(Math.random() * palette.length)];
            const duration = 5.2 + Math.random() * 2.5;
            petal.className = `rsvp-petal petal-shape-${1 + Math.floor(Math.random() * 3)}`;
            const vars = {
                "--petal-left": `${Math.random() * 100}vw`,
                "--petal-top": `${-25 - Math.random() * 90}px`,
                "--petal-color": color,
                "--petal-highlight": highlight,
                "--petal-shadow": shadow,
                "--petal-width": `${8 + Math.random() * 8}px`,
                "--petal-height": `${13 + Math.random() * 13}px`,
                "--petal-scale": `${0.72 + Math.random() * 0.7}`,
                "--petal-duration": `${duration}s`,
                "--drift-a": `${-55 + Math.random() * 110}px`,
                "--drift-b": `${-90 + Math.random() * 180}px`,
                "--drift-c": `${-115 + Math.random() * 230}px`,
                "--drift-end": `${-140 + Math.random() * 280}px`,
                "--rotation-start": `${-55 + Math.random() * 110}deg`,
                "--rotation-a": `${90 + Math.random() * 170}deg`,
                "--rotation-b": `${240 + Math.random() * 220}deg`,
                "--rotation-c": `${410 + Math.random() * 220}deg`,
                "--rotation-end": `${580 + Math.random() * 260}deg`,
            };
            Object.entries(vars).forEach(([name, value]) => petal.style.setProperty(name, value));
            petal.addEventListener("animationend", () => petal.remove(), { once: true });
            container.append(petal);
        }, Math.random() * releaseWindow);
    }
}

export function mountSchedule(root = document) {
    const schedule = root.querySelector?.("[data-schedule-root]");
    if (!schedule) return () => {};

    const modalLayer = schedule.querySelector("[data-schedule-modal-layer]");
    if (modalLayer && modalLayer.parentElement !== document.body) {
        document.body.append(modalLayer);
        modalLayer.dataset.portalMounted = "true";
    }
    const interactionRoots = modalLayer ? [schedule, modalLayer] : [schedule];

    const controller = new AbortController();
    const { signal } = controller;
    const backgroundNodes = [
        schedule.querySelector(".schedule-intro"),
        schedule.querySelector(".schedule-journey"),
        schedule.querySelector(".cinematic-event-list"),
    ].filter(Boolean);

    let observer = null;
    let activeOverlay = null;
    let lastTrigger = null;

    function getOverlay(kind, eventId) {
        const selector = `#${CSS.escape(`${kind}-overlay-${eventId}`)}`;
        return modalLayer?.querySelector(selector) || schedule.querySelector(selector);
    }

    function closeMenus() {
        schedule.querySelectorAll(".calendar-popover").forEach((menu) => {
            menu.hidden = true;
        });
        schedule.querySelectorAll(".calendar-toggle").forEach((button) => {
            button.setAttribute("aria-expanded", "false");
        });
    }

    function setBackgroundInteractive(interactive) {
        backgroundNodes.forEach((node) => {
            if (interactive) {
                node.removeAttribute("inert");
                node.removeAttribute("aria-hidden");
            } else {
                node.setAttribute("inert", "");
                node.setAttribute("aria-hidden", "true");
            }
        });
    }

    function setTriggerExpanded(trigger, expanded) {
        trigger?.setAttribute?.("aria-expanded", expanded ? "true" : "false");
    }

    function openOverlay(kind, eventId, trigger) {
        const overlay = getOverlay(kind, eventId);
        if (!overlay) return;

        if (activeOverlay && activeOverlay !== overlay) {
            closeOverlay(activeOverlay.dataset.overlay, activeOverlay.dataset.eventId, false);
        }

        closeMenus();
        lastTrigger = trigger || null;
        activeOverlay = overlay;
        overlay.classList.add("is-open");
        overlay.setAttribute("aria-hidden", "false");
        document.documentElement.classList.add("schedule-modal-open");
        document.body.classList.add("schedule-modal-open", `${kind}-overlay-open`);
        setBackgroundInteractive(false);
        setTriggerExpanded(lastTrigger, true);

        window.setTimeout(() => {
            overlay.querySelector(".overlay-close")?.focus({ preventScroll: true });
        }, 40);
    }

    function closeOverlay(kind, eventId, restoreFocus = true) {
        const overlay = getOverlay(kind, eventId);
        if (!overlay) return;

        overlay.classList.remove("is-open");
        overlay.setAttribute("aria-hidden", "true");
        document.body.classList.remove(`${kind}-overlay-open`);
        document.body.classList.remove("schedule-modal-open");
        document.documentElement.classList.remove("schedule-modal-open");
        setBackgroundInteractive(true);
        setTriggerExpanded(lastTrigger, false);

        const triggerToRestore = lastTrigger;
        activeOverlay = null;
        lastTrigger = null;

        if (restoreFocus) {
            triggerToRestore?.focus?.({ preventScroll: true });
        }
    }

    function trapFocus(event) {
        if (!activeOverlay || event.key !== "Tab") return;
        const focusable = [...activeOverlay.querySelectorAll(focusableSelector)]
            .filter((node) => !node.hidden && node.getClientRects().length > 0);
        if (!focusable.length) {
            event.preventDefault();
            return;
        }

        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    }

    function setActiveJourney(targetId) {
        schedule.querySelectorAll("[data-action='journey']").forEach((stop) => {
            const active = stop.dataset.eventTarget === targetId;
            stop.classList.toggle("is-active", active);
            if (active) stop.setAttribute("aria-current", "step");
            else stop.removeAttribute("aria-current");
        });
    }

    function syncSavedFormState(form, payload) {
        const eventId = form.dataset.eventId;
        const count = form.querySelector("input[name='guest_count']");
        const output = document.getElementById(`guest-count-output-${eventId}`);
        const notes = form.querySelector("textarea[name='notes']");
        if (count) count.value = String(payload.guest_count ?? 0);
        if (output) output.textContent = String(payload.guest_count ?? 0);
        if (notes && typeof payload.notes === "string") notes.value = payload.notes;
    }

    async function submitRsvp(form) {
        if (!form.reportValidity()) return;

        const eventId = form.dataset.eventId;
        const button = form.querySelector(".confirm-response-btn");
        const label = form.querySelector("[data-submit-label]");
        const errorNode = form.querySelector("[data-form-error]");
        const original = label?.textContent || "Confirm Response";
        const formData = new FormData(form);

        if (button) button.disabled = true;
        if (label) label.textContent = "Saving…";
        if (errorNode) {
            errorNode.hidden = true;
            errorNode.textContent = "";
        }

        try {
            const csrf = document.querySelector('meta[name="csrf-token"]')?.content || "";
            const response = await fetch(form.action, {
                method: "POST",
                body: formData,
                credentials: "same-origin",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRFToken": csrf,
                },
            });

            const contentType = response.headers.get("content-type") || "";
            const payload = contentType.includes("application/json")
                ? await response.json()
                : {};

            if (!response.ok || !payload.success) {
                throw new Error(payload.message || "Unable to save your response.");
            }

            const card = document.getElementById(`event-card-${eventId}`);
            card?.querySelector("[data-response-text]")?.replaceChildren(payload.summary_text);
            card?.querySelector("[data-rsvp-trigger-label]")?.replaceChildren("Edit Response");
            if (label) label.textContent = "Update Response";
            syncSavedFormState(form, payload);
            closeOverlay("rsvp", eventId);
            schedule.querySelector("[data-schedule-live]")
                ?.replaceChildren(`Response saved for ${payload.event_title}.`);
            if (payload.celebrate) window.setTimeout(() => burstPetals(eventId), 90);
        } catch (error) {
            if (label) label.textContent = original;
            if (errorNode) {
                errorNode.textContent = error instanceof Error
                    ? error.message
                    : "Unable to save your response.";
                errorNode.hidden = false;
                errorNode.focus?.({ preventScroll: true });
            }
        } finally {
            if (button) button.disabled = false;
        }
    }

    function handleScheduleClick(event) {
        const actionNode = event.target.closest("[data-action]");

        if (!actionNode) {
            if (!event.target.closest(".calendar-menu-wrap")) closeMenus();
            if (event.target.matches("[data-overlay]")) {
                closeOverlay(event.target.dataset.overlay, event.target.dataset.eventId);
            }
            return;
        }

        const { action, eventId } = actionNode.dataset;
        if (action === "journey") {
            const target = document.getElementById(actionNode.dataset.eventTarget);
            if (target) {
                setActiveJourney(target.id);
                target.scrollIntoView({ behavior: "smooth", block: "start" });
            }
        } else if (action === "open-rsvp") {
            openOverlay("rsvp", eventId, actionNode);
        } else if (action === "close-rsvp") {
            closeOverlay("rsvp", eventId);
        } else if (action === "open-attire") {
            openOverlay("attire", eventId, actionNode);
        } else if (action === "close-attire") {
            closeOverlay("attire", eventId);
        } else if (action === "toggle-calendar") {
            const menu = document.getElementById(`calendar-menu-${eventId}`);
            const willOpen = Boolean(menu?.hidden);
            closeMenus();
            if (menu && willOpen) {
                menu.hidden = false;
                actionNode.setAttribute("aria-expanded", "true");
            }
        } else if (action === "adjust-guests") {
            const form = actionNode.closest(".cinematic-rsvp-form");
            const input = form?.querySelector("input[name='guest_count']");
            const output = form?.querySelector("output");
            const checked = form?.querySelector("input[name='attending']:checked");
            if (!input || !output || checked?.value === "No") return;

            const next = Math.max(
                Number(input.min || 0),
                Math.min(
                    Number(input.max || 10),
                    Number(input.value || 0) + Number(actionNode.dataset.delta || 0),
                ),
            );
            input.value = String(next);
            output.textContent = String(next);
        }
    }

    function handleScheduleChange(event) {
        const input = event.target.closest("[data-action='attendance-choice']");
        if (!input) return;

        const form = input.closest(".cinematic-rsvp-form");
        input.closest(".attendance-choices")
            ?.querySelectorAll(".attendance-choice")
            .forEach((choice) => choice.classList.toggle("is-selected", choice.contains(input)));

        const wrap = form?.querySelector(".guest-stepper-wrap");
        const count = form?.querySelector("input[name='guest_count']");
        const output = form?.querySelector("output");
        const disabled = input.value === "No";
        wrap?.classList.toggle("is-disabled", disabled);

        if (count && output) {
            if (disabled) {
                count.value = "0";
                output.textContent = "0";
            } else if (Number(count.value) < 1) {
                count.value = "1";
                output.textContent = "1";
            }
        }
    }

    function handleScheduleSubmit(event) {
        const form = event.target.closest(".cinematic-rsvp-form");
        if (!form) return;
        event.preventDefault();
        submitRsvp(form);
    }

    interactionRoots.forEach((interactionRoot) => {
        interactionRoot.addEventListener("click", handleScheduleClick, { signal });
        interactionRoot.addEventListener("change", handleScheduleChange, { signal });
        interactionRoot.addEventListener("submit", handleScheduleSubmit, { signal });
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && activeOverlay) {
            event.preventDefault();
            closeOverlay(activeOverlay.dataset.overlay, activeOverlay.dataset.eventId);
            return;
        }
        trapFocus(event);
    }, { signal });

    document.addEventListener("touchmove", (event) => {
        if (!activeOverlay) return;
        if (!event.target.closest(".event-rsvp-sheet, .attire-inspiration-sheet")) {
            event.preventDefault();
        }
    }, { signal, passive: false });

    const cards = [...schedule.querySelectorAll("[data-schedule-event]")];
    if ("IntersectionObserver" in window && cards.length) {
        observer = new IntersectionObserver((entries) => {
            if (activeOverlay) return;
            const visible = entries
                .filter((entry) => entry.isIntersecting)
                .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
            if (visible[0]) setActiveJourney(visible[0].target.id);
        }, {
            rootMargin: "-28% 0px -54% 0px",
            threshold: [0.12, 0.3, 0.55],
        });
        cards.forEach((card) => observer.observe(card));
    }

    return () => {
        if (activeOverlay) {
            closeOverlay(activeOverlay.dataset.overlay, activeOverlay.dataset.eventId, false);
        }
        controller.abort();
        observer?.disconnect();
        closeMenus();
        setBackgroundInteractive(true);
        document.documentElement.classList.remove("schedule-modal-open");
        document.body.classList.remove(
            "schedule-modal-open",
            "rsvp-overlay-open",
            "attire-overlay-open",
        );
        if (modalLayer?.dataset.portalMounted === "true") {
            modalLayer.remove();
        }
    };
}
