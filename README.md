# Bachateca · app para iPhone (gratis)

Bachateca es una app web instalable: se añade a la pantalla de inicio del iPhone, se abre a pantalla completa,
funciona sin conexión y guarda tus figuras y vídeos **en el propio iPhone** (sin límite de 20 MB y sin subir nada).

## 1. Publicarla gratis con GitHub Pages (una sola vez, ~5 minutos)

1. Entra en github.com con tu cuenta (o crea una gratis).
2. Pulsa **New repository**, nombre `bachateca`, marca **Public** y créalo.
3. En el repositorio: **Add file → Upload files**, arrastra **todos** los archivos de esta carpeta
   (`index.html`, `sw.js`, `manifest.webmanifest` y los `icon-*.png`) y pulsa **Commit changes**.
4. Ve a **Settings → Pages**. En *Build and deployment*, elige **Deploy from a branch**, rama **main**, carpeta **/ (root)** y **Save**.
5. En un minuto tendrás la dirección: `https://TU-USUARIO.github.io/bachateca/`

El código queda público, pero **tus datos no**: figuras, registros y vídeos solo existen en tu iPhone.

## 2. Instalarla en el iPhone

1. Abre la dirección con **Safari** (no con Chrome).
2. Pulsa **Compartir** → **Añadir a pantalla de inicio** → **Añadir**.
3. Ábrela desde el icono. En **Ajustes** pulsa **Proteger mis datos**.

## 3. Traer tus datos del artefacto de Claude

1. En el artefacto: **Ajustes → Copiar JSON**.
2. En la app: **Ajustes**, pega el texto en el recuadro y pulsa **Añadir al repertorio**.
3. Los vídeos no viajan en ese texto: vuelve a añadirlos desde cada figura.

## 4. Copias de seguridad

Todo vive en el iPhone: si borras la app, se pierde. Cada cierto tiempo:
- **Ajustes → Exportar copia** (figuras, registros y ajustes) y guárdala en Archivos o iCloud Drive.
- Los vídeos ya están en tu carrete; desde cada figura puedes usar **Guardar en Fotos**.

## 5. Actualizar la app

Sube el `index.html` nuevo al repositorio y cambia `bachateca-v1` por `bachateca-v2` en `sw.js`.
La próxima vez que abras la app con conexión, se actualizará sola. Tus datos no se tocan.

## Limitaciones conocidas

- No sincroniza entre dispositivos: cada iPhone/Mac tiene sus propios datos (usa Exportar/Importar para pasarlos).
- La ayuda de Claude funciona a través de la hoja de compartir: compartes los fotogramas con la app de Claude
  y pegas su respuesta en la ficha, que se rellena sola. No usa ninguna clave de pago.

## Licencia

Código bajo la [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0):
uso libre para fines no comerciales; el uso comercial requiere permiso del autor.
El nombre «Bachateca» y el icono no se incluyen en la licencia. Ver `LICENSE`.
