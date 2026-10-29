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
        if (files.length > 6) {
            button.disabled = true;
            message("Please choose up to 6 photos at once.", true);
            return;
        }
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
            const label = document.createElement("figcaption");
            label.textContent = file.name.length > 20 ? file.name.slice(0, 17) + "…" : file.name;
            figure.append(image, label);
            preview.appendChild(figure);
        }
    }

    input.addEventListener("change", () => {
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

    form.addEventListener("submit", async event => {
        // Native submission remains available when JavaScript is disabled.
        event.preventDefault();
        if (button.disabled || !files.length || files.length > 6) return;
        button.disabled = true;
        form.setAttribute("aria-busy", "true");
        message("Preparing your photos…");
        try {
            const payload = new FormData(form);
            payload.delete("photos");
            for (const file of files) {
                const prepared = await convertPhoto(file);
                payload.append("photos", prepared, prepared.name);
            }
            message("Sending your moments…");
            const response = await new Promise((resolve, reject) => {
                const xhr = new XMLHttpRequest();
                xhr.open("POST", window.location.pathname);
                xhr.responseType = "json";
                xhr.setRequestHeader("Accept", "application/json");
                xhr.upload.addEventListener("progress", progress => {
                    if (progress.lengthComputable) {
                        message("Uploading · " + Math.round(progress.loaded / progress.total * 100) + "%");
                    }
                });
                xhr.addEventListener("load", () => resolve(xhr));
                xhr.addEventListener("error", () => reject(new Error("The connection dropped. Please try again.")));
                xhr.addEventListener("abort", () => reject(new Error("The upload was interrupted.")));
                xhr.send(payload);
            });
            if (response.status < 200 || response.status >= 300 || !response.response?.success) {
                throw new Error(response.response?.message || "We couldn't save your photos. Please try again.");
            }
            const count = Number(response.response.count) || files.length;
            window.location.assign(window.location.pathname + "/thanks?count=" + count);
        } catch (error) {
            message(error.message || "Something went wrong. Please try again.", true);
            button.disabled = false;
            form.removeAttribute("aria-busy");
        }
    });
})();
