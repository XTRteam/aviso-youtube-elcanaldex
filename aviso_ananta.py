"""
Aviso de novedades de Ananta en Discord, sin bot en el servidor.

Lee los canales RSS de webs de videojuegos y publica las noticias nuevas
en un canal de Discord mediante un webhook.

Variables de entorno:
  DISCORD_WEBHOOK_NOTICIAS  URL del webhook del canal de Discord
  FUENTES                   (opcional) lista de fuentes, una por línea, con el
                            formato "Nombre | URL del RSS". Si no se pone, se
                            usan las fuentes por defecto de abajo.
  PALABRAS_CLAVE            (opcional) palabras separadas por comas. Si se pone,
                            solo se avisa de noticias cuyo título contenga alguna
                            (p. ej. "GTA 6, Once Human, PS5, Nintendo").
  MAX_NOTICIAS              (opcional) máximo de noticias por ejecución (por defecto 5)
  MENCION                   (opcional) texto encima del aviso, p. ej. "<@&ID_DEL_ROL>"
  ARCHIVO_ESTADO            (opcional) archivo con las noticias ya avisadas
"""

import email.utils
import html
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

FUENTES_POR_DEFECTO = """
3DJuegos | https://www.3djuegos.com/feedburner.xml
Vandal | https://vandal.elespanol.com/xml.cgi
Eurogamer España | https://www.eurogamer.es/feed
"""

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_NOTICIAS", "").strip()
FUENTES = (os.environ.get("FUENTES") or "").strip() or FUENTES_POR_DEFECTO
# Fuentes adicionales que se suman a las anteriores (mismo formato)
FUENTES += "\n" + (os.environ.get("FUENTES_EXTRA") or "")
PALABRAS = [p.strip() for p in (os.environ.get("PALABRAS_CLAVE") or "").split(",") if p.strip()]
MAX_NOTICIAS = int(os.environ.get("MAX_NOTICIAS") or 5)
MENCION = (os.environ.get("MENCION") or "").strip()
ARCHIVO_ESTADO = os.environ.get("ARCHIVO_ESTADO", "noticias_vistas.json")
# Si es mayor que 0, publica ya las N novedades más recientes aunque se hayan visto antes
FORZAR = int(os.environ.get("FORZAR") or 0)
# Imagen que se usa cuando la noticia no trae foto ni se encuentra en su página
IMAGEN_POR_DEFECTO = (os.environ.get("IMAGEN_POR_DEFECTO") or "").strip()
MAX_GUARDADAS = 800
COLORES = [0xE74C3C, 0x3498DB, 0x9B59B6, 0x1ABC9C, 0xE67E22, 0x2ECC71]

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "media": "http://search.yahoo.com/mrss/",
    "content": "http://purl.org/rss/1.0/modules/content/",
}


def leer_fuentes():
    fuentes = []
    for linea in FUENTES.splitlines():
        if "|" not in linea:
            continue
        nombre, url = (x.strip() for x in linea.split("|", 1))
        if nombre and url:
            fuentes.append((nombre, url))
    return fuentes


def sin_html(texto):
    texto = re.sub(r"<[^>]+>", " ", texto or "")
    return re.sub(r"\s+", " ", html.unescape(texto)).strip()


def primera_imagen(*textos):
    for t in textos:
        m = re.search(r'<img[^>]+src="([^"]+)"', t or "")
        if m:
            return html.unescape(m.group(1))
    return None


def imagen_de_pagina(url):
    """Busca la foto de portada (og:image / twitter:image) de la página de la noticia."""
    if not url or "news.google." in url:
        return None  # los enlaces de Google Noticias no llevan a la foto real
    try:
        peticion = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (aviso-noticias)"})
        with urllib.request.urlopen(peticion, timeout=15) as respuesta:
            pagina = respuesta.read(400_000).decode("utf-8", errors="ignore")
    except Exception:
        return None
    patrones = [
        r'<meta[^>]+(?:property|name)=["\'](?:og:image|og:image:url|twitter:image)["\'][^>]*content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\'](?:og:image|og:image:url|twitter:image)["\']',
    ]
    for patron in patrones:
        m = re.search(patron, pagina, re.IGNORECASE)
        if m:
            imagen = html.unescape(m.group(1)).strip()
            if imagen.startswith("//"):
                imagen = "https:" + imagen
            if imagen.startswith("http"):
                return imagen
    return None


