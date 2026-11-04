"""
Cuenta atrás diaria en Discord (sin bot en el servidor).

Cada vez que se ejecuta, publica cuántos días faltan para una fecha y menciona
a un rol. El día del lanzamiento publica un mensaje especial y, a partir de
ahí, deja de publicar.

Variables de entorno:
  DISCORD_WEBHOOK_CUENTA_ATRAS  URL del webhook del canal de Discord
  FECHA_OBJETIVO                fecha en formato AAAA-MM-DD (p. ej. 2026-11-19)
  NOMBRE                        nombre del juego o evento (p. ej. "GTA 6")
  MENCION                       (opcional) mención del rol, p. ej. "<@&123456789>"
  IMAGEN                        (opcional) URL de una imagen para el mensaje
"""

import datetime
import json
import os
import sys
import urllib.error
import urllib.request

try:
    from zoneinfo import ZoneInfo
    ZONA = ZoneInfo("Europe/Madrid")
except Exception:
    ZONA = datetime.timezone(datetime.timedelta(hours=1))

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_CUENTA_ATRAS", "").strip()
FECHA = (os.environ.get("FECHA_OBJETIVO") or "").strip()
NOMBRE = (os.environ.get("NOMBRE") or "el lanzamiento").strip()
MENCION = (os.environ.get("MENCION") or "").strip()
IMAGEN = (os.environ.get("IMAGEN") or "").strip()

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def fecha_bonita(f):
    return f"{f.day} de {MESES[f.month - 1]} de {f.year}"


def crear_mensaje(dias, objetivo):
    if dias > 1:
        titulo = f"⏳ Faltan {dias} días para {NOMBRE}"
        texto = f"Sale el **{fecha_bonita(objetivo)}**. ¡Cada vez queda menos!"
        color = 0xE91E63
    elif dias == 1:
        titulo = f"🔥 ¡MAÑANA sale {NOMBRE}!"
        texto = "Esta medianoche empieza la cuenta final. ¿Quién va a estar despierto? 🌙"
        color = 0xFF9800
    else:  # dias == 0
        titulo = f"🎉 ¡HOY sale {NOMBRE}!"
        texto = "Ya está aquí. ¡A disfrutarlo! Contadnos qué os parece en el chat 🎮"
        color = 0x4CAF50

    embed = {"title": titulo, "description": texto, "color": color}
    if IMAGEN:
        embed["image"] = {"url": IMAGEN}
    return {
        "content": MENCION or None,
        "embeds": [embed],
        "allowed_mentions": {"parse": ["roles", "everyone"]},
    }


def enviar(cuerpo):
    peticion = urllib.request.Request(
        WEBHOOK_URL,
        data=json.dumps(cuerpo).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "DiscordBot (cuenta-atras, 1.0)",
        },
        method="POST",
    )
    with urllib.request.urlopen(peticion, timeout=30):
        pass


def main():
    if not WEBHOOK_URL or not FECHA:
        sys.exit("Faltan DISCORD_WEBHOOK_CUENTA_ATRAS o FECHA_OBJETIVO.")

    objetivo = datetime.date.fromisoformat(FECHA)
    hoy = datetime.datetime.now(ZONA).date()
    dias = (objetivo - hoy).days

    if dias < 0:
        print(f"{NOMBRE} ya salió el {objetivo}. No se publica nada.")
        return

    try:
        enviar(crear_mensaje(dias, objetivo))
    except urllib.error.HTTPError as e:
        sys.exit(f"Error al publicar en Discord ({e.code}): {e.read().decode()}")
    print(f"Publicado: faltan {dias} días para {NOMBRE}.")


if __name__ == "__main__":
    main()
