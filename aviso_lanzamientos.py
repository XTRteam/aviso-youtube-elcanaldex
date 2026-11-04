"""
Aviso diario de lanzamientos de juegos en Discord, sin bot en el servidor.

Consulta en IGDB (la base de datos de juegos de Twitch) los juegos que salen
hoy, se queda con los más esperados y los publica en un canal de Discord
mediante un webhook, indicando claramente en qué plataformas salen HOY.

Variables de entorno:
  TWITCH_CLIENT_ID              Client ID de tu aplicación de dev.twitch.tv
  TWITCH_CLIENT_SECRET          Client Secret de esa aplicación
  DISCORD_WEBHOOK_LANZAMIENTOS  URL del webhook del canal de Discord
  MENCION                       (opcional) texto encima del resumen, p. ej. "<@&ID_DEL_ROL>"
  MIN_POPULARIDAD               (opcional) nº mínimo de usuarios que esperaban el juego
                                para avisar (por defecto 3). Pon 0 para avisar de todos.
  MAX_JUEGOS                    (opcional) máximo de juegos por día (por defecto 10)
  ARCHIVO_ESTADO                (opcional) archivo con los juegos ya avisados
"""

import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

CLIENT_ID = os.environ.get("TWITCH_CLIENT_ID", "").strip()
CLIENT_SECRET = os.environ.get("TWITCH_CLIENT_SECRET", "").strip()
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_LANZAMIENTOS", "").strip()
MENCION = (os.environ.get("MENCION") or "").strip()
MIN_POPULARIDAD = int(os.environ.get("MIN_POPULARIDAD") or 3)
MAX_JUEGOS = int(os.environ.get("MAX_JUEGOS") or 10)
ARCHIVO_ESTADO = os.environ.get("ARCHIVO_ESTADO", "lanzamientos_vistos.json")
MAX_GUARDADOS = 500

try:
    from zoneinfo import ZoneInfo
    ZONA = ZoneInfo("Europe/Madrid")
except Exception:  # si el sistema no tiene zonas horarias
    ZONA = datetime.timezone(datetime.timedelta(hours=1))

# Cómo se muestra cada familia de plataformas: (emoji, nombre)
FAMILIAS = {
    "pc": ("🖥️", "PC"),
    "playstation": ("🎮", "PlayStation"),
    "xbox": ("🟩", "Xbox"),
    "nintendo": ("🔴", "Nintendo"),
    "android": ("📱", "Android"),
    "ios": ("📱", "iOS"),
    "mac": ("🍎", "Mac"),
    "linux": ("🐧", "Linux"),
}
ORDEN = ["pc", "playstation", "xbox", "nintendo", "android", "ios", "mac", "linux"]

NOMBRES_CORTOS = {
    "PlayStation 5": "PS5",
    "PlayStation 4": "PS4",
    "Xbox Series X|S": "Series X|S",
    "Xbox One": "One",
    "Nintendo Switch": "Switch",
    "Nintendo Switch 2": "Switch 2",
}


def familia_de(nombre):
    n = nombre.lower()
    if "windows" in n or n.startswith("pc"):
        return "pc"
    if "playstation" in n:
        return "playstation"
    if "xbox" in n:
        return "xbox"
    if "nintendo" in n or "switch" in n:
        return "nintendo"
    if "android" in n:
        return "android"
    if n == "ios":
        return "ios"
    if "mac" in n:
        return "mac"
    if "linux" in n:
        return "linux"
    return None


def texto_plataformas(nombres):
    grupos = {}
    for nombre in nombres:
        familia = familia_de(nombre)
        if not familia:
            continue
        lista = grupos.setdefault(familia, [])
        corto = NOMBRES_CORTOS.get(nombre)
        if corto and corto not in lista:
            lista.append(corto)
    partes = []
    for familia in ORDEN:
        if familia in grupos:
            emoji, nombre = FAMILIAS[familia]
            detalle = grupos[familia]
            partes.append(f"{emoji} **{nombre}**" + (f" ({', '.join(detalle)})" if detalle else ""))
    return "  ·  ".join(partes) or "❔ Sin confirmar"


def peticion_json(url, datos=None, cabeceras=None):
    peticion = urllib.request.Request(
        url,
        data=datos,
        headers={"User-Agent": "aviso-lanzamientos/1.0", **(cabeceras or {})},
        method="POST" if datos is not None else "GET",
    )
    with urllib.request.urlopen(peticion, timeout=30) as respuesta:
        return json.loads(respuesta.read())


def obtener_token():
    params = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "client_credentials",
    })
    datos = peticion_json("https://id.twitch.tv/oauth2/token?" + params, datos=b"")
    return datos["access_token"]


