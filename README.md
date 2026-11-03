# Aviso de vídeos nuevos de YouTube en Discord

Publica un mensaje en un canal de Discord cada vez que subes un vídeo a YouTube.
**No necesita ningún bot en el servidor**: usa un webhook de Discord y se ejecuta
gratis en GitHub Actions, así que no tienes que dejar tu ordenador encendido.

Comprueba el canal cada 15 minutos (GitHub a veces se retrasa unos minutos más).

---

## 1. Crea el webhook en Discord

1. En tu servidor, pasa el ratón por el canal donde quieres los avisos → ⚙️ **Editar canal**.
2. **Integraciones → Webhooks → Nuevo webhook**.
3. Ponle nombre (por ejemplo "Nuevo vídeo") y tu foto de canal como avatar.
4. Pulsa **Copiar URL del webhook**. Guárdala: **no la compartas con nadie**,
   porque quien la tenga puede escribir en ese canal.

## 2. Busca el ID de tu canal de YouTube

Entra en <https://www.youtube.com/account_advanced> con tu cuenta.
Copia el **ID del canal** (empieza por `UC...`).

## 3. Sube esto a GitHub

1. Crea una cuenta en <https://github.com> si no tienes.
2. **New repository** → ponle un nombre (por ejemplo `aviso-youtube`) →
   márcalo como **Public** → **Create repository**.
   (Público es gratis e ilimitado. La URL del webhook va guardada como secreto,
   así que nadie la ve.)
3. Pulsa **uploading an existing file** y sube **todo el contenido de esta carpeta**,
   incluida la carpeta `.github` con `workflows/aviso.yml` dentro.
   Si el navegador no te deja subir la carpeta `.github`, crea el archivo a mano:
   **Add file → Create new file**, escribe como nombre `.github/workflows/aviso.yml`
   y pega su contenido.

## 4. Configura tus datos

En el repositorio: **Settings → Secrets and variables → Actions**.

- Pestaña **Secrets** → **New repository secret**
  - Nombre: `DISCORD_WEBHOOK_URL`
  - Valor: la URL del webhook del paso 1
- Pestaña **Variables** → **New repository variable**
  - Nombre: `YOUTUBE_CHANNEL_ID`
  - Valor: tu ID `UC...` del paso 2
- (Opcional) otra variable llamada `MENSAJE` para personalizar el aviso. Ejemplo:

  ```
  @everyone 🔥 ¡Nuevo vídeo de Once Human! **{titulo}**
  {enlace}
  ```

  `{titulo}` y `{enlace}` se cambian solos. Puedes usar `@everyone`, `@here`
  o mencionar un rol con `<@&ID_DEL_ROL>`.

## 5. Actívalo

1. Pestaña **Actions** del repositorio → si te lo pide, pulsa para habilitar los workflows.
2. Entra en **Aviso de vídeos nuevos → Run workflow**.

La **primera vez no avisa de nada**: solo apunta los vídeos que ya tienes para no
publicar todo tu canal de golpe. A partir de ahí, cada vídeo nuevo saldrá en Discord.

Para probarlo, publica un vídeo (tiene que ser **público**; los ocultos y privados
no salen en el feed) y espera unos 15–20 minutos, o pulsa **Run workflow** otra vez.

---

## Preguntas frecuentes

**¿Avisa también de Shorts y directos?**
Sí, de todo lo que aparezca como vídeo público en tu canal.

**¿Lo puedo usar en varios servidores?**
Sí. Crea un webhook en cada servidor y duplica el repositorio, o pide que te
adapte el script para varios webhooks.

**Ha dejado de funcionar.**
GitHub desactiva las tareas programadas si un repositorio público pasa 60 días sin
cambios. Si estás más de dos meses sin subir vídeos, entra en **Actions** y vuelve
a activarlo.

**Se repite un aviso o no sale.**
Mira el registro en **Actions** (cada ejecución dice qué ha hecho). El archivo
`videos_vistos.json` guarda los vídeos ya avisados; si lo borras, la siguiente
ejecución vuelve a empezar sin avisar.
