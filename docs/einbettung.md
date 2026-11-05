# Einbettung der Parkkarte in WordPress

Das Web-Frontend (`web_frontend/`) lässt sich per iframe in eine WordPress-Seite einbetten. Mit dem URL-Parameter `?embed=1` blendet die Seite ihren eigenen Header aus (Logo und Menü kommen von WordPress), reduziert den äußeren Rand auf 8 px und meldet ihre Höhe an die einbettende Seite. Ein kleines Skript auf der WordPress-Seite passt die iframe-Höhe daran an, sodass keine zweite Scrollleiste entsteht.

## Einbinden (Block „Individuelles HTML“)

`https://DEINE-HOSTING-DOMAIN/pfad/zum/frontend` an zwei Stellen durch die Adresse ersetzen, unter der `web_frontend/` veröffentlicht ist. Im Skript steht nur die Domain, ohne Pfad und ohne abschließenden Schrägstrich.

```html
<iframe
  id="ieej-parkkarte"
  src="https://DEINE-HOSTING-DOMAIN/pfad/zum/frontend/index.html?embed=1"
  title="Energiesystem im Innovationspark Jüchen"
  style="width: 100%; height: 1400px; border: 0; display: block;"
  loading="lazy"
></iframe>
<script>
  (function () {
    // Nur Nachrichten der eigenen Hosting-Domain annehmen
    var ALLOWED_ORIGIN = "https://DEINE-HOSTING-DOMAIN";
    var frame = document.getElementById("ieej-parkkarte");
    window.addEventListener("message", function (event) {
      if (event.origin !== ALLOWED_ORIGIN) return;
      if (event.source !== frame.contentWindow) return;
      var data = event.data || {};
      if (data.type !== "ieej-height") return;
      var height = Number(data.height);
      if (!isFinite(height) || height < 300 || height > 20000) return;
      frame.style.height = Math.ceil(height) + "px";
    });
  })();
</script>
```

Die Höhe von 1400 px im `style` ist nur der Startwert, bis die erste Nachricht ankommt.

## Verhalten im iframe

- Die Seite meldet ihre Höhe beim Laden und bei jeder Größenänderung (ResizeObserver), z. B. beim Auf- und Zuklappen der Auswahl oder beim Wechsel zum Lageplan. Die Nachricht hat die Form `{ type: "ieej-height", height: <Pixel> }`.
- Die Umbruchpunkte richten sich nach der Breite des iframes (Container Queries), nicht nach der Fensterbreite: ab 1400 px Erzeugung und Verbrauch nebeneinander, 900–1400 px eine Spalte, darunter die aufklappbare Auswahl „Szenario anpassen“.
- Weil der iframe mit dem Inhalt wächst, scrollt die WordPress-Seite. Die Auswahlspalten bleiben im eingebetteten Modus deshalb nicht stehen, sondern scrollen mit.
- Ohne `?embed=1` verhält sich die Seite wie eigenständig aufgerufen (mit Header und festen Auswahlspalten).

## Prüfen

1. Seite mit `?embed=1` direkt öffnen: Der Header fehlt, der Rand ist schmal.
2. In WordPress-Vorschau die Entwicklerwerkzeuge öffnen: Beim Aufklappen eines Bereichs ändert sich die Höhe des iframes, es erscheint keine innere Scrollleiste.
3. Kommt keine Höhe an: `ALLOWED_ORIGIN` muss exakt der Adresse aus `src` entsprechen (Protokoll und Domain, ggf. mit Port).