def leer_lanzamientos(inicio, fin):
    """Juegos con alguna fecha de lanzamiento entre inicio y fin (timestamps)."""
    token = obtener_token()
    consulta = (
        "fields name,slug,url,hypes,genres.name,cover.image_id,version_parent,"
        "release_dates.date,release_dates.platform.name;"
        f"where release_dates.date >= {inicio} & release_dates.date < {fin};"
        "sort hypes desc;"
        "limit 100;"
    )
    juegos = peticion_json(
        "https://api.igdb.com/v4/games",
        datos=consulta.encode("utf-8"),
        cabeceras={
            "Client-ID": CLIENT_ID,
            "Authorization": f"Bearer {token}",
            "Content-Type": "text/plain",
        },
    )

    resultado = []
    for juego in juegos:
        if juego.get("version_parent"):  # ediciones especiales del mismo juego
            continue
        if (juego.get("hypes") or 0) < MIN_POPULARIDAD:
            continue
        # Solo las plataformas en las que sale HOY
        hoy = [
            (r.get("platform") or {}).get("name", "")
            for r in juego.get("release_dates") or []
            if inicio <= (r.get("date") or 0) < fin
        ]
        if not hoy:
            continue
        juego["plataformas_hoy"] = hoy
        resultado.append(juego)
    resultado.sort(key=lambda j: j.get("hypes") or 0, reverse=True)
    return resultado


def cargar_estado():
    if not os.path.exists(ARCHIVO_ESTADO):
        return []
    with open(ARCHIVO_ESTADO, encoding="utf-8") as f:
        return json.load(f)


def guardar_estado(ids):
    with open(ARCHIVO_ESTADO, "w", encoding="utf-8") as f:
        json.dump(ids[:MAX_GUARDADOS], f, indent=2)


def formato_fecha(fecha):
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    return f"{fecha.day} de {meses[fecha.month - 1]} de {fecha.year}"


def crear_embed(juego, fecha):
    generos = ", ".join(g["name"] for g in juego.get("genres") or []) or "—"
    embed = {
        "title": "🆕 " + juego.get("name", "Juego nuevo"),
        "url": juego.get("url") or f"https://www.igdb.com/games/{juego.get('slug', '')}",
        "description": "**Plataformas:**\n" + texto_plataformas(juego["plataformas_hoy"]),
        "color": 0x2ECC71,
        "fields": [
            {"name": "🏷️ Género", "value": generos[:1000], "inline": True},
            {"name": "📅 Lanzamiento", "value": formato_fecha(fecha), "inline": True},
        ],
        "footer": {"text": "Datos de IGDB.com"},
    }
    imagen = (juego.get("cover") or {}).get("image_id")
    if imagen:
        embed["thumbnail"] = {"url": f"https://images.igdb.com/igdb/image/upload/t_cover_big/{imagen}.jpg"}
    return embed


def enviar(cuerpo):
    peticion = urllib.request.Request(
        WEBHOOK_URL,
        data=json.dumps(cuerpo).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "DiscordBot (aviso-lanzamientos, 1.0)",
        },
        method="POST",
    )
    with urllib.request.urlopen(peticion, timeout=30):
        pass


def main():
    if not CLIENT_ID or not CLIENT_SECRET or not WEBHOOK_URL:
        sys.exit("Faltan TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET o DISCORD_WEBHOOK_LANZAMIENTOS.")

    ahora = datetime.datetime.now(ZONA)
    hoy = ahora.date()
    inicio_dt = datetime.datetime.combine(hoy, datetime.time.min, tzinfo=ZONA)
    inicio = int(inicio_dt.timestamp())
    fin = int((inicio_dt + datetime.timedelta(days=1)).timestamp())

    vistos = cargar_estado()
    nuevos = [j for j in leer_lanzamientos(inicio, fin) if j.get("id") not in vistos][:MAX_JUEGOS]

    if not nuevos:
        print(f"No hay lanzamientos destacados nuevos para {hoy}.")
        return

    cabecera = f"🎮 **Lanzamientos de hoy, {formato_fecha(hoy)}**"
    if MENCION:
        cabecera = f"{MENCION}\n{cabecera}"

    # Discord admite hasta 10 tarjetas por mensaje
    for i in range(0, len(nuevos), 10):
        grupo = nuevos[i:i + 10]
        cuerpo = {
            "content": cabecera if i == 0 else None,
            "embeds": [crear_embed(j, hoy) for j in grupo],
            "allowed_mentions": {"parse": ["everyone", "roles"]},
        }
        try:
            enviar(cuerpo)
        except urllib.error.HTTPError as e:
            guardar_estado(vistos)
            sys.exit(f"Error al avisar en Discord ({e.code}): {e.read().decode()}")
        vistos = [j["id"] for j in grupo] + vistos
        guardar_estado(vistos)
        time.sleep(1)

    print(f"Avisados {len(nuevos)} lanzamientos: " + ", ".join(j["name"] for j in nuevos))


if __name__ == "__main__":
    main()
