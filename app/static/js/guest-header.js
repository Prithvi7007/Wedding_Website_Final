// The original wedding signature stays visible without covering the
// photographs and schedule while guests scroll deeper into the invitation.
export function mountCompactGuestHeader() {
    if (!document.body.classList.contains("dashboard-page")) return;
    const header = document.querySelector(".dashboard-header");
    if (!header) return;

    let pendingFrame = false;
    function syncHeader() {
        pendingFrame = false;
        header.classList.toggle("is-condensed", window.scrollY > 160);
    }
    window.addEventListener("scroll", () => {
        if (pendingFrame) return;
        pendingFrame = true;
        window.requestAnimationFrame(syncHeader);
    }, { passive: true });
    syncHeader();
}
