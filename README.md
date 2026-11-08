# Bachateca · app para iPhone (gratis)

Bachateca es una app web instalable: se añade a la pantalla de inicio del iPhone, se abre a pantalla completa,
funciona sin conexión y guarda tus figuras y vídeos **en el propio iPhone** (sin límite de 20 MB y sin subir nada).

## 1. Publicarla gratis con GitHub Pages (una sola vez, ~5 minutos)

1. Entra en github.com con tu cuenta (o crea una gratis).
2. Pulsa **New repository**, nombre `bachateca`, marca **Public** y créalo.
3. En el repositorio: **Add file → Upload files**, arrastra **todo el contenido del repositorio** (todos los archivos
   y carpetas de esta carpeta, incluida la carpeta `sonidos/`) y pulsa **Commit changes**.
   Sin `sonidos/` la app no funciona sin conexión.
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
- Los vídeos: **Ajustes → Copia completa** los guarda después de la copia. Guárdalos también en **Archivos o iCloud Drive**
  (no en Fotos, que puede cambiarles el nombre): así **Restaurar o importar → Recuperar vídeos** los devuelve a su figura.

**Ajustes → Instantáneas**: la app guarda sola una copia al día y otra antes de importar o restaurar; no sustituyen a
Exportar, porque viven en el mismo iPhone.

## 5. Actualizar la app

Sube el `index.html` nuevo al repositorio y sube el número de versión en `sw.js` (por ejemplo, `bachateca-v54` → `bachateca-v55`).
La próxima vez que abras la app con conexión, se actualizará sola. Tus datos no se tocan.

## Practicar para el social

- **Simulacro de social** (en Social y en Repasar): mientras suena la cuenta, la app te da una posición y un agarre.
  Pulsa **«La tengo»** antes del siguiente 1; después ves las salidas posibles y te calificas. Esa calificación
  alimenta tu repaso de enlaces. Si una posición no tiene salidas, se convierte en una pregunta para clase.
- **Para tu próxima clase** (en Inicio): cada bloque que te atascas crea una pregunta. Si luego guardas una figura
  desde esa posición, la app te ofrece marcar la pregunta como respondida.
- Enlazar, Social y Repasar muestran un selector de baile solo cuando tienes figuras de más de un baile; los enlaces,
  las cadenas y la lista del social nunca mezclan bailes.
- Las cadenas respetan el agarre elegido. Puedes usar **«Solo seguras»** y **«Agarres exactos»**; los pasos muestran
  «en práctica» y «agarre sin indicar».
- Una figura marcada en un social cuenta como un repaso «Fluida» (una vez al día); si borras el registro, se deshace.
  «Atrasada» ya no se confunde con «Olvidada».
- La cuenta pide a iOS el audio de reproducción, para que suene aunque el iPhone esté en silencio.
- **Aprender a enlazar** (versión 1.52):
  - El repaso de enlaces ahora es independiente en cada baile.
  - **«Lo he bailado»** marca los enlaces que ya has probado, en la ficha («Y después») y en las cadenas. Las cadenas
    prefieren los enlaces probados. Tras un social en el que marcas dos figuras seguidas, la app te pregunta si
    bailaste A → B.
  - **«Preguntas de memoria»** (en Repasar): ¿Dónde termina?, ¿Desde dónde entras? y ¿Qué puedes hacer después?
    Cuentan como repaso de la figura, una vez al día.
  - En **«Errores que cometo»** se cuentan las repeticiones (×N). Puedes marcar un error como **«Ya no me pasa»** y
    volver a ponerlo con **«Me ha vuelto a pasar»**. Mientras un error siga activo, la figura se repasa como mucho
    cada 7 días.
  - **«Opciones de la cadena»**: terminar en una posición, incluir una figura, dejar fuera otras, y elegir la longitud (de 2 a 6).

## Vídeo y práctica (versión 1.53)

- **Paso fino**: en el vídeo de la figura y en **Comparar** puedes avanzar o retroceder 0,1 s para ver bien un movimiento.
- **«Nota aquí»**: mientras ves el vídeo de la clase, apunta una nota en el momento exacto. Se muestra mientras suena
  esa parte del vídeo y queda en una lista con su tiempo. Si añades una parte al vídeo, las notas pasan a la parte
  anterior; si reemplazas el vídeo, se borran.
