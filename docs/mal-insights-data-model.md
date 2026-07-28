# MAL Insights — Modelo de datos y arquitectura

Este documento describe el estado implementado de **MAL Insights — Anime & Manga** dentro de MVS Tracker, junto con las extensiones que siguen pendientes.

MAL Insights nació como **MAL Insight Lab** y continúa usando la aplicación Django técnica `mal_data`. Anime se encuentra funcionalmente estable. Manga ya dispone de biblioteca, dashboard, sincronización de progreso, rescates manuales y Chapter Signals canónicos y externos.

El checkpoint documentado corresponde a:

```text
Aplicación Django técnica: mal_data
Nombre público del módulo: MAL Insights
Ruta Anime: /anime/
Ruta Manga: /manga/
Migraciones documentadas: hasta mal_data.0016
Base de datos operativa: Supabase PostgreSQL
Pruebas de mal_data: 46 OK
Pruebas globales: 349 OK
Pruebas automatizadas: SQLite en memoria
```

El módulo combina:

- MyAnimeList como fuente principal de la relación personal.
- AniList como fuente pública de emisión, descubrimiento y metadatos de Anime.
- MANGA Plus y Weeb Central como fuentes explícitas de disponibilidad de capítulos.
- Persistencia local-first en PostgreSQL.
- Acceso público de solo lectura.
- Acciones privadas para el owner autenticado.
- Sincronización explícita y separada por responsabilidad.
- Dos mundos internos: Anime y Manga.
- Integración futura con Hibi Log.

---

## 1. Alcance del módulo

MAL Insights administra contenido perteneciente al ecosistema de MyAnimeList:

```text
MAL Insights
├── Anime
└── Manga
```

Anime incluye actualmente:

- Biblioteca personal.
- Watching y Rewatching.
- Episode Signals.
- Seasonal Board.
- Broadcast Watchlist.
- Command Logs.
- Search / Rescue.
- Relation Scan.
- Franchise Audit.
- Sequel Radar.
- Metadatos externos.
- OAuth con renovación automática.

Manga incluye actualmente:

- Manga Command Center.
- Archivo público por estado.
- Reading y Rereading.
- Sincronización optimizada de biblioteca.
- Sincronización de progreso activo.
- Manual Manga Rescues.
- Manga Command Logs.
- Señales canónicas de finalización.
- Chapter Signals con disponibilidad externa.
- Fuentes persistentes por manga.
- Prioridad configurable y fallback automático.
- MANGA Plus y Weeb Central.

Watchroom administra series, películas, cartoons, documentales y live action fuera del ecosistema anime. Game Kiroku administra videojuegos. Estos dominios no se mezclan dentro de MAL Insights.

---

## 2. Principios de arquitectura

MAL Insights sigue estas reglas:

- MyAnimeList es la fuente principal del estado, progreso y score personal.
- AniList complementa Anime; no reemplaza la biblioteca personal.
- MANGA Plus y Weeb Central aportan disponibilidad de capítulos, no progreso personal.
- Los datos sincronizados se almacenan localmente.
- Las páginas normales leen desde la base local.
- Una vista GET normal no produce sincronizaciones ni escrituras ocultas.
- Las sincronizaciones se ejecutan mediante acciones explícitas del owner.
- Los procesos pesados se dividen por responsabilidad.
- El módulo trabaja con una única biblioteca personal.
- Los modelos no se relacionan con `User`.
- La autenticación decide quién puede escribir.
- El acceso público es de solo lectura.
- Las acciones mutables requieren normalmente login, POST y CSRF.
- OAuth utiliza rutas autenticadas, `state` y PKCE.
- Anime y Manga comparten OAuth, cliente MAL, sesión y base de datos.
- Anime y Manga conservan dashboards, navegación y señales propias.
- Las fuentes externas se vinculan una vez y luego se consultan por su identificador guardado.
- Un fallo externo individual no detiene la sincronización de los demás mangas.
- Hibi Log consumirá actividad derivada de ambos mundos en una etapa posterior.

---

## 3. Dos mundos dentro de MAL Insights

La aplicación Django técnica sigue siendo:

```text
mal_data
```

No existe una app separada para Manga.

### Anime

Ruta principal:

```text
/anime/
```

Navegación:

```text
Dashboard
Seasonal
All
Watching
On Hold
Plan to Watch
Completed
Dropped
Search
```

### Manga

