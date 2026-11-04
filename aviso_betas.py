"""
Aviso de betas y accesos anticipados en Discord, sin bot en el servidor.

Consulta la API pública de GamerPower (sorteos de tipo "beta") y publica
las nuevas en un canal de Discord mediante un webhook.

Variables de entorno:
  DISCORD_WEBHOOK_BETAS  URL del webhook del canal de Discord
  MENCION                (opcional) texto encima del aviso, p. ej. "@everyone"
                         o "<@&ID_DEL_ROL>"
  PLATAFORMAS            (opcional) tiendas separadas por comas, p. ej.
                         "steam,epic-games-store". Vacío = todas.
  ARCHIVO_ESTADO         (opcional) archivo con las betas ya avisadas
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_BETAS", "").strip()
MENCION = (os.environ.get("MENCION") or "").strip()
PLATAFORMAS = (os.environ.get("PLATAFORMAS") or "").strip()
ARCHIVO_ESTADO = os.environ.get("ARCHIVO_ESTADO", "betas_vistas.json")
MAX_GUARDADOS = 300
COLOR = 0x5865F2


def leer_betas():
    """Devuelve las betas activas de GamerPower (lista vacía si no hay)."""
    if PLATAFORMAS:
        # El endpoint de filtro admite varias tiendas separadas por puntos
        tiendas = ".".join(p.strip() for p in PLATAFORMAS.split(",") if p.strip())
        url = "https://www.gamerpower.com/api/filter?" + urllib.parse.urlencode(
            {"platform": tiendas, "type": "beta"}
        )
    else:
        url = "https://www.gamerpower.com/api/giveaways?" + urllib.parse.urlencode(
            {"type": "beta", "sort-by": "date"}
        )

    peticion = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(peticion, timeout=30) as respuesta:
            datos = json.loads(respuesta.read())
    except urllib.error.HTTPError as e:
        # GamerPower puede responder con error cuando no hay sorteos activos
        if e.code == 404:
            return []
        raise
    # Cuando no hay resultados devuelve un objeto en vez de una lista
    return datos if isinstance(datos, list) else []


def cargar_estado():
    if not os.path.exists(ARCHIVO_ESTADO):
        return None
    with open(ARCHIVO_ESTADO, encoding="utf-8") as f:
        return json.load(f)


def guardar_estado(ids):
    with open(ARCHIVO_ESTADO, "w", encoding="utf-8") as f:
        json.dump(ids[:MAX_GUARDADOS], f, indent=2)


def recortar(texto, limite):
    texto = (texto or "").strip()
    return texto if len(texto) <= limite else texto[: limite - 1].rstrip() + "…"


def crear_embed(beta):
    campos = []
    if beta.get("platforms"):
        campos.append({"name": "🕹️ Plataformas", "value": recortar(beta["platforms"], 1000), "inline": True})
    fin = beta.get("end_date")
    campos.append({
        "name": "⏳ Disponible hasta",
        "value": fin if fin and fin != "N/A" else "Hasta agotar existencias",
        "inline": True,
    })
    if beta.get("instructions"):
        campos.append({"name": "📋 Cómo conseguirla", "value": recortar(beta["instructions"], 1000)})

    embed = {
        "title": recortar("🧪 " + beta.get("title", "Nueva beta"), 256),
        "url": beta.get("open_giveaway_url") or beta.get("gamerpower_url"),
        "description": recortar(beta.get("description"), 1500),
        "color": COLOR,
        "fields": campos,
        "footer": {"text": "Datos de GamerPower"},
    }
    if beta.get("image"):
        embed["image"] = {"url": beta["image"]}
    return embed


def avisar(beta):
    cuerpo = {
        "content": MENCION or None,
        "embeds": [crear_embed(beta)],
        "allowed_mentions": {"parse": ["everyone", "roles"]},
    }
    peticion = urllib.request.Request(
        WEBHOOK_URL,
        data=json.dumps(cuerpo).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "DiscordBot (aviso-betas, 1.0)",
        },
        method="POST",
    )
    with urllib.request.urlopen(peticion, timeout=30):
        pass


def main():
    if not WEBHOOK_URL:
        sys.exit("Falta DISCORD_WEBHOOK_BETAS.")

    betas = leer_betas()
    vistas = cargar_estado()

    # Primera ejecución: guarda las betas actuales sin avisar,
    # para no llenar el canal de golpe.
    if vistas is None:
        guardar_estado([b["id"] for b in betas if "id" in b])
        print(f"Primera ejecución: {len(betas)} betas guardadas, sin avisos.")
        return

    nuevas = [b for b in betas if b.get("id") not in vistas]
    if not nuevas:
        print("No hay betas nuevas.")
        return

    # Avisa de la más antigua a la más reciente
    for beta in reversed(nuevas):
        try:
            avisar(beta)
        except urllib.error.HTTPError as e:
            guardar_estado(vistas)
            sys.exit(f"Error al avisar en Discord ({e.code}): {e.read().decode()}")
        vistas.insert(0, beta["id"])
        guardar_estado(vistas)
        print(f"Avisada: {beta.get('title')}")
        time.sleep(1)  # para no saturar el webhook


if __name__ == "__main__":
    main()