def poner_imagen(noticia):
    if not noticia.get("imagen"):
        noticia["imagen"] = imagen_de_pagina(noticia["enlace"]) or IMAGEN_POR_DEFECTO or None


def fecha_a_numero(texto):
    if not texto:
        return 0
    try:
        return email.utils.parsedate_to_datetime(texto).timestamp()
    except Exception:
        pass
    try:
        from datetime import datetime
        return datetime.fromisoformat(texto.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0


def leer_feed(nombre, url):
    peticion = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (aviso-noticias)"})
    with urllib.request.urlopen(peticion, timeout=30) as respuesta:
        raiz = ET.fromstring(respuesta.read())

    noticias = []
    # RSS 2.0
    for item in raiz.iter("item"):
        descripcion = item.findtext("description") or ""
        contenido = item.findtext("content:encoded", namespaces=NS) or ""
        imagen = None
        for etiqueta in ("media:content", "media:thumbnail"):
            nodo = item.find(etiqueta, NS)
            if nodo is not None and nodo.get("url"):
                imagen = nodo.get("url")
                break
        if not imagen:
            enc = item.find("enclosure")
            if enc is not None and (enc.get("type") or "").startswith("image"):
                imagen = enc.get("url")
        noticias.append({
            "fuente": nombre,
            "titulo": sin_html(item.findtext("title")),
            "enlace": (item.findtext("link") or "").strip(),
            "resumen": sin_html(descripcion),
            "imagen": imagen or primera_imagen(descripcion, contenido),
            "fecha": fecha_a_numero(item.findtext("pubDate")),
        })
    # Atom
    for entrada in raiz.findall("atom:entry", NS):
        enlace = entrada.find("atom:link[@rel='alternate']", NS)
        if enlace is None:
            enlace = entrada.find("atom:link", NS)
        resumen = (entrada.findtext("atom:summary", namespaces=NS)
                   or entrada.findtext("atom:content", namespaces=NS)
                   or entrada.findtext(".//media:description", namespaces=NS)  # vídeos de YouTube
                   or "")
        miniatura = entrada.find(".//media:thumbnail", NS)
        noticias.append({
            "fuente": nombre,
            "titulo": sin_html(entrada.findtext("atom:title", namespaces=NS)),
            "enlace": enlace.get("href") if enlace is not None else "",
            "resumen": sin_html(resumen),
            "imagen": (miniatura.get("url") if miniatura is not None else None) or primera_imagen(resumen),
            "fecha": fecha_a_numero(entrada.findtext("atom:updated", namespaces=NS)
                                    or entrada.findtext("atom:published", namespaces=NS)),
        })
    return [n for n in noticias if n["titulo"] and n["enlace"]]


def normalizar(texto):
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def interesa(noticia):
    if not PALABRAS:
        return True
    titulo = normalizar(noticia["titulo"])
    return any(normalizar(p) in titulo for p in PALABRAS)


def cargar_estado():
    if not os.path.exists(ARCHIVO_ESTADO):
        return None
    with open(ARCHIVO_ESTADO, encoding="utf-8") as f:
        return json.load(f)


def guardar_estado(enlaces):
    with open(ARCHIVO_ESTADO, "w", encoding="utf-8") as f:
        json.dump(enlaces[:MAX_GUARDADAS], f, indent=2)


def recortar(texto, limite):
    return texto if len(texto) <= limite else texto[: limite - 1].rstrip() + "…"


def crear_embed(noticia, color):
    embed = {
        # Si el nombre de la fuente ya empieza por un emoji, no se añade el 📰
        "author": {"name": noticia["fuente"] if not noticia["fuente"][:1].isalnum()
                   else f"📰 {noticia['fuente']}"},
        "title": recortar(noticia["titulo"], 256),
        "url": noticia["enlace"],
        "description": recortar(noticia["resumen"], 300),
        "color": color,
    }
    if noticia.get("imagen"):
        embed["image"] = {"url": noticia["imagen"]}
    return embed


def enviar(cuerpo):
    peticion = urllib.request.Request(
        WEBHOOK_URL,
        data=json.dumps(cuerpo).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "DiscordBot (aviso-noticias, 1.0)",
        },
        method="POST",
    )
    with urllib.request.urlopen(peticion, timeout=30):
        pass


