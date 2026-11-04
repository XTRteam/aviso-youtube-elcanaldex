"""
Publica un chiste de videojuegos al azar en Discord, sin bot en el servidor.

Lee los chistes de chistes.txt (uno por línea) y publica uno que no haya salido
todavía. Cuando han salido todos, vuelve a empezar.

Formato de chistes.txt:
  - Un chiste por línea.
  - Si tiene pregunta y respuesta, sepáralas con " | ". La respuesta sale oculta
    (spoiler) para que haya que pulsar en ella:
        ¿Por qué el creeper no tiene amigos? | Porque siempre explota.
  - Las líneas vacías y las que empiezan por # se ignoran.

Variables de entorno:
  DISCORD_WEBHOOK_CHISTES  URL del webhook del canal de Discord
  ARCHIVO_CHISTES          (opcional) por defecto chistes.txt
  ARCHIVO_ESTADO           (opcional) por defecto chistes_usados.json
"""

import hashlib
import json
import os
import random
import sys
import urllib.error
import urllib.request

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_CHISTES", "").strip()
ARCHIVO_CHISTES = os.environ.get("ARCHIVO_CHISTES", "chistes.txt")
ARCHIVO_ESTADO = os.environ.get("ARCHIVO_ESTADO", "chistes_usados.json")
COLORES = [0xF1C40F, 0x2ECC71, 0x3498DB, 0xE67E22, 0x9B59B6, 0x1ABC9C]


def leer_chistes():
    with open(ARCHIVO_CHISTES, encoding="utf-8") as f:
        lineas = [l.strip() for l in f]
    return [l for l in lineas if l and not l.startswith("#")]


def huella(chiste):
    return hashlib.sha1(chiste.lower().encode("utf-8")).hexdigest()[:12]


def cargar_usados():
    if not os.path.exists(ARCHIVO_ESTADO):
        return []
    with open(ARCHIVO_ESTADO, encoding="utf-8") as f:
        return json.load(f)


def guardar_usados(usados):
    with open(ARCHIVO_ESTADO, "w", encoding="utf-8") as f:
        json.dump(usados, f)


def crear_embed(chiste):
    if " | " in chiste:
        pregunta, respuesta = (p.strip() for p in chiste.split(" | ", 1))
        texto = f"{pregunta}\n\n||{respuesta}||"
    else:
        texto = chiste
    return {
        "title": "😂 Chiste gamer",
        "description": texto,
        "color": random.choice(COLORES),
    }


def enviar(cuerpo):
    peticion = urllib.request.Request(
        WEBHOOK_URL,
        data=json.dumps(cuerpo).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "DiscordBot (aviso-chistes, 1.0)",
        },
        method="POST",
    )
    with urllib.request.urlopen(peticion, timeout=30):
        pass


def main():
    if not WEBHOOK_URL:
        sys.exit("Falta DISCORD_WEBHOOK_CHISTES.")

    chistes = leer_chistes()
    if not chistes:
        sys.exit(f"No hay chistes en {ARCHIVO_CHISTES}.")

    usados = set(cargar_usados())
    disponibles = [c for c in chistes if huella(c) not in usados]
    if not disponibles:
        print("Ya han salido todos los chistes: se empieza de nuevo.")
        usados = set()
        disponibles = chistes

    chiste = random.SystemRandom().choice(disponibles)
    try:
        enviar({"embeds": [crear_embed(chiste)], "allowed_mentions": {"parse": []}})
    except urllib.error.HTTPError as e:
        sys.exit(f"Error al publicar en Discord ({e.code}): {e.read().decode()}")

    usados.add(huella(chiste))
    guardar_usados(sorted(usados))
    print(f"Publicado ({len(chistes) - len(disponibles) + 1}/{len(chistes)}): {chiste}")


if __name__ == "__main__":
    main()
