export function runLoginSparkles() {
    if (document.body.dataset.loginEffect !== "success") return;
    const canvas = document.getElementById("celebration-canvas");
    if (!canvas) return;

    const context = canvas.getContext("2d", { alpha: true });
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    const colors = ["#916926", "#d7c08a", "#c4935f", "#fff1d6"];
    const particles = Array.from({ length: 38 }, () => ({
        x: Math.random(),
        y: -Math.random() * 0.25,
        vx: (Math.random() - 0.5) * 0.0008,
        vy: 0.00022 + Math.random() * 0.00034,
        rotation: Math.random() * Math.PI,
        vr: (Math.random() - 0.5) * 0.06,
        size: 5 + Math.random() * 6,
        color: colors[Math.floor(Math.random() * colors.length)],
    }));

    function resize() {
        canvas.width = Math.round(innerWidth * ratio);
        canvas.height = Math.round(innerHeight * ratio);
        canvas.style.width = `${innerWidth}px`;
        canvas.style.height = `${innerHeight}px`;
        context.setTransform(ratio, 0, 0, ratio, 0, 0);
    }

    resize();
    window.addEventListener("resize", resize, { passive: true });
    const started = performance.now();
    let previous = started;

    function frame(now) {
        const elapsed = now - started;
        const delta = Math.min(32, now - previous);
        previous = now;
        context.clearRect(0, 0, innerWidth, innerHeight);

        particles.forEach((particle) => {
            particle.x += particle.vx * delta;
            particle.y += particle.vy * delta;
            particle.rotation += particle.vr;
            context.save();
            context.translate(particle.x * innerWidth, particle.y * innerHeight);
            context.rotate(particle.rotation);
            context.globalAlpha = Math.max(0, 1 - elapsed / 6200);
            context.fillStyle = particle.color;
            context.fillRect(-particle.size / 2, -particle.size / 2, particle.size, particle.size * 1.4);
            context.restore();
        });

        if (elapsed < 6200) requestAnimationFrame(frame);
        else {
            context.clearRect(0, 0, innerWidth, innerHeight);
            window.removeEventListener("resize", resize);
            history.replaceState(null, "", `${location.pathname}#welcome`);
        }
    }

    requestAnimationFrame(frame);
}
