export function mountCountdown(root = document) {
    const countdown = root.querySelector("[data-countdown]");
    if (!countdown) return () => {};

    const target = new Date(countdown.dataset.target).getTime();
    const fields = {
        days: countdown.querySelector("[data-countdown-days]"),
        hours: countdown.querySelector("[data-countdown-hours]"),
        minutes: countdown.querySelector("[data-countdown-minutes]"),
        seconds: countdown.querySelector("[data-countdown-seconds]"),
    };

    function update() {
        const distance = Math.max(0, target - Date.now());
        fields.days.textContent = String(Math.floor(distance / 86400000)).padStart(2, "0");
        fields.hours.textContent = String(Math.floor(distance / 3600000) % 24).padStart(2, "0");
        fields.minutes.textContent = String(Math.floor(distance / 60000) % 60).padStart(2, "0");
        fields.seconds.textContent = String(Math.floor(distance / 1000) % 60).padStart(2, "0");
    }

    update();
    const intervalId = window.setInterval(update, 1000);
    return () => window.clearInterval(intervalId);
}
