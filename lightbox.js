// Foto-Großansicht der Teilprojekte (natives <dialog>, keine Bibliothek).
// Aufruf: openPhotoLightbox(photoId, triggerElement); Fotos und Texte aus assets/photos/photos.json.

const LIGHTBOX_PHOTOS_PATH = "./assets/photos/photos.json";
const LIGHTBOX_CREDIT_PLACEHOLDER = "[Bildnachweis offen";

const lightboxState = {
  photos: null,          // Promise auf den Inhalt von photos.json
  dialog: null,
  items: [],
  index: 0,
  trigger: null,
};

function loadLightboxPhotos() {
  lightboxState.photos ??= fetch(LIGHTBOX_PHOTOS_PATH)
    .then((res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    })
    .then((photos) => {
      const open = Object.entries(photos)
        .filter(([, list]) => list.some((p) => String(p.bildnachweis || "").startsWith(LIGHTBOX_CREDIT_PLACEHOLDER)))
        .map(([id]) => id);
      if (open.length) {
        console.warn(`Bildnachweis noch offen in assets/photos/photos.json für: ${open.join(", ")}`);
      }
      return photos;
    });
  return lightboxState.photos;
}

function buildLightbox() {
  const dialog = document.createElement("dialog");
  dialog.id = "photo-lightbox";
  dialog.className = "lightbox";
  dialog.setAttribute("aria-labelledby", "lb-title");
  dialog.innerHTML = `
    <div class="lb-panel">
      <button type="button" class="lb-close" aria-label="Schließen">×</button>
      <figure class="lb-figure">
        <div class="lb-stage">
          <button type="button" class="lb-nav lb-prev" aria-label="Vorheriges Foto">‹</button>
          <img class="lb-image" alt="" hidden>
          <p class="lb-status" aria-live="polite"></p>
          <button type="button" class="lb-nav lb-next" aria-label="Nächstes Foto">›</button>
        </div>
        <figcaption class="lb-caption">
          <h2 class="lb-title" id="lb-title"></h2>
          <p class="lb-desc"></p>
          <p class="lb-credit"></p>
          <p class="lb-counter" aria-live="polite"></p>
        </figcaption>
      </figure>
    </div>`;
  document.body.appendChild(dialog);

  dialog.querySelector(".lb-close").addEventListener("click", () => dialog.close());
  dialog.querySelector(".lb-prev").addEventListener("click", () => showLightboxItem(lightboxState.index - 1));
  dialog.querySelector(".lb-next").addEventListener("click", () => showLightboxItem(lightboxState.index + 1));
  // Klick auf den Hintergrund: das Ereignis landet direkt am <dialog>, nicht am Inhalt
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
  dialog.addEventListener("keydown", (event) => {
    if (lightboxState.items.length < 2) return;
    if (event.key === "ArrowRight") showLightboxItem(lightboxState.index + 1);
    else if (event.key === "ArrowLeft") showLightboxItem(lightboxState.index - 1);
    else return;
    event.preventDefault();
  });
  // Esc schließt nativ; danach Fokus zurück an das auslösende Element
  dialog.addEventListener("close", () => {
    const img = dialog.querySelector(".lb-image");
    img.removeAttribute("src");
    img.hidden = true;
    lightboxState.trigger?.focus?.();
    lightboxState.trigger = null;
  });

  const img = dialog.querySelector(".lb-image");
  img.addEventListener("load", () => {
    img.hidden = false;
    dialog.querySelector(".lb-status").textContent = "";
  });
  img.addEventListener("error", () => {
    if (!img.getAttribute("src")) return;
    img.hidden = true;
    dialog.querySelector(".lb-status").textContent = "Foto konnte nicht geladen werden.";
  });
  return dialog;
}

function showLightboxItem(index) {
  const { dialog, items } = lightboxState;
  if (!items.length) return;
  lightboxState.index = (index + items.length) % items.length;
  const item = items[lightboxState.index];
  const multiple = items.length > 1;

  const img = dialog.querySelector(".lb-image");
  img.hidden = true;
  dialog.querySelector(".lb-status").textContent = "Foto wird geladen …";
  img.alt = item.alt || item.titel || "";
  img.src = item.src;   // erst jetzt laden

  dialog.querySelector(".lb-title").textContent = item.titel || "";
  dialog.querySelector(".lb-desc").textContent = item.beschreibung || "";
  const credit = dialog.querySelector(".lb-credit");
  credit.textContent = item.bildnachweis ? `Bild: ${item.bildnachweis}` : "";
  credit.hidden = !item.bildnachweis;
  const counter = dialog.querySelector(".lb-counter");
  counter.textContent = `${lightboxState.index + 1} / ${items.length}`;
  counter.hidden = !multiple;
  dialog.querySelectorAll(".lb-nav").forEach((button) => {
    button.hidden = !multiple;
  });
}

// Im eingebetteten iframe wächst die Seite mit dem Inhalt; die Mitte des iframes kann dann
// weit außerhalb des sichtbaren Bereichs liegen. Deshalb dort nahe am Auslöser öffnen.
function anchorLightbox(dialog, trigger) {
  const embedded = document.documentElement.classList.contains("is-embed") && window.parent !== window;
  dialog.classList.toggle("is-anchored", embedded);
  if (!embedded || !trigger?.getBoundingClientRect) return;
  const top = Math.max(8, trigger.getBoundingClientRect().top + window.scrollY - 160);
  dialog.style.setProperty("--lb-top", `${Math.round(top)}px`);
}

async function openPhotoLightbox(photoId, trigger) {
  lightboxState.dialog ??= buildLightbox();
  const { dialog } = lightboxState;
  if (dialog.open) return;

  lightboxState.trigger = trigger || document.activeElement;
  lightboxState.items = [];
  for (const selector of [".lb-title", ".lb-desc", ".lb-credit", ".lb-counter"]) {
    dialog.querySelector(selector).textContent = "";
  }
  dialog.querySelectorAll(".lb-nav, .lb-counter").forEach((el) => {
    el.hidden = true;
  });
  dialog.querySelector(".lb-status").textContent = "Fotos werden geladen …";
  anchorLightbox(dialog, trigger);
  dialog.showModal();

  try {
    const photos = await loadLightboxPhotos();
    lightboxState.items = photos[photoId] || [];
    if (!lightboxState.items.length) {
      dialog.querySelector(".lb-status").textContent = "Für dieses Teilprojekt ist noch kein Foto hinterlegt.";
      return;
    }
    showLightboxItem(0);
  } catch (err) {
    dialog.querySelector(".lb-status").textContent = `Fotos konnten nicht geladen werden (${err.message}).`;
  }
}
