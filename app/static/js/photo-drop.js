"use strict";

(() => {
    const form = document.querySelector("[data-photo-drop-form]");
    if (!form) return;

    const input = form.querySelector("[data-photo-input]");
    const preview = form.querySelector("[data-photo-preview]");
    const button = form.querySelector("[data-photo-submit]");
    const status = form.querySelector("[data-photo-progress]");
    let files = [];
    let imageUrls = [];
    let sharedCount = 0;
    const maxRequestFiles = 6;
    const maxRequestBytes = 30 * 1024 * 1024;

    function clearPreviews() {
        for (const url of imageUrls) URL.revokeObjectURL(url);
        imageUrls = [];
        preview.replaceChildren();
    }

    function message(text, bad = false) {
        status.textContent = text;
        status.style.color = bad ? "#ffb9a8" : "";
    }

    function showFiles() {
        clearPreviews();
        if (files.length === 0) {
            button.disabled = true;
            message("");
            return;
        }
        button.disabled = false;
        button.firstChild.textContent = files.length === 1 ? "Share this moment " : "Share these moments ";
        message(files.length + (files.length === 1 ? " photo selected" : " photos selected"));
        for (const file of files) {
            const url = URL.createObjectURL(file);
            imageUrls.push(url);
            const figure = document.createElement("figure");
            const image = document.createElement("img");
            image.src = url;
            image.alt = "Selected photo preview";
            image.loading = "lazy";
            image.decoding = "async";
            image.addEventListener("error", () => {
                const placeholder = document.createElement("span");
                placeholder.className = "photo-drop-preview-placeholder";
                placeholder.textContent = "Photo selected";
                image.replaceWith(placeholder);
            }, {once: true});
            const label = document.createElement("figcaption");
            label.textContent = file.name.length > 20 ? file.name.slice(0, 17) + "…" : file.name;
            figure.append(image, label);
            preview.appendChild(figure);
        }
    }

    input.addEventListener("change", () => {
        sharedCount = 0;
        files = Array.from(input.files || []);
        showFiles();
    });
    window.addEventListener("pagehide", clearPreviews);

    function decodeWithImage(file) {
        return new Promise((resolve, reject) => {
            const url = URL.createObjectURL(file);
            const image = new Image();
            image.onload = () => {
                URL.revokeObjectURL(url);
                resolve(image);
            };
            image.onerror = () => {
                URL.revokeObjectURL(url);
                reject(new Error("Your phone couldn't convert a selected photo. Please export it as JPG first."));
            };
            image.src = url;
        });
    }

    async function convertPhoto(file) {
        if (file.size > 40 * 1024 * 1024) {
            throw new Error("One selected photo is too large. Please choose a smaller photo.");
        }
        const image = await decodeWithImage(file);
        const maxSize = 2600;
        const scale = Math.min(1, maxSize / Math.max(image.naturalWidth, image.naturalHeight));
        const canvas = document.createElement("canvas");
        canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
        canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
        const context = canvas.getContext("2d");
        if (!context) throw new Error("This browser can't prepare the photo.");
        context.fillStyle = "#faf5ec";
        context.fillRect(0, 0, canvas.width, canvas.height);
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/jpeg", .82));
        canvas.width = 0;
        canvas.height = 0;
        if (!blob || blob.size > 12 * 1024 * 1024) {
            throw new Error("One photo couldn't be prepared. Try a smaller version.");
        }
        return new File([blob], "wedding-moment.jpg", {type: "image/jpeg"});
    }

    function sendPhotos(payload, start, end, total) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open("POST", window.location.pathname);
            xhr.responseType = "json";
            xhr.setRequestHeader("Accept", "application/json");
            xhr.upload.addEventListener("progress", progress => {
                if (progress.lengthComputable) {
                    message(`Uploading photos ${start}–${end} of ${total} · ${Math.round(progress.loaded / progress.total * 100)}%`);
                }
            });
            xhr.addEventListener("load", () => resolve(xhr));
            xhr.addEventListener("error", () => reject(new Error("The connection dropped. Some photos may already be shared; check the gallery before retrying.")));
            xhr.addEventListener("abort", () => reject(new Error("The upload was interrupted. Some photos may already be shared; check the gallery before retrying.")));
            xhr.send(payload);
        });
    }

    form.addEventListener("submit", async event => {
        event.preventDefault();
        if (button.disabled || !files.length) return;
        const total = sharedCount + files.length;
        // Snapshot consent and metadata before locking editable controls.
        const fields = new FormData(form);
        fields.delete("photos");
        const controls = Array.from(form.querySelectorAll("input:not([type=hidden]), select"));
        const disabledStates = controls.map(control => control.disabled);
        controls.forEach(control => { control.disabled = true; });
        button.disabled = true;
        form.setAttribute("aria-busy", "true");
        try {
            while (files.length) {
                const preparedFiles = [];
                let preparedBytes = 0;
                for (const file of files.slice(0, maxRequestFiles)) {
                    message(`Preparing photo ${sharedCount + preparedFiles.length + 1} of ${total}…`);
                    let prepared;
                    try {
                        prepared = await convertPhoto(file);
                    } catch (error) {
                        // Use server decoding for browser-unsupported originals.
                        if (file.size > 12 * 1024 * 1024) {
                            throw new Error("This photo can't be prepared on your phone. Choose a version under 12 MB.");
                        }
                        prepared = file;
                    }
                    if (preparedFiles.length && preparedBytes + prepared.size > maxRequestBytes) break;
                    preparedFiles.push(prepared);
                    preparedBytes += prepared.size;
                }
                const payload = new FormData();
                for (const [key, value] of fields) payload.append(key, value);
                for (const file of preparedFiles) payload.append("photos", file, file.name);
                const response = await sendPhotos(payload, sharedCount + 1,
                    sharedCount + preparedFiles.length, total);
                if (response.status < 200 || response.status >= 300 || !response.response?.success) {
                    throw new Error(response.response?.message ||
                        `We couldn't confirm this upload (HTTP ${response.status}). Check the gallery before retrying.`);
                }
                if (response.response.count !== preparedFiles.length) {
                    throw new Error("We couldn't confirm all photos. Check the gallery before retrying.");
                }
                // Remove only acknowledged files. A later failure leaves the
                // remaining queue available without resending confirmed photos.
                sharedCount += preparedFiles.length;
                files = files.slice(preparedFiles.length);
                for (let i = 0; i < preparedFiles.length; i++) {
                    preview.firstElementChild?.remove();
                    const url = imageUrls.shift();
                    if (url) URL.revokeObjectURL(url);
                }
                message(`${sharedCount} of ${total} photos shared…`);
            }
            input.value = "";
            window.location.assign(window.location.pathname + "/thanks?count=" + sharedCount);
        } catch (error) {
            const progress = sharedCount ? `${sharedCount} photos shared. ${files.length} still to send. ` : "";
            message(progress + (error.message || "Something went wrong. Please try again."), true);
            if (sharedCount) button.firstChild.textContent = "Retry remaining photos ";
        } finally {
            controls.forEach((control, index) => { control.disabled = disabledStates[index]; });
            button.disabled = files.length === 0;
            form.removeAttribute("aria-busy");
        }
    });
})();
