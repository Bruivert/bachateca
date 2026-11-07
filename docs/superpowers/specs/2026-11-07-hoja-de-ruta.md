# Bachateca · Hoja de ruta de mejoras

Estado: **propuesta pendiente de aprobación**. No se implementa nada hasta aprobar el plan de cada fase.

Punto de partida: la auditoría técnica del 6-11-2026 (v1.49, `SCHEMA 6`, `bachateca-v49`). La auditoría es el diagnóstico inicial, no el límite: aquí se añaden oportunidades de aprendizaje y capacidades nuevas.

## Principios

1. **Primero, los datos.** Ninguna función nueva se publica mientras existan caminos de pérdida de datos conocidos (P0-1, P0-2, P0-3).
2. **Nada se quita.** Toda funcionalidad actual se conserva (inventario en §4). Si una corrección cambia un comportamiento, se dice y se decide (§5).
3. **Cada fase deja la app publicable.** Plan aprobado → implementación con pruebas → todas las pruebas en verde → lista manual en iPhone → publicar.
4. **Sin reescritura, sin backend, sin framework, sin bundler.** La refactorización es progresiva y se hace cuando la pide una función.
5. **La IA no inventa datos.** Solo trabaja sobre lo que hay en Bachateca y nunca crea compatibilidades entre figuras.

## 1. Criterios de evaluación

| Criterio | Pregunta |
|---|---|
| Aprendizaje | ¿Mejora recordar y ejecutar figuras y enlaces en un social? (recuperación activa, práctica intercalada y variable, decidir bajo presión de tiempo, feedback concreto) |
| Utilidad | ¿Lo va a usar de verdad un leader principiante o intermedio, en clase, en casa o en el social? |
| Complejidad | Baja: horas, una función. Media: varios días, toca datos o interfaz. Alta: semanas o depende de capacidades de iOS dudosas |
| Riesgo | Probabilidad de romper algo o perder datos al implementarlo |
| Dependencias | Lo que tiene que existir antes |

## 2. Propuestas evaluadas

### 2.1 Integridad de datos (bloquea todo lo demás)

| ID | Propuesta | Aprendizaje | Utilidad | Complejidad | Riesgo | Depende de | Fase |
|---|---|---|---|---|---|---|---|
| I1 | Modo seguro si la lectura de datos falla al arrancar: no escribe nada y avisa (P0-1) | — (protege todo) | Muy alta | Baja | Bajo | — | 1 |
| I2 | Instantáneas automáticas locales (diaria, antes de importar o restaurar, antes de un encogimiento grande) y «Restaurar» en Ajustes | — | Muy alta | Media | Bajo | I1 | 1 |
| I3 | Al arrancar, usar la copia más reciente entre IndexedDB y localStorage; avisar si el guardado de respaldo falla (P0-3) | — | Alta | Baja | Bajo | I1 | 1 |
| I4 | Escapar los ids en el HTML y validar la forma de una copia importada (P1-1) | — | Alta | Baja | Bajo | — | 1 |
| I5 | «Añadir al repertorio» conserva tus figuras y pregunta si hay distintas; «Reemplazar todo» guarda antes una instantánea (P0-2) | — | Muy alta | Media | Medio (cambia un comportamiento probado) | I2 | 1 |
| I6 | La copia por descarga pregunta «¿Se ha guardado?» antes de darse por hecha (P1-2) | — | Alta | Baja | Bajo | — | 1 |
| I7 | Limpieza de vídeos huérfanos que respeta las instantáneas (P1-3) | — | Media (espacio) | Baja | **Alto sin I1 e I2** | I1, I2 | 2 |
| I8 | Marca `modificado` en cada figura y registro (permite fusionar copias con criterio) | — | Media | Baja | Bajo (migración 6→7) | — | 2 |
| I9 | Copia completa con vídeos para cambiar de iPhone (JSON más los vídeos por la hoja de compartir, y restaurarlos por su nombre) | — | Alta | Media | Medio [VALIDAR memoria en iPhone] | I6, I8 | 2 |
| P2 | Service Worker: límite de 3 s para la red y `cache:"reload"` al instalar; README al día (la lista de archivos) (P1-7) | — | Alta en el social | Baja | Bajo | — | 2 |

### 2.2 Coherencia de la lógica actual