Ruta principal:

```text
/manga/
```

Navegación:

```text
Dashboard
All
Reading
On Hold
Plan to Read
Completed
Dropped
```

`Rereading` forma parte de Reading, de la misma manera que Rewatching forma parte de Watching.

### Switch Anime / Manga

El encabezado compartido muestra un selector de mundo:

```text
MAL INSIGHTS                     [ ANIME | MANGA ]
```

Al cambiar de mundo:

- Cambia la ruta principal.
- Cambia la navegación secundaria.
- Cambia el dashboard.
- Cambian las métricas y señales.
- Se mantiene la identidad visual de MAL Insights.
- Se comparte la sesión del owner.
- Se comparte la conexión OAuth con MAL.

---

## 4. Modelo conceptual actual

```text
MALOAuthToken

AnimeEntry
├── AnimeAiringData
├── AnimeSyncEvent
└── AnimeRelation
    └── AnimeMetadata como fallback externo

ManualTrackedAnime
└── reconstruye o actualiza AnimeEntry

SeasonalAnime

MangaEntry
├── MangaSyncEvent
├── MangaChapterSignal
└── MangaSourceLink [0..n]

ManualTrackedManga
└── reconstruye o actualiza MangaEntry
```

### Responsabilidad de las entidades Manga

```text
MangaEntry
    Biblioteca personal local de Manga.

MangaSyncEvent
    Command Log de cambios personales.

ManualTrackedManga
    Excepción persistente para entradas omitidas por la lista MAL.

MangaChapterSignal
    Estado vigente de disponibilidad y capítulos pendientes.

MangaSourceLink
    Asociación persistente entre un manga local y una serie externa.
```

---

## 5. MangaEntry

`MangaEntry` representa una entrada personal de manga importada desde MyAnimeList.

### Campos implementados

| Campo | Tipo | Nulo / vacío | Descripción |
|---|---|---:|---|
| `mal_id` | `PositiveIntegerField` | No | Identificador único de MAL. |
| `title` | `CharField` | No | Título principal. |
| `title_japanese` | `CharField` | Sí | Título japonés. |
| `title_english` | `CharField` | Sí | Título inglés. |
| `main_picture_url` | `URLField` | Sí | Portada principal. |
| `media_type` | `CharField` | Sí | Tipo de publicación. |
| `publication_status` | `CharField` | Sí | Estado editorial. |
| `num_volumes` | `PositiveIntegerField` | No | Total conocido de volúmenes. |
| `num_chapters` | `PositiveIntegerField` | No | Total canónico conocido. |
| `start_date` | `DateField` | Sí | Fecha de inicio. |
| `end_date` | `DateField` | Sí | Fecha de término. |
| `list_status` | `CharField` | No | Estado personal en MAL. |
| `score` | `PositiveIntegerField` | No | Score personal. |
| `num_volumes_read` | `PositiveIntegerField` | No | Volúmenes leídos. |
| `num_chapters_read` | `PositiveIntegerField` | No | Capítulos leídos. |
| `is_rereading` | `BooleanField` | No | Relectura activa. |
| `updated_at_mal` | `DateTimeField` | Sí | Última actualización conocida en MAL. |
| `raw_data` | `JSONField` | Sí | Payload original almacenado. |
| `last_synced_at` | `DateTimeField` | No | Última sincronización local. |

### Estados personales

```text
reading
completed
on_hold
dropped
plan_to_read
```

`Rereading` se deriva de:

```text
is_rereading = True
```

### Título visible

Cuando existe título japonés:

```text
Título principal (日本語タイトル)
```

### Orden

```text
updated_at_mal descendente
title ascendente
```

---

## 6. MangaSyncEvent

`MangaSyncEvent` implementa el Command Log de Manga.

### Tipos implementados

```text
created
status_changed
chapter_changed
volume_changed
score_changed
```

### Campos

| Campo | Tipo | Nulo / vacío | Descripción |
|---|---|---:|---|
| `manga` | `ForeignKey` | Sí | Entrada relacionada. |
| `mal_id` | `PositiveIntegerField` | No | Snapshot del MAL ID. |
| `title_snapshot` | `CharField` | No | Título al momento del evento. |
| `event_type` | `CharField` | No | Tipo de cambio. |
| `old_value` | `CharField` | Sí | Valor anterior. |
| `new_value` | `CharField` | Sí | Valor nuevo. |
| `created_at` | `DateTimeField` | No | Fecha del evento. |

