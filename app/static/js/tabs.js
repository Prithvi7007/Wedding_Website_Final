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

export function mountFragmentNavigation(onContentMounted, initialCleanup = () => {}) {
    const content = document.getElementById("tab-content");
    if (!content) return;
    cleanupCurrentTab = initialCleanup;

    async function navigate(link, pushHistory = true) {
        const tabName = link.dataset.tabName;
        const fragmentUrl = link.dataset.fragmentUrl;
        if (!tabName || !fragmentUrl) return;

        content.setAttribute("aria-busy", "true");
        try {
            const response = await fetch(fragmentUrl, {
                credentials: "same-origin",
                headers: { "X-Requested-With": "XMLHttpRequest" },
            });
            if (!response.ok) throw new Error(`Tab request failed: ${response.status}`);

            cleanupCurrentTab();
            content.innerHTML = await response.text();
            setActiveTab(tabName);
            cleanupCurrentTab = onContentMounted(content) || (() => {});

            if (pushHistory) {
                history.pushState({ tabName }, "", link.href);
            }
            window.scrollTo({ top: 0, behavior: "smooth" });
            content.focus({ preventScroll: true });
        } catch (error) {
            console.error(error);
            window.location.assign(link.href);
        } finally {
            content.removeAttribute("aria-busy");
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
        if (link) navigate(link, false);
    });
}