def main():
    if not WEBHOOK_URL:
        sys.exit("Falta DISCORD_WEBHOOK_NOTICIAS.")

    fuentes = leer_fuentes()
    colores = {nombre: COLORES[i % len(COLORES)] for i, (nombre, _) in enumerate(fuentes)}
    noticias, fallos = [], []
    for nombre, url in fuentes:
        try:
            leidas = leer_feed(nombre, url)
            noticias += leidas
            print(f"✅ {nombre}: {len(leidas)} publicaciones leídas.")
        except Exception as e:
            fallos.append(nombre)
            print(f"⚠️ No se pudo leer {nombre} ({url}): {e}")

    if fallos and len(fallos) == len(fuentes):
        sys.exit("No se ha podido leer ninguna fuente. Revisa las URL de FUENTES.")

    vistas = cargar_estado()

    if not noticias:
        print("Las fuentes no han devuelto ninguna publicación.")
        return

    # Publicación forzada: las N más recientes, aunque ya se hubieran visto
    if FORZAR > 0:
        print(f"Publicación forzada de las {FORZAR} novedades más recientes.")
        vistas = [n["enlace"] for n in noticias if n not in
                  sorted(noticias, key=lambda n: n["fecha"], reverse=True)[:FORZAR]]
        guardar_estado(vistas)

    # Primera ejecución: guarda las noticias actuales sin avisar
    if vistas is None:
        guardar_estado([n["enlace"] for n in noticias])
        print(f"Primera ejecución: {len(noticias)} noticias guardadas, sin avisos.")
        return

    nuevas = [n for n in noticias if n["enlace"] not in vistas and interesa(n)]
    # Las más recientes primero, y solo hasta el máximo
    nuevas.sort(key=lambda n: n["fecha"], reverse=True)
    elegidas = nuevas[:max(MAX_NOTICIAS, FORZAR)]
    # Las que no caben ni interesan también se marcan como vistas, para no avisarlas tarde
    descartadas = [n["enlace"] for n in noticias if n["enlace"] not in vistas and n not in elegidas]

    if not elegidas:
        guardar_estado(descartadas + vistas)
        print("No hay noticias nuevas" + (" con esas palabras clave." if PALABRAS else "."))
        return

    for i, noticia in enumerate(reversed(elegidas)):
        poner_imagen(noticia)
        cuerpo = {
            "content": MENCION if (MENCION and i == 0) else None,
            "embeds": [crear_embed(noticia, colores.get(noticia["fuente"], COLORES[0]))],
            "allowed_mentions": {"parse": ["everyone", "roles"]},
        }
        try:
            enviar(cuerpo)
        except urllib.error.HTTPError as e:
            guardar_estado(vistas)
            sys.exit(f"Error al avisar en Discord ({e.code}): {e.read().decode()}")
        vistas.insert(0, noticia["enlace"])
        guardar_estado(vistas)
        print(f"Avisada [{noticia['fuente']}]: {noticia['titulo']}")
        time.sleep(1)

    guardar_estado(descartadas + vistas)


if __name__ == "__main__":
    main()
