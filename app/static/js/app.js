import { createSlideshow } from "./slideshow.js";
import { mountCountdown } from "./countdown.js";
import { runLoginSparkles } from "./effects.js";
import { mountSchedule } from "./schedule.js";
import { mountFragmentNavigation } from "./tabs.js";
import { mountInformationTabs } from "./information.js";

function mountTabContent(root = document) {
    const cleanups = [mountCountdown(root), mountSchedule(root), mountInformationTabs(root)];
    return () => cleanups.forEach((cleanup) => cleanup());
}

createSlideshow();
const cleanupInitialTab = mountTabContent(document);
mountFragmentNavigation(mountTabContent, cleanupInitialTab);
runLoginSparkles();
