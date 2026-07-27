#!/usr/bin/env python3
"""
Lesehilfe für Raspberry Pi 3B + Raspberry Pi Kamera 3
- Startet den Kamerafeed direkt auf dem HDMI-Ausgang (kein Desktop nötig)
- 4 Taster: Zoom rein, Zoom raus, heller/mehr Kontrast, dunkler/weniger Kontrast
- Läuft dauerhaft als systemd-Dienst, startet sich bei Fehlern selbst neu
"""

import logging
import time

from gpiozero import Button
from picamera2 import Picamera2, Preview

# ---------------------------------------------------------------------------
# Konfiguration – hier bei Bedarf anpassen
# ---------------------------------------------------------------------------

# GPIO-Pins der vier Taster (BCM-Nummerierung)
PIN_ZOOM_IN = 17
PIN_ZOOM_OUT = 27
PIN_HELLER = 22
PIN_DUNKLER = 23

# Auflösung des angeschlossenen Displays (Dell 2001fp, natives Querformat 4:3,
# physisch um 90° gedreht montiert -> Kamera ist ebenfalls physisch gedreht,
# daher ist im Bild/Code KEINE Rotation nötig)
DISPLAY_WIDTH = 1600
DISPLAY_HEIGHT = 1200

# Sensor-/Bildauflösung, die von der Kamera aufgenommen wird
CAMERA_WIDTH = 1600
CAMERA_HEIGHT = 1200

# Feste Fokusdistanz (manueller Fokus, da der Abstand Kamera–Zeitung konstant ist)
# LensPosition in Dioptrien = 1 / Abstand_in_Metern.
# Kalibriert für 20 cm Abstand Kamera->Zeitung. Bei anderem Abstand die 0.20 anpassen.
FESTER_FOKUS_DIOPTRIEN = 1 / 0.20

# Zoom-Grenzen und Schrittweite
ZOOM_MIN = 0.15   # kleinster Ausschnitt = stärkster Zoom
ZOOM_MAX = 1.0    # kompletter Sensorbereich = kein Zoom
ZOOM_SCHRITT = 0.05

# Helligkeits-/Kontrast-Grenzen und Schrittweite
HELLIGKEIT_MIN, HELLIGKEIT_MAX = -1.0, 1.0
KONTRAST_MIN, KONTRAST_MAX = 0.0, 2.0
WERT_SCHRITT = 0.05

# Taste gedrückt halten = wiederholtes Auslösen (Komfortfunktion)
HOLD_WIEDERHOLRATE = 0.15  # Sekunden zwischen Wiederholungen beim Gedrückthalten

# ---------------------------------------------------------------------------
# Logging (hilfreich, falls über journalctl Fehler analysiert werden müssen)
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger("lesehilfe")

# ---------------------------------------------------------------------------
# Zustand
# ---------------------------------------------------------------------------
zoom_level = 1.0
helligkeit = 0.0
kontrast = 1.0


def kamera_starten() -> Picamera2:
    """Initialisiert die Kamera und startet die Vorschau direkt über DRM/HDMI."""
    picam2 = Picamera2()

    # "raw" erzwingt den vollen Sensor-Auslesebereich (kein Binning), damit beim
    # Zoomen (ScalerCrop) die volle Detailschärfe des Sensors zur Verfügung steht.
    # "main" bleibt bei der kleineren Zielauflösung für Anzeige/Performance/Strom.
    sensor_modes = picam2.sensor_modes
    volle_sensor_groesse = max(sensor_modes, key=lambda m: m["size"][0] * m["size"][1])["size"]

    config = picam2.create_preview_configuration(
        main={"size": (CAMERA_WIDTH, CAMERA_HEIGHT)},
        raw={"size": volle_sensor_groesse},
    )
    picam2.configure(config)

    # DRM-Preview: zeichnet direkt auf den Bildschirm, ganz ohne Desktop/X11/Wayland
    picam2.start_preview(
        Preview.DRM, x=0, y=0, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT
    )

    picam2.start()

    # Fokus fest einstellen, damit die Kamera nicht ständig nachfokussiert
    picam2.set_controls({"AfMode": 0, "LensPosition": FESTER_FOKUS_DIOPTRIEN})

    return picam2