Ejemplos:

```text
CH_UPDATE
Seihantai na Kimi to Boku [CH. 42 → CH. 43]

VOLUME_UPDATE
Manga X [VOL. 8 → VOL. 9]

STATUS_UPDATE
Manga Y [Reading → Completed]
```

---

## 7. ManualTrackedManga

`ManualTrackedManga` protege entradas que existen en la lista real del usuario, pero que el endpoint general de lista de MAL omite.

### Campos

| Campo | Tipo | Nulo / vacío | Descripción |
|---|---|---:|---|
| `mal_id` | `PositiveIntegerField` | No | MAL ID único. |
| `title_snapshot` | `CharField` | Sí | Título de respaldo. |
| `status` | `CharField` | No | Estado personal fallback. |
| `chapters_read` | `PositiveIntegerField` | No | Capítulos leídos fallback. |
| `volumes_read` | `PositiveIntegerField` | No | Volúmenes leídos fallback. |
| `score` | `PositiveIntegerField` | No | Score fallback. |
| `is_rereading` | `BooleanField` | No | Rereading fallback. |
| `active` | `BooleanField` | No | Activa o desactiva el rescate. |
| `notes` | `TextField` | Sí | Contexto manual. |
| `created_at` | `DateTimeField` | No | Fecha de creación. |
| `updated_at` | `DateTimeField` | No | Última actualización. |

### Semántica

`ManualTrackedManga` no crea una segunda biblioteca.

```text
La lista general omite el manga
↓
ManualTrackedManga recuerda la excepción
↓
El detalle individual de MAL entrega el estado real cuando es posible
↓
MangaEntry se reconstruye o actualiza
↓
El tracker manual se mantiene alineado como fallback
```

---

## 8. MangaChapterSignal

`MangaChapterSignal` representa el objetivo de lectura vigente para un manga activo.

Cada `MangaEntry` puede tener como máximo una señal.

### Tipos de fuente de disponibilidad

```text
canonical
external
manual
```

### Campos principales

| Campo | Tipo | Nulo / vacío | Descripción |
|---|---|---:|---|
| `manga` | `OneToOneField` | No | Manga local asociado. |
| `mal_id` | `PositiveIntegerField` | No | MAL ID único. |
| `canonical_total_chapters` | `PositiveIntegerField` | No | Total canónico conocido. |
| `latest_available_chapter` | `DecimalField` | Sí | Último capítulo detectado externamente. |
| `availability_source_type` | `CharField` | No | Canonical, external o manual. |
| `availability_source_name` | `CharField` | Sí | Nombre visible de la fuente. |
| `availability_source_url` | `URLField` | Sí | URL de la serie externa. |
| `release_schedule` | `CharField` | Sí | Calendario manual o futuro. |
| `next_release_at` | `DateTimeField` | Sí | Próxima publicación conocida. |
| `external_checked_at` | `DateTimeField` | Sí | Última consulta externa. |
| `raw_data` | `JSONField` | No | Metadatos del proveedor y sus intentos. |
| `last_synced_at` | `DateTimeField` | No | Última actualización local. |

### Objetivo canónico

```text
canonical_total_chapters
o
manga.num_chapters
```

### Objetivo vigente

Cuando existe disponibilidad externa:

```text
target_chapter = latest_available_chapter
```

En caso contrario:

```text
target_chapter = canonical_total_chapters
```

### Capítulos pendientes

```text
target_chapter
-
manga.num_chapters_read
```

El resultado nunca baja de cero y admite capítulos decimales, por ejemplo `125.5`.

### Prioridad visual

La jerarquía actual favorece:

```text
0. Publicación activa con fuente viva
1. Publicación activa sin fuente viva
2. Otros casos intermedios
3. Manga finalizado
4. Rereading
```

Dentro de cada grupo se consideran actualización, cantidad pendiente y título.

---

## 9. MangaSourceLink

`MangaSourceLink` vincula un `MangaEntry` con una serie concreta de un proveedor externo.

La búsqueda se utiliza para descubrir el vínculo. Las sincronizaciones posteriores usan el `source_id` y la URL guardados; no vuelven a depender del matching por título.

### Campos principales

