"""
Aviso de vídeos nuevos de YouTube en Discord, sin bot en el servidor.

Lee el feed RSS público del canal de YouTube y, si hay vídeos nuevos,
los publica en un canal de Discord mediante un webhook.

Variables de entorno:
  YOUTUBE_CHANNEL_ID   ID del canal de YouTube (empieza por "UC...")
  DISCORD_WEBHOOK_URL  URL del webhook del canal de Discord
  MENSAJE              (opcional) plantilla del aviso. Admite {titulo} y {enlace}
  ARCHIVO_ESTADO       (opcional) archivo donde se guardan los vídeos ya avisados
"""

import json
import os
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

CHANNEL_ID = os.environ.get("YOUTUBE_CHANNEL_ID", "").strip()
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
MENSAJE = (os.environ.get("MENSAJE") or "").strip() or (
    "📢 **¡Nuevo vídeo en el canal!**\n**{titulo}**\n{enlace}"
)
ARCHIVO_ESTADO = os.environ.get("ARCHIVO_ESTADO", "videos_vistos.json")
MAX_GUARDADOS = 50

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}


def leer_feed():
    """Devuelve los vídeos del feed, del más nuevo al más antiguo."""
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
    peticion = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(peticion, timeout=30) as respuesta:
        raiz = ET.fromstring(respuesta.read())

    videos = []
    for entrada in raiz.findall("atom:entry", NS):
        video_id = entrada.findtext("yt:videoId", namespaces=NS)
        titulo = entrada.findtext("atom:title", default="", namespaces=NS)
        enlace = entrada.find("atom:link", NS)
        if not video_id:
            continue
        videos.append({
            "id": video_id,
            "titulo": titulo,
            "enlace": enlace.get("href") if enlace is not None
            else f"https://www.youtube.com/watch?v={video_id}",
        })
    return videos


def cargar_estado():
    if not os.path.exists(ARCHIVO_ESTADO):
        return None
    with open(ARCHIVO_ESTADO, encoding="utf-8") as f:
        return json.load(f)


def guardar_estado(ids):
    with open(ARCHIVO_ESTADO, "w", encoding="utf-8") as f:
        json.dump(ids[:MAX_GUARDADOS], f, indent=2)


def avisar(video):
    contenido = MENSAJE.replace("{titulo}", video["titulo"]).replace(
        "{enlace}", video["enlace"]
    )
    datos = json.dumps({
        "content": contenido,
        # Permite que @everyone, @here o menciones de rol funcionen en el mensaje
        "allowed_mentions": {"parse": ["everyone", "roles"]},
    }).encode("utf-8")
    peticion = urllib.request.Request(
        WEBHOOK_URL,
        data=datos,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "DiscordBot (aviso-youtube, 1.0)",
        },
        method="POST",
    )
    with urllib.request.urlopen(peticion, timeout=30):
        pass


def main():
    if not CHANNEL_ID or not WEBHOOK_URL:
        sys.exit("Faltan YOUTUBE_CHANNEL_ID o DISCORD_WEBHOOK_URL.")

    videos = leer_feed()
    vistos = cargar_estado()

    # Primera ejecución: guarda los vídeos actuales sin avisar,
    # para no publicar de golpe todos los vídeos antiguos.
    if vistos is None:
        guardar_estado([v["id"] for v in videos])
        print(f"Primera ejecución: {len(videos)} vídeos guardados, sin avisos.")
        return

    nuevos = [v for v in videos if v["id"] not in vistos]
    if not nuevos:
        print("No hay vídeos nuevos.")
        return

    # Avisa en orden cronológico (del más antiguo al más nuevo)
    for video in reversed(nuevos):
        try:
            avisar(video)
        except urllib.error.HTTPError as e:
            guardar_estado(vistos)
            sys.exit(f"Error al avisar en Discord ({e.code}): {e.read().decode()}")
        vistos.insert(0, video["id"])
        guardar_estado(vistos)
        print(f"Avisado: {video['titulo']}")


if __name__ == "__main__":
    main()