| ID | Propuesta | Aprendizaje | Utilidad | Complejidad | Riesgo | Depende de | Fase |
|---|---|---|---|---|---|---|---|
| E1 | Enlaces, cadenas, Social y bloqueo filtran por baile (P1-4) | **Alto**: deja de proponer enlaces que no existen | Alta | Baja | Bajo | — | 3 |
| E2 | Cadena desde el agarre elegido; aviso «agarre sin indicar»; opción de agarres estrictos (P1-5) | Medio | Media | Baja | Bajo | E1 | 3 |
| L1 | Una figura que sale en el social cuenta como repaso; «atrasada» y «olvidada» se separan (P1-6) | **Alto**: el repaso refleja lo que se baila de verdad | Alta | Baja | Medio (cambian las cifras de Inicio) | — | 3 |
| L7 | «Preguntas para clase»: cada bloqueo genera una pregunta que se sigue hasta resolverla («ya tengo salida desde X») | Medio | Alta | Baja | Bajo | — | 3 |
| V4 | `navigator.audioSession` para que el conteo se oiga con el interruptor de silencio y con el micrófono activo | — | Alta | Baja | Bajo [VALIDAR] | — | 3 |
| V5 | Modo «copia en memoria» solo para el vídeo que lo necesita, y caché de vídeos con límite (P1-9) | — | Alta (estabilidad) | Media | Medio | — | 3 |
| P3 | Extraer la lógica pura (repaso, enlaces, cadenas, importación) a funciones que reciben los datos, y un punto único de cambios `commit()` | Indirecto | — | Media | Medio (las pruebas lo cubren) | Fase 1 | 3 |

### 2.3 Nuevas capacidades de aprendizaje

| ID | Propuesta | Aprendizaje | Utilidad | Complejidad | Riesgo | Depende de | Fase |
|---|---|---|---|---|---|---|---|
| L3 | **Simulacro de social**: una posición y un agarre al azar mientras suena el pulso; hay que decidir una salida antes del siguiente 1; al final, cuáles costaron | **Muy alto**: entrena justo la decisión que falla en el bloqueo, con presión de tiempo | Alta | Media | Bajo | E1, E2 | 4 |
| E3 | **Enlaces comprobados**: marcar «este enlace lo he bailado» (A → B). Las cadenas y el simulacro prefieren los comprobados; los no comprobados se muestran como «sin probar» | **Alto**: convierte una compatibilidad deducida en conocimiento real y reduce falsos positivos | Alta | Media | Medio (dato nuevo, migración) | E1, I8 | 4 |
| L2 | Preguntas de recuperación generadas con los datos propios: «¿Cómo acaba X?», «¿Desde dónde entras en X?», «¿Qué puedes hacer después de X?» | Alto | Alta | Media | Bajo | E1 | 4 |
| L6 | **Errores recurrentes**: el mismo error en varios intentos se cuenta, se marca «resuelto» con fecha, se ve su evolución y aumenta la frecuencia de repaso mientras esté activo | Alto | Alta | Media | Bajo (migración) | I8 | 4 |
| E4 | Cadenas con posición final, figuras obligatorias o excluidas, longitud y sin repetir la anterior | Medio | Media | Media | Bajo | E1, E2 | 4 |
| V1 | Avance fino (±0,1 s) en Comparar y en la ficha | Medio | Alta | Baja | Bajo [VALIDAR precisión en iOS] | — | 4 |
| L4 | Dos medidas por figura: «la recuerdo» y «la ejecuto con pareja» | Alto | Media | Media | Medio (modelo de datos) | L1 | 5 |
| L5 | Cadenas como unidad de repaso (práctica intercalada) | Alto | Media | Media | Bajo | E4 | 5 |
| L8 | Sesión de práctica física guiada: bloques, repeticiones y conteo con la voz que ya existe | Medio-alto | Media | Media | Bajo | — | 5 |
| V2 | Notas ancladas a un momento del vídeo de la clase | Medio | Media | Baja | Bajo | — | 5 |
| V3 | Superposición o espejo del intento sobre la clase | Medio | Media | Media | Medio [VALIDAR iOS] | V1 | 5 |
| IA1 | El prompt de «Preguntar a Claude» incluye errores activos, estado del repaso y enlaces comprobados | Medio | Media | Baja | Bajo | L6, E3 | 5 |

### 2.4 Pospuestas o descartadas

| Propuesta | Motivo |
|---|---|
| Sincronización en la nube, cuentas, backend | La privacidad es un requisito y el riesgo se resuelve con I2 e I9 |
| API de IA directa desde la app | Necesita claves en el cliente o un servidor; la hoja de compartir ya funciona |
| IA que ordena cadenas (IA2) | Poco valor hasta que existan E3 y E4; si se hace, la IA solo ordena candidatos válidos que genera el código |
| Análisis de postura con visión artificial | Complejidad muy alta y fiabilidad dudosa en la web de iOS |
| Reescritura o cambio de framework | Sin beneficio que compense el riesgo |

## 3. Fases

| Fase | Contenido | Resultado publicable |
|---|---|---|
| **0 · Red de seguridad** | CI con Chromium y WebKit; la prueba intermitente deja de serlo | La misma app, con pruebas automáticas en cada push |
| **1 · Integridad** | I1–I6 | Ningún camino conocido de pérdida de datos; instantáneas restaurables |
| **2 · Copias y almacenamiento** | I7, I8, I9, P2 | Cambiar de iPhone sin perder vídeos; arranque rápido sin cobertura |
| **3 · Coherencia** | E1, E2, L1, L7, V4, V5, P3 | Enlaces y repaso fiables; lógica pura probada sin navegador |
| **4 · Aprender a enlazar** | L3, E3, L2, L6, E4, V1 | Entrenamiento específico contra el bloqueo |
| **5 · Profundizar** | L4, L5, L8, V2, V3, IA1 | Práctica física y análisis más finos |