| Campo | Tipo | Nulo / vacío | Descripción |
|---|---|---:|---|
| `manga` | `ForeignKey` | No | Manga local asociado. |
| `provider` | `CharField` | No | Identificador del proveedor. |
| `source_id` | `CharField` | No | ID externo estable. |
| `source_title` | `CharField` | No | Título de la fuente. |
| `source_url` | `URLField` | No | URL de la serie. |
| `thumbnail_url` | `URLField` | Sí | Portada externa. |
| `match_score` | `DecimalField` | No | Puntaje de coincidencia. |
| `search_query` | `CharField` | Sí | Consulta usada al vincular. |
| `priority` | `PositiveSmallIntegerField` | No | Orden de preferencia. |
| `active` | `BooleanField` | No | Participa o no en resolución. |
| `raw_data` | `JSONField` | No | Datos adicionales. |
| `created_at` | `DateTimeField` | No | Fecha de creación. |
| `updated_at` | `DateTimeField` | No | Última modificación. |

### Restricción

Existe una sola vinculación por combinación:

```text
manga + provider
```

Guardar otra selección del mismo proveedor actualiza el vínculo existente.

### Prioridad

Un número menor tiene mayor preferencia:

```text
MANGA Plus      priority=1
Weeb Central    priority=2
```

La prioridad expresa la preferencia del usuario. El `match_score` solo expresa qué tan probable es que el candidato corresponda al manga correcto.

---

## 10. Proveedores de Chapter Signals

### MANGA Plus

Identificador interno:

```text
manga_plus
```

Uso principal:

- Fuente oficial preferida para títulos compatibles.
- Búsqueda por título, ID o URL oficial.
- Lectura de metadatos de serie y capítulos recientes.
- Detección del capítulo numéricamente más alto.

Ejemplo:

```text
https://mangaplus.shueisha.co.jp/titles/100274
```

Aunque MANGA Plus exponga una ventana limitada de capítulos recientes, es suficiente para Chapter Signals cuando el objetivo es detectar el último capítulo disponible.

### Weeb Central

Identificador interno:

```text
weeb_central
```

Uso principal:

- Búsqueda de series por título.
- Parseo de lista completa de capítulos.
- Soporte de números enteros y decimales.
- Fuente principal o fallback configurable.

### Registro común

Los clientes se registran en:

```text
mal_data/services/manga_sources/registry.py
```

El registro centraliza:

- Proveedor disponible.
- Clase cliente.
- Etiqueta visible.

Añadir un proveedor futuro requiere implementar el mismo contrato básico:

```text
search(query)
fetch_chapters(series_url)
fetch_latest_chapter(series_url)
```

---

## 11. Resolución, prioridad y fallback

La resolución vive fuera de los comandos HTTP o de consola.

Flujo normal:

```text
Obtener MangaSourceLink activos
↓
Ordenar por priority y provider
↓
Intentar fuente principal
↓
Si falla o no entrega capítulos útiles, intentar la siguiente
↓
Devolver fuente usada, capítulo e historial de intentos
```

### Sin override

```text
MANGA Plus falla
→ Weeb Central responde
→ la señal usa Weeb Central
→ raw_data registra used_fallback = true
```

### Con provider explícito

```text
--provider manga_plus
```

Solo se consulta MANGA Plus. No existe fallback implícito porque el owner pidió verificar esa fuente concreta.

### Resultado de intentos

Cada intento registra:

```text
provider
priority
status
ok
error
```

Estados posibles:

```text
success
empty
error
```

Si todas las fuentes fallan, el resolver devuelve un error agregado. Si una fuente responde sin capítulos y otra sí tiene datos, se utiliza la fuente útil.

---

## 12. Sincronización de Manga

### Sync Manga Library

Actualiza:

```text
reading
completed
on_hold
dropped
plan_to_read
```

Flujo:

```text
Descargar páginas de MAL
↓
Normalizar
↓
Cargar existentes en bloque
↓
Comparar campos relevantes
↓
Created / Updated / Unchanged
↓
Escribir solo cambios reales
```

### Sync Reading Progress

Targets:

```text
list_status = reading
OR
is_rereading = True
```

Responsabilidades:

- Consultar el estado personal vigente.
- Actualizar capítulos.
- Actualizar volúmenes.
- Actualizar score.
- Actualizar estado.
- Alinear rescates manuales.
- Crear Manga Command Logs.

### Sync Canonical Chapter Signals

Para cada manga activo:

- Crea o actualiza `MangaChapterSignal`.
- Conserva el total canónico.
- No elimina disponibilidad externa existente.
- Recalcula señales accionables.

