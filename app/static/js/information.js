function mountQaAccordion(root) {
    const accordion = root.querySelector?.("[data-qa-accordion]");
    if (!accordion) return () => {};

    const items = [...accordion.querySelectorAll("details.qa-item")];
    const listeners = [];

    items.forEach((item) => {
        const onToggle = () => {
            if (!item.open) return;

            items.forEach((other) => {
                if (other !== item && other.open) other.open = false;
            });
        };

        item.addEventListener("toggle", onToggle);
        listeners.push(() => item.removeEventListener("toggle", onToggle));
    });

    return () => listeners.forEach((remove) => remove());
}

export function mountInformationTabs(root = document) {
    const cleanups = [mountQaAccordion(root)];
    return () => cleanups.forEach((cleanup) => cleanup());
}
