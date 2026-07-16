const TRANSITION_MS = 620;
const INTERVAL_MS = 7500;

function decodeImage(image) {
    if (typeof image.decode === "function") {
        return image.decode().catch(() => undefined);
    }
    if (image.complete) return Promise.resolve();
    return new Promise((resolve) => {
        image.addEventListener("load", resolve, { once: true });
        image.addEventListener("error", resolve, { once: true });
    });
}

function applySlide(buffer, slide, highPriority = false) {
    const avif = buffer.querySelector('[data-slide-source="avif"]');
    const webp = buffer.querySelector('[data-slide-source="webp"]');
    const image = buffer.querySelector("[data-slide-image]");

    buffer.style.setProperty("--position-desktop", slide.positionDesktop);
    buffer.style.setProperty("--position-mobile", slide.positionMobile);
    avif.srcset = slide.avifSrcset;
    webp.srcset = slide.webpSrcset;
    image.fetchPriority = highPriority ? "high" : "auto";
    image.src = slide.fallback;
    return decodeImage(image);
}

export function createSlideshow() {
    const root = document.querySelector("[data-slideshow-root]");
    const dataNode = document.getElementById("slideshow-data");
    if (!root || !dataNode) return null;

    const slides = JSON.parse(dataNode.textContent || "[]");
    const buffers = Array.from(root.querySelectorAll("[data-slide-buffer]"));
    if (!slides.length || buffers.length !== 2) return null;

    let currentIndex = 0;
    let activeBufferIndex = 0;
    let transitioning = false;
    let timerId = null;

    function updateDots() {
        document.querySelectorAll("[data-slide-index]").forEach((dot) => {
            const active = Number(dot.dataset.slideIndex) === currentIndex;
            dot.classList.toggle("is-active", active);
            if (active) dot.setAttribute("aria-current", "true");
            else dot.removeAttribute("aria-current");
        });
    }

    function restartTimer() {
        if (timerId) window.clearInterval(timerId);
        timerId = window.setInterval(() => goTo(currentIndex + 1, false), INTERVAL_MS);
    }

    async function goTo(index, restart = true) {
        if (transitioning) return;
        const nextIndex = (index + slides.length) % slides.length;
        if (nextIndex === currentIndex) {
            if (restart) restartTimer();
            return;
        }

        transitioning = true;
        const outgoing = buffers[activeBufferIndex];
        const incomingIndex = activeBufferIndex === 0 ? 1 : 0;
        const incoming = buffers[incomingIndex];

        incoming.classList.remove("is-active", "is-leaving");
        await applySlide(incoming, slides[nextIndex]);

        requestAnimationFrame(() => {
            incoming.classList.add("is-active");
            outgoing.classList.add("is-leaving");
        });

        window.setTimeout(() => {
            outgoing.classList.remove("is-active", "is-leaving");
            activeBufferIndex = incomingIndex;
            currentIndex = nextIndex;
            transitioning = false;
            updateDots();
        }, TRANSITION_MS + 40);

        if (restart) restartTimer();
    }

    document.addEventListener("click", (event) => {
        const previous = event.target.closest("[data-slide-previous]");
        const next = event.target.closest("[data-slide-next]");
        const dot = event.target.closest("[data-slide-index]");
        if (previous) goTo(currentIndex - 1);
        if (next) goTo(currentIndex + 1);
        if (dot) goTo(Number(dot.dataset.slideIndex));
    });

    document.addEventListener("visibilitychange", () => {
        if (document.hidden && timerId) {
            window.clearInterval(timerId);
            timerId = null;
        } else if (!document.hidden) {
            restartTimer();
        }
    });

    updateDots();
    restartTimer();

    return { goTo, getCurrentIndex: () => currentIndex };
}