### Sync External Chapter Signals

Targets:

```text
Reading o Rereading
+
al menos un MangaSourceLink activo
```

Para cada manga:

- Resuelve fuentes por prioridad.
- Consulta el último capítulo.
- Actualiza el mismo `MangaChapterSignal`.
- Guarda proveedor, URL, fecha, capítulo e intentos.
- Conserva `canonical_total_chapters`.
- Continúa aunque otro manga falle.

### Manga Sync Signals

El botón del dashboard ejecuta en este orden:

```text
1. Progreso personal desde MAL
2. Totales canónicos
3. Fuentes externas
4. Reordenamiento final de señales accionables
```

El resumen informa:

```text
Signals
Pending
External targets
External created
External updated
External unchanged
External empty
External errors
External fallbacks
```

---

## 13. Comandos de fuentes Manga

### Buscar candidatos

```bash
python manage.py search_manga_source MAL_ID   --provider manga_plus   --query SOURCE_ID_OR_URL
```

### Guardar un resultado

```bash
python manage.py search_manga_source MAL_ID   --provider manga_plus   --query SOURCE_ID_OR_URL   --save 1   --priority 1
```

### Inspeccionar sin modificar

```bash
python manage.py inspect_manga_source MAL_ID
```

### Inspeccionar un proveedor concreto

```bash
python manage.py inspect_manga_source MAL_ID   --provider weeb_central
```

### Sincronizar una señal externa

```bash
python manage.py sync_manga_source_signal MAL_ID
```

Los comandos son owner/developer tooling. La gestión visual de fuentes todavía no está implementada.

---

## 14. Dashboard y archivo Manga

### Manga Command Center

El dashboard incluye:

- Perfil.
- Estado de sincronización.
- Backlog Clear Ratio.
- JP Title Signal.
- Chapter Signals.
- Manga Command Logs.
- Controles owner.

### Chapter Signals

Cada señal puede mostrar:

```text
READ 102
AVAILABLE 126
PENDING +24
MANGA PLUS
PUBLISHING
```

Para mangas finalizados sin disponibilidad externa:

```text
READ 43
TOTAL 71
TO COMPLETE +28
CANONICAL TOTAL
FINISHED
```

### Archivo

Estados públicos:

```text
All
Reading
Completed
Plan to Read
On Hold
Dropped
```

Reading incluye:

```text
list_status = reading
OR
is_rereading = True
```

Filtros implementados incluyen estado de publicación y tipo de manga.

---

## 15. Modelos Anime

La mitad Anime conserva su arquitectura estable.

### AnimeEntry

Biblioteca personal local con títulos, portada, tipo, estado de emisión, progreso, score, rewatch y timestamps.

### AnimeAiringData

Señal externa de AniList con:

- Próximo episodio.
- Próxima fecha.
- Episodios emitidos estimados.
- Episodios pendientes.
- Links de streaming.
- Payload y sincronización.

### AnimeSyncEvent

Command Log con:

```text
created
status_changed
episode_changed
score_changed
```

### ManualTrackedAnime

Fallback persistente para entradas omitidas por el endpoint general de MAL.

### AnimeRelation y AnimeMetadata

Relaciones y metadatos de nodos externos usados por Relation Scan, Franchise Audit y Sequel Radar.

### SeasonalAnime

Catálogo estacional sincronizado desde AniList.

---

## 16. MALOAuthToken

`MALOAuthToken` almacena la conexión OAuth de MyAnimeList.

### Flujo

```text
Owner autenticado
↓
Connect / Renew MAL
↓
state + PKCE
↓
Autorización MAL
↓
Callback
↓
Access token + Refresh token
↓
Persistencia
```

### Renovación

```text
Token válido
→ usarlo

Token próximo a expirar
→ refresh
→ guardar credenciales nuevas
→ continuar
```

### Retry ante 401

```text
Petición MAL
↓
401 invalid_token
↓
Refresh forzado
↓
Reintento único
```

No se permite un bucle infinito.

---

## 17. Fuentes externas y local-first

### MyAnimeList

Fuente principal para:

- Estado personal.
- Progreso.
- Score.
- Rewatch / Reread.
- Biblioteca Anime.
- Biblioteca Manga.
- Detalles individuales.
- Relaciones.
- Add to Plan.

### AniList