def update_kamera(picam2: Picamera2) -> None:
    """Sendet aktuelle Helligkeit, Kontrast und Zoom-Ausschnitt an die Kamera."""
    picam2.set_controls({"Brightness": helligkeit, "Contrast": kontrast})

    sensor_box = picam2.camera_properties["PixelArrayActiveAreas"][0]
    # Je nach picamera2-Version ist das entweder ein Rectangle-Objekt
    # (mit .width/.height) oder ein einfaches Tupel (x, y, width, height).
    if hasattr(sensor_box, "width"):
        max_w = sensor_box.width
        max_h = sensor_box.height
    else:
        max_w = sensor_box[2]
        max_h = sensor_box[3]

    neu_w = int(max_w * zoom_level)
    neu_h = int(max_h * zoom_level)
    x = int((max_w - neu_w) / 2)
    y = int((max_h - neu_h) / 2)

    picam2.set_controls({"ScalerCrop": (x, y, neu_w, neu_h)})


def zoom_in(picam2: Picamera2) -> None:
    global zoom_level
    zoom_level = max(ZOOM_MIN, zoom_level - ZOOM_SCHRITT)
    update_kamera(picam2)


def zoom_out(picam2: Picamera2) -> None:
    global zoom_level
    zoom_level = min(ZOOM_MAX, zoom_level + ZOOM_SCHRITT)
    update_kamera(picam2)


def werte_erhoehen(picam2: Picamera2) -> None:
    global helligkeit, kontrast
    helligkeit = min(HELLIGKEIT_MAX, helligkeit + WERT_SCHRITT)
    kontrast = min(KONTRAST_MAX, kontrast + WERT_SCHRITT)
    update_kamera(picam2)


def werte_verringern(picam2: Picamera2) -> None:
    global helligkeit, kontrast
    helligkeit = max(HELLIGKEIT_MIN, helligkeit - WERT_SCHRITT)
    kontrast = max(KONTRAST_MIN, kontrast - WERT_SCHRITT)
    update_kamera(picam2)


def taster_einrichten(picam2: Picamera2) -> None:
    """Verbindet die vier Taster mit den Funktionen. when_held sorgt dafür,
    dass Gedrückthalten wiederholt auslöst statt nur einmal pro Druck."""
    btn_zoom_in = Button(PIN_ZOOM_IN, hold_repeat=True, hold_time=HOLD_WIEDERHOLRATE)
    btn_zoom_out = Button(PIN_ZOOM_OUT, hold_repeat=True, hold_time=HOLD_WIEDERHOLRATE)
    btn_heller = Button(PIN_HELLER, hold_repeat=True, hold_time=HOLD_WIEDERHOLRATE)
    btn_dunkler = Button(PIN_DUNKLER, hold_repeat=True, hold_time=HOLD_WIEDERHOLRATE)

    btn_zoom_in.when_pressed = lambda: zoom_in(picam2)
    btn_zoom_in.when_held = lambda: zoom_in(picam2)

    btn_zoom_out.when_pressed = lambda: zoom_out(picam2)
    btn_zoom_out.when_held = lambda: zoom_out(picam2)

    btn_heller.when_pressed = lambda: werte_erhoehen(picam2)
    btn_heller.when_held = lambda: werte_erhoehen(picam2)

    btn_dunkler.when_pressed = lambda: werte_verringern(picam2)
    btn_dunkler.when_held = lambda: werte_verringern(picam2)

    # Referenzen zurückgeben, damit sie nicht vom Garbage Collector entfernt werden
    return btn_zoom_in, btn_zoom_out, btn_heller, btn_dunkler


def main() -> None:
    log.info("Starte Lesehilfe...")
    picam2 = kamera_starten()
    update_kamera(picam2)  # Startwerte einmal anwenden

    tasten = taster_einrichten(picam2)  # noqa: F841 (Referenzen halten)
    log.info("Lesehilfe läuft. Warte auf Tastendrücke...")

    while True:
        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log.exception("Unerwarteter Fehler - Dienst wird von systemd neu gestartet.")
        raise