Cada fase tiene su propio plan de implementación, que se aprueba antes de empezarla. Las fases 0 y 1 ya tienen plan: `docs/superpowers/plans/2026-11-07-fase-0-1-integridad.md`.

## 4. Regresión: lo que no se puede romper

**Inventario protegido** (cada línea tiene al menos una prueba automática, salvo las marcadas como manuales):

| Área | Funcionalidad | Pruebas actuales |
|---|---|---|
| Datos | Migraciones 0→6, conservar campos desconocidos, rechazar copias más nuevas | `migracion_*`, `arranque_migra_y_guarda`, `importar_copia_*` |
| Biblioteca | Crear, editar, borrar con Deshacer, filtros y búsqueda, ejemplos | `ficha_y_filtros`, `recorrer_pestanas_sin_errores` |
| Repaso | Escalera 1-3-7-14-30-60, sesiones, entreno de Inicio, incompletas cada día | `repaso_espaciado`, `entreno_completo`, `incompleta_*` |
| Enlaces | Salidas por posición y agarre, mapa, cadenas | `enlaces_por_posicion_y_agarre`, `cadenas_validas` |
| Social | Marcar, bloqueo, registro, sugerencias de estado | `recorrer_pestanas_sin_errores` (parcial; se amplía en la fase 1) |
| Vídeos | Guardar, recortar, portadas, respaldos frag/plain/mem, aviso de vídeos sin copia, borrar con Deshacer | `portadas_*`, `video_*`, `videos_*`, `aviso_videos_sin_copia`, `borrar_intento_y_figura_borra_videos` |
| Intentos, pulso, comparar | Grabar, marcar el pulso, comparar por tiempos, marcas y errores | `intento_*`, `marcar_pulso_*`, `comparar_*`, `marcas_y_errores_que_cometo` |
| Conteo | Grabar con conteo, pulso automático, apagar la cámara | `grabarme_con_conteo`, `pulso_automatico_del_conteo`, `salir_de_grabar_apaga_la_camara`, `conteo_*` |
| Offline | Páginas guardadas por separado en el SW | `service_worker_no_confunde_las_paginas` |
| Accesibilidad, aspecto | Tema, foco, VoiceOver | `apariencia`; VoiceOver: manual |

**Reglas de cada fase:**

1. Las 49 pruebas actuales siguen pasando en Chromium. Una prueba solo cambia si una decisión aprobada (§5) cambia el comportamiento que comprueba, y el cambio se explica en el commit.
2. Ninguna prueba se desactiva para conseguir verde. Las que no pueden correr en WebKit (cámara simulada) se marcan como solo Chromium con el motivo escrito.
3. Cada fallo corregido entra con la prueba que lo reproduce, escrita antes del arreglo.
4. Cada cambio de datos sube `SCHEMA` con su paso en `MIGRATIONS` y su prueba de migración.
5. Antes de publicar: lista manual en iPhone (abajo) y subir `VERSION` en `sw.js`.

**Lista manual en iPhone (por versión publicada):** instalar desde Safari; abrir sin conexión; añadir una figura con vídeo; repasar; registrar un social; exportar la copia y comprobar que el archivo está en Archivos; importarla; grabar con conteo y escuchar el vídeo; comparar; borrar y deshacer; bloquear la pantalla a mitad de una grabación.

## 5. Decisiones que necesito de ti

| # | Decisión | Mi recomendación |
|---|---|---|
| D1 | «Añadir al repertorio» con figuras que ya tienes y son distintas: ¿se conservan las tuyas por defecto y se pregunta? Cambia la prueba `importar_conserva_intentos_locales`, que hoy exige que gane la copia | Sí: preguntar «Usar las de la copia» o «Conservar las mías»; las dos opciones siguen existiendo · Aprobada |
| D2 | «Reemplazar todo» deja de borrar vídeos al momento (los borrará la limpieza de la fase 2, respetando las instantáneas), para que restaurar una instantánea los recupere | Sí · Aprobada |
| D3 | Copia o vídeo descargado (sin hoja de compartir): preguntar «¿Se ha guardado?» antes de darlo por copiado. Cambia un paso de `aviso_videos_sin_copia` | Sí · Aprobada |
| D4 | (Fase 3) ¿Una figura marcada en el social cuenta como un repaso «Fluida»? | Sí, como máximo una vez al día · Aprobada |
| D5 | (Fase 3) ¿Las cadenas incluyen figuras «en práctica»? | Sí, señaladas, con un interruptor para «solo seguras» · Aprobada |