Fuente complementaria de Anime para:

- Emisiones.
- Próximo episodio.
- Episodios emitidos.
- Streaming.
- Títulos nativos.
- Search.
- Seasonal Board.

### MANGA Plus y Weeb Central

Fuentes de disponibilidad, no de progreso personal.

```text
Proveedor externo
↓
Cliente explícito
↓
Normalización
↓
MangaSourceLink + MangaChapterSignal
↓
Dashboard local
```

Las páginas normales no dependen de una respuesta externa para renderizar.

---

## 18. Acceso y seguridad

### Acceso público

Son públicas las vistas de lectura:

- Dashboard Anime.
- Dashboard Manga.
- Archivos.
- Search.
- Seasonal.
- Relation Scan.
- Chapter Signals almacenados.

### Acceso owner

Las acciones mutables requieren normalmente:

```text
login
POST
CSRF
```

Incluyen:

- Sincronizaciones.
- Rescates.
- Relation Sync.
- Seasonal Sync.
- Add to Plan.

### OAuth

Connect y Callback usan:

- Sesión owner.
- `state`.
- PKCE.
- Redirect URL exacta.
- Credenciales privadas.
- Tokens persistidos.

### Secretos

Nunca deben versionarse:

- `.env`.
- MAL Client Secret.
- Access tokens.
- Refresh tokens.
- Database credentials.
- MANGA Plus device ID o device secret.
- Payloads privados.

---

## 19. Pruebas

Checkpoint actual:

```text
mal_data: 46 pruebas aprobadas
global: 349 pruebas aprobadas
```

Las pruebas usan:

```text
config.test_settings
SQLite en memoria
```

No modifican Supabase.

Cobertura relevante de Manga:

- Dashboard y rutas públicas.
- Acciones POST protegidas.
- Library Sync.
- Created / Updated / Unchanged.
- Reading y Rereading.
- Rescates manuales.
- Manga Command Logs.
- Señales canónicas.
- Señales externas.
- Preservación del total canónico.
- Parseo de MANGA Plus.
- Parseo de Weeb Central.
- Matching de títulos.
- Persistencia de fuentes.
- Prioridad.
- Provider override.
- Fallback automático.
- Aislamiento de errores en batch.
- Integración con Sync Signals.

---

## 20. Estado de implementación

```text
Documento: mal-insights-data-model.md
Módulo: MAL Insights
Aplicación técnica: mal_data
Migraciones documentadas: hasta mal_data.0016
Pruebas mal_data: 46 OK
Pruebas globales: 349 OK

Anime:
Estado: Funcionalmente estable
Dashboard y archivos: Implementados
OAuth: Implementado
MAL Library Sync: Implementado y optimizado
Episode Signals: Implementado
Manual Rescues: Implementado
Seasonal Board: Implementado
Relations / Franchise Audit / Sequel Radar: Implementados
Search: Implementado

Manga:
MangaEntry ampliado: Implementado
Dashboard: Implementado
Switch Anime / Manga: Implementado
Rutas públicas y archivos: Implementados
Manga Library Sync: Implementado
Reading Progress Sync: Implementado
Manga Command Logs: Implementados
Manual Manga Rescues: Implementados
Canonical Chapter Signals: Implementados
MangaSourceLink: Implementado
MANGA Plus: Implementado
Weeb Central: Implementado
Prioridad y fallback: Implementados
Batch externo desde Sync Signals: Implementado
Manga Relations: Pendiente
Anime ↔ Manga Bridge: Pendiente
Gestión owner de fuentes desde UI: Pendiente
```

---

## 21. Siguiente etapa

El bloque técnico de Chapter Signals queda cerrado.

La siguiente mejora natural es una interfaz owner para:

- Buscar fuentes por manga.
- Revisar candidatos.
- Guardar un vínculo.
- Activar o desactivar fuentes.
- Cambiar prioridades.
- Ver la última consulta y el fallback usado.

Después de esa interfaz, las extensiones de mayor valor son:

1. Manga Relations.
2. Anime ↔ Manga adaptation bridge.
3. Integración de actividad con Hibi Log.
4. Nuevos proveedores solo cuando un flujo de lectura real lo justifique.

No forman parte del bloque cerrado:

- Scraping universal.
- Soporte para cada extensión de Mihon.
- Descarga o lectura dentro de MVS Tracker.
- Sincronización permanente en background.
- Múltiples usuarios.
