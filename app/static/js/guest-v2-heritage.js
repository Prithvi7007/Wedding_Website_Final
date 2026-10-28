/*
 * Private Heritage preview interactions.
 * Reuses the wedding's real six-photo manifest and countdown module.
 * Slides are not advanced automatically for reduced-motion visitors.
 */
import { mountCountdown } from "./countdown.js";

const imageData = document.getElementById("slideshow-data");
const slideshow = document.querySelector("[data-slideshow-root]");
const buffers = slideshow ? [...slideshow.querySelectorAll("[data-slide-buffer]")] : [];
const dots = [...document.querySelectorAll("[data-slide-index]")];
const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
const slides = imageData ? JSON.parse(imageData.textContent || "[]") : [];
const INTERVAL_MS = 7500;
const TRANSITION_MS = 650;
let active = 0;
let bufferIndex = 0;
let timer = null;
let busy = false;

function updateDots() {
    for (const dot of dots) {
        const chosen = Number(dot.dataset.slideIndex) === active;
        dot.classList.toggle("is-active", chosen);
        if (chosen) dot.setAttribute("aria-current", "true");
        else dot.removeAttribute("aria-current");
    }
}

async function loadBuffer(buffer, slide) {
    const avif = buffer.querySelector('[data-slide-source="avif"]');
    const webp = buffer.querySelector('[data-slide-source="webp"]');
    const image = buffer.querySelector("[data-slide-image]");
    buffer.style.setProperty("--position-desktop", slide.positionDesktop);
    buffer.style.setProperty("--position-mobile", slide.positionMobile);
    avif.srcset = slide.avifSrcset;
    webp.srcset = slide.webpSrcset;
    image.src = slide.fallback;
    if (image.decode) await image.decode().catch(() => {});
    else if (!image.complete) {
        await new Promise(resolve => {
            image.addEventListener("load", resolve, { once: true });
            image.addEventListener("error", resolve, { once: true });
        });
    }
}

function startTimer() {
    if (timer !== null) {
        clearInterval(timer);
        timer = null;
    }
    if (document.hidden || motion.matches || slides.length < 2) return;
    timer = setInterval(() => goTo(active + 1, false), INTERVAL_MS);
}

async function goTo(index, restart = true) {
    if (busy || slides.length < 2 || buffers.length !== 2) return;
    const next = (index + slides.length) % slides.length;
    if (next === active) {
        if (restart) startTimer();
        return;
    }
    busy = true;
    const incomingIndex = bufferIndex === 0 ? 1 : 0;
    const outgoing = buffers[bufferIndex];
    const incoming = buffers[incomingIndex];
    incoming.classList.remove("is-active", "is-leaving");
    await loadBuffer(incoming, slides[next]);
    incoming.classList.add("is-active");
    outgoing.classList.add("is-leaving");

    const delay = motion.matches ? 0 : TRANSITION_MS;
    window.setTimeout(() => {
        outgoing.classList.remove("is-active", "is-leaving");
        bufferIndex = incomingIndex;
        active = next;
        busy = false;
        updateDots();
        if (restart) startTimer();
    }, delay);
}

if (slideshow && buffers.length === 2 && slides.length) {
    document.querySelector("[data-slide-previous]")?.addEventListener("click", () => goTo(active - 1));
    document.querySelector("[data-slide-next]")?.addEventListener("click", () => goTo(active + 1));
    for (const dot of dots) {
        dot.addEventListener("click", () => goTo(Number(dot.dataset.slideIndex)));
    }
    document.addEventListener("visibilitychange", startTimer);
    motion.addEventListener("change", startTimer);
    updateDots();
    startTimer();
    document.documentElement.dataset.heritageGalleryReady = "true";
}

mountCountdown(document);

const toggle = document.querySelector("[data-heritage-transparency]");
if (toggle) {
    const update = opaque => {
        document.body.dataset.heritageTransparency = opaque ? "solid" : "glass";
        toggle.setAttribute("aria-pressed", String(opaque));
        toggle.setAttribute("aria-label", opaque ? "Enable transparent glass" : "Use solid glass");
        toggle.textContent = opaque ? "Frosted glass" : "Solid glass";
    };
    update(false);
    toggle.addEventListener("click", () => update(toggle.getAttribute("aria-pressed") !== "true"));
}
