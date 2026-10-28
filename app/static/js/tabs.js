let cleanupCurrentTab = () => {};

function setActiveTab(tabName) {
    document.body.dataset.activeTab = tabName;
    document.querySelectorAll("[data-tab-name]").forEach((link) => {
        const active = link.dataset.tabName === tabName;
        link.classList.toggle("is-active", active);
        if (active) link.setAttribute("aria-current", "page");
        else link.removeAttribute("aria-current");
    });
}

// Target only event cards rendered for this invitation. Unknown IDs fall
// back to the Schedule introduction without fetching any other event.
function focusLinkedScheduleEvent(content, eventId) {
    if (!eventId) return false;
    const card = [...content.querySelectorAll("[data-schedule-event]")]
        .find((element) => element.dataset.scheduleEvent === eventId);
    if (!card) return false;

    content.querySelectorAll("[data-action='journey']").forEach((stop) => {
        const active = stop.dataset.eventTarget === card.id;
        stop.classList.toggle("is-active", active);
        if (active) stop.setAttribute("aria-current", "step");
        else stop.removeAttribute("aria-current");
    });
    const heading = card.querySelector("h3");
    if (heading) {
        heading.tabIndex = -1;
        heading.focus({ preventScroll: true });
    }
    card.scrollIntoView({ behavior: "auto", block: "start" });
    return true;
}

export function mountFragmentNavigation(onContentMounted, initialCleanup = () => {}) {
    const content = document.getElementById("tab-content");
    if (!content) return;
    cleanupCurrentTab = initialCleanup;
    let currentNavigation = null;
    let navigationSequence = 0;

    async function navigate(link, pushHistory = true, historyEventId = null) {
        const tabName = link.dataset.tabName;
        const fragmentUrl = link.dataset.fragmentUrl;
        if (!tabName || !fragmentUrl) return;

        // Only the newest requested tab may render, update browser history,
        // or clear loading state. Cancel the older fetch when possible and
        // guard the response body read if cancellation comes too late.
        const sequence = ++navigationSequence;
        currentNavigation?.abort();
        const controller = new AbortController();
        currentNavigation = controller;

        content.setAttribute("aria-busy", "true");
        try {
            const response = await fetch(fragmentUrl, {
                credentials: "same-origin",
                headers: { "X-Requested-With": "XMLHttpRequest" },
                signal: controller.signal,
            });
            if (sequence !== navigationSequence) return;

            if (response.status === 401) {
                window.location.assign("/");
                return;
            }

            if (!response.ok) throw new Error(`Tab request failed: ${response.status}`);

            const markup = await response.text();
            if (sequence !== navigationSequence) return;

            cleanupCurrentTab();
            content.innerHTML = markup;
            setActiveTab(tabName);
            cleanupCurrentTab = onContentMounted(content) || (() => {});

            if (pushHistory) {
                history.pushState({ tabName }, "", link.href);
            }
            content.focus({ preventScroll: true });
            const eventId = historyEventId || new URL(link.href, location.href).searchParams.get("event");
            if (tabName !== "schedule" || !focusLinkedScheduleEvent(content, eventId)) {
                window.scrollTo({ top: 0, behavior: "smooth" });
            }
        } catch (error) {
            if (sequence !== navigationSequence || error?.name === "AbortError") return;
            console.error(error);
            window.location.assign(link.href);
        } finally {
            if (sequence === navigationSequence) {
                currentNavigation = null;
                content.removeAttribute("aria-busy");
            }
        }
    }

    document.addEventListener("click", (event) => {
        const link = event.target.closest("a[data-tab-name][data-fragment-url]");
        if (!link || event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        navigate(link);
    });

    window.addEventListener("popstate", () => {
        const params = new URLSearchParams(location.search);
        const tabName = params.get("tab") || "welcome";
        const link = document.querySelector(`a[data-tab-name="${CSS.escape(tabName)}"]`);
        if (link) navigate(link, false, params.get("event"));
    });

    // Copied links and refreshes should land on the same permitted card.
    const params = new URLSearchParams(location.search);
    if (params.get("tab") === "schedule") {
        focusLinkedScheduleEvent(content, params.get("event"));
    }
}