- **«Superponer»** (en Comparar): pone tu vídeo encima del de referencia, con transparencia y con espejo para tu vídeo.
- **«Práctica guiada»** (en Repasar): una sesión de 10 o 20 minutos con figuras, enlaces y una cadena con la cuenta
  de la voz. Te calificas después de cada bloque, y puedes marcar **«Con pareja»**.
- **Dos medidas por figura**, en la ficha: **«La recuerdo»** y **«Me sale con pareja»**. La segunda solo sube con
  pruebas reales: socials, práctica guiada con pareja o intentos en los que solo marcas «Bien». En Social salen
  primero las figuras que te salen mejor con pareja.

## Tus datos (versión 1.54)

- **Copia completa** (Ajustes): guarda un JSON con todas tus figuras y registros, más todos tus vídeos. Guárdala en
  **Archivos o iCloud Drive**, no en Fotos: Fotos puede cambiar el nombre de los archivos y entonces un vídeo no
  sabría a qué figura volver.
- **Recuperar vídeos**: elige en Archivos los vídeos de la copia; cada uno vuelve a su figura por el id que lleva en el nombre.
  Desde la versión 1.55 también reconoce los nombres en los que Safari cambió los espacios por «_».
- **Limpieza automática**: un vídeo que ya no pertenece a ninguna figura se borra solo a los 7 días, y nunca si está en
  una instantánea. **Ajustes → Espacio → Liberar ahora** lo hace al momento.

## Versión 1.57

- **Abre sin cobertura**: si la red tarda más de 3 segundos (por ejemplo, en un social con mala cobertura), la app se
  abre con la copia guardada en el iPhone; lo nuevo, si llega, se guarda para la próxima vez.
- **Preguntar a Claude qué trabajar** manda también los errores que se te repiten, cómo va tu memoria de las figuras y
  los enlaces que ya has bailado, para que los consejos sean más concretos.
- El aviso **«N vídeos no tienen copia»** ya no cuenta vídeos que no están en este iPhone.

## Arreglo (versión 1.56)

- **Grabarme con conteo** vuelve a encender la cámara con «Grabar también el sonido del micrófono» marcado. Desde la
  1.51 la app ponía el audio en «solo reproducir» (para que el conteo se oiga con el iPhone en silencio) y en ese modo
  iOS no deja usar el micrófono: la cámara solo se encendía desmarcándolo.

## Pruebas automáticas

Antes de publicar un cambio, comprueba que no se ha roto nada (repaso, enlaces, migración de datos, importar copias, vídeos):

```
pip install playwright && playwright install chromium   # solo la primera vez
python3 tests/test_bachateca.py
```

Para probar también con el motor de Safari: `playwright install webkit` y luego `BROWSER=webkit python3 tests/test_bachateca.py`.

Abren la app en un navegador sin ventana y con datos de prueba: no tocan tus datos.

## Versión de los datos

Los datos guardados llevan un número de versión (`schema`). Si un cambio necesita guardar las figuras de otra forma,
se sube `SCHEMA` en `index.html` y se añade un paso en `MIGRATIONS`: al abrir la app, los datos antiguos se ponen al día
solos, sin borrar nada. La versión 1.54 deja los datos en la versión 11 (la 1.53 los pasó a la 11, la 1.52 a la 10 y la versión 1.51 los había pasado a la 7 con las preguntas para clase). Las copias exportadas con una versión anterior se ponen al día al importarlas.

## Limitaciones conocidas

- No sincroniza entre dispositivos: cada iPhone/Mac tiene sus propios datos (usa Exportar/Importar para pasarlos).
- La ayuda de Claude funciona a través de la hoja de compartir: compartes los fotogramas con la app de Claude
  y pegas su respuesta en la ficha, que se rellena sola. No usa ninguna clave de pago.

## Licencia

Código bajo la [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0):
uso libre para fines no comerciales; el uso comercial requiere permiso del autor.
El nombre «Bachateca» y el icono no se incluyen en la licencia. Ver `LICENSE`.
