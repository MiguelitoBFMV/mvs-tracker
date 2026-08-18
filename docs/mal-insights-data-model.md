# MAL Insights — Modelo de datos y arquitectura

Este documento describe el estado final implementado de **MAL Insights — Anime & Manga** dentro de MVS Tracker.

MAL Insights nació como **MAL Insight Lab** y conserva la aplicación Django técnica `mal_data`. El módulo está ahora **funcionalmente completo** para su alcance actual: biblioteca personal, sincronización, señales de Anime y Manga, rescates manuales, fuentes externas de capítulos, búsqueda, relaciones cruzadas Anime ↔ Manga y acceso público de solo lectura.

El checkpoint actual se expresa sin fijar un número de migración o de pruebas, porque ambos cambian con mantenimiento incremental:

```text
Aplicación Django técnica: mal_data
Nombre público del módulo: MAL Insights
Ruta Anime: /anime/
Ruta Manga: /manga/
Base de datos operativa: Supabase PostgreSQL
Pruebas automatizadas: SQLite en memoria
Estado de la suite de mal_data: OK
Estado de la suite global: OK
Estado funcional del módulo: COMPLETE
```

El módulo combina:

- MyAnimeList como fuente principal de la relación personal.
- AniList como fuente pública de emisión, búsqueda, descubrimiento y relaciones.
- MANGA Plus, Weeb Central, MangaFire, Mangas.in y Mangabat como fuentes explícitas de disponibilidad de capítulos.
- Persistencia local-first en PostgreSQL.
- Acceso público de solo lectura.
- Acciones privadas para el owner autenticado.
- Sincronización explícita y separada por responsabilidad.
- Dos mundos internos: Anime y Manga.
- Una frontera de lectura clara para la futura integración con Hibi Log.

---

## 1. Alcance del módulo

MAL Insights administra contenido perteneciente al ecosistema de MyAnimeList:

```text
MAL Insights
├── Anime
└── Manga
```

Anime incluye:

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
- Relaciones Anime ↔ Anime.
- Relaciones Anime → Manga / Light Novel / Novel.
- Metadatos externos.
- OAuth con renovación automática.

Manga incluye:

- Manga Command Center.
- Archivo público por estado.
- Reading y Rereading.
- Sincronización optimizada de biblioteca.
- Sincronización de progreso activo.
- Manual Manga Rescues.
- Search / Rescue mediante AniList.
- Manga Command Logs.
- Señales canónicas de finalización.
- Chapter Signals con disponibilidad externa.
- Fuentes persistentes por manga.
- Source Management.
- Source Coverage.
- Prioridad configurable y fallback automático.
- Cinco proveedores de capítulos.
- Manga Relations.
- Relaciones Manga → Anime.
- Relaciones Manga ↔ Manga / Novel.

Watchroom administra series, películas, cartoons, documentales y live action fuera del ecosistema anime. Game Kiroku administra videojuegos. Estos dominios no se mezclan dentro de MAL Insights.

---

## 2. Principios de arquitectura

MAL Insights sigue estas reglas:

- MyAnimeList es la fuente principal del estado, progreso, score y rewatch / reread personal.
- El MAL ID es la identidad canónica usada para conectar datos de distintas fuentes.
- AniList complementa el módulo; no reemplaza la biblioteca personal.
- AniList descubre relaciones de Anime y Manga.
- Los proveedores externos de Manga aportan disponibilidad de capítulos, no progreso personal.
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
- Hibi Log consumirá datos de MAL Insights sin que `mal_data` dependa de Hibi Log.

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

El encabezado compartido muestra:

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
    ├── target AnimeEntry
    ├── target AnimeMetadata
    └── target MangaEntry

ManualTrackedAnime
└── reconstruye o actualiza AnimeEntry

SeasonalAnime

MangaEntry
├── MangaSyncEvent
├── MangaChapterSignal
├── MangaSourceLink [0..n]
└── MangaRelation
    ├── target MangaEntry
    ├── target AnimeEntry
    └── target AnimeMetadata

ManualTrackedManga
└── reconstruye o actualiza MangaEntry
```

La biblioteca personal y las relaciones son conceptos distintos:

```text
AnimeEntry / MangaEntry
    estado personal

AnimeRelation / MangaRelation
    grafo de conexiones

AnimeMetadata
    fallback para nodos Anime no presentes en la biblioteca local
```

---

## 5. MangaEntry

`MangaEntry` representa una entrada personal de Manga importada o reconstruida desde MyAnimeList.

### Campos principales

| Campo | Tipo | Nulo / vacío | Descripción |
|---|---|---:|---|
| `mal_id` | `PositiveIntegerField` | No | Identificador único de MAL. |
| `title` | `CharField` | No | Título principal. |
| `title_japanese` | `CharField` | Sí | Título japonés. |
| `title_english` | `CharField` | Sí | Título inglés. |
| `main_picture_url` | `URLField` | Sí | Portada principal. |
| `media_type` | `CharField` | Sí | Manga, light novel, novel, one-shot u otro tipo MAL. |
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

### Semántica

Un evento registra que el valor local cambió durante una sincronización:

```text
CH_UPDATE
Seihantai na Kimi to Boku [CH. 42 → CH. 43]
```

El timestamp de `MangaSyncEvent` es la hora del cambio detectado por el sistema. **No debe interpretarse como la hora exacta en que el usuario leyó el capítulo.**

Esta distinción es importante para la futura integración con Hibi Log.

---

## 7. ManualTrackedManga y Search / Rescue

`ManualTrackedManga` protege entradas que existen en la lista real del usuario, pero que el endpoint general de lista de MAL puede omitir.

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

### Flujo de rescate

```text
La lista general de MAL omite el manga
↓
Search / Rescue busca candidatos en AniList
↓
El candidato aporta AniList ID + MAL ID
↓
Rescue / Track crea o actualiza ManualTrackedManga
↓
El detalle individual de MAL intenta recuperar el estado personal real
↓
MangaEntry se reconstruye o actualiza
↓
ManualTrackedManga permanece como safety net
```

`ManualTrackedManga` no crea una segunda biblioteca.

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

### Objetivo vigente con fuente externa

El valor externo se conserva como `Decimal`.

Ejemplo:

```text
latest_available_chapter = 9.50
```

Sin embargo, el progreso personal de MAL usa capítulos enteros. Por eso el objetivo consumible por Chapter Signals se normaliza hacia abajo:

```text
9.50 external
→ target_chapter = 9
```

Ejemplo:

```text
READ 2
AVAILABLE 9
PENDING +7
```

El valor decimal original permanece disponible en los datos de la fuente.

### Capítulos pendientes

```text
max(
    target_chapter - manga.num_chapters_read,
    0
)
```

### Prioridad visual

Las señales de manga actualmente en publicación y con capítulos pendientes tienen prioridad sobre backlog finalizado.

Cuando existe `published_at` válido del proveedor, las señales vivas más recientes se muestran primero. Fechas externas inválidas no deben romper el orden.

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
| `is_official` | `BooleanField` | No | Marca una fuente oficial como MANGA Plus. |
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
priority=1   Primary
priority=2   Fallback
priority=3   siguiente fallback
```

La prioridad expresa preferencia de resolución. `match_score` expresa confianza de matching.

---

## 10. Proveedores de Chapter Signals

El registro actual incluye cinco proveedores:

```text
manga_plus
weeb_central
manga_fire
mangas_in
mangabat
```

### MANGA Plus

Uso principal:

- Fuente oficial preferida para títulos compatibles.
- Búsqueda por título, ID o URL oficial.
- Lectura de metadatos recientes.
- Detección del capítulo numéricamente más alto.
- `is_official = True`.

### Weeb Central

Uso principal:

- Búsqueda por título.
- Parseo de capítulos.
- Soporte de capítulos enteros y decimales.
- Fuente principal o fallback.

### MangaFire

Uso principal:

- Búsqueda de candidatos.
- Consulta de capítulos.
- Soporte del mecanismo VRF requerido por sus endpoints.

Limitación conocida:

```text
Cloudflare / HTTP 403
```

Puede bloquear solicitudes válidas, por lo que debe considerarse un proveedor frágil y convivir con fallbacks.

### Mangas.in

Uso principal:

- Búsqueda y resolución por slug.
- Compatibilidad con el host actual `m440.in`.
- Compatibilidad con URLs históricas `mangas.in`.
- Detección del último capítulo desde el resumen de la serie.

### Mangabat

Uso principal:

- Búsqueda por título.
- Slug persistente.
- Endpoint de capítulos.
- Detección del último capítulo y timestamp cuando existe.

### Contrato común

Los proveedores se normalizan alrededor de operaciones equivalentes a:

```text
search(query)
fetch_latest_chapter(series_url)
```

El resolver no necesita conocer los detalles internos del proveedor.

---

## 11. Resolución, prioridad y fallback

Flujo normal:

```text
Obtener MangaSourceLink activos
↓
Ordenar por priority y provider
↓
Intentar Primary
↓
Si falla o queda vacío, intentar Fallback
↓
Continuar hasta obtener un capítulo útil
↓
Devolver fuente usada + capítulo + historial de intentos
```

### Sin override

```text
MANGA Plus falla
→ Mangabat responde
→ la señal usa Mangabat
→ raw_data registra fallback
```

### Con provider explícito

```text
--provider manga_plus
```

Solo se consulta ese proveedor. No existe fallback implícito porque el owner pidió verificar una fuente concreta.

### Resultado de intentos

Cada intento registra información equivalente a:

```text
provider
priority
status
ok
error
```

Estados:

```text
success
empty
error
```

---

## 12. Source Management y Source Coverage

### Source Management

Ruta conceptual:

```text
/manga/<mal_id>/sources/
```

La interfaz owner permite:

- Buscar candidatos en un proveedor.
- Revisar score, título, URL y portada.
- Guardar como Primary.
- Guardar como Fallback.
- Promover un fallback a Primary.
- Activar o desactivar.
- Desvincular.
- Ejecutar `Sync Now`.

La gestión de fuentes ya no depende de Django Admin.

### Source Coverage

Ruta:

```text
/manga/sources/coverage/
```

Su alcance técnico es deliberadamente acotado:

```text
Reading
+
currently_publishing
```

Clasifica mangas en estados como:

```text
Needs Setup
Disabled
Single Source
Ready
```

No representa prioridad personal de lectura. Su pregunta es únicamente:

```text
¿Este Chapter Signal tiene cobertura externa utilizable y suficiente?
```

---

## 13. Sincronización de Manga

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

El botón ejecuta:

```text
1. Progreso personal desde MAL
2. Totales canónicos
3. Fuentes externas
4. Reordenamiento final de señales accionables
```

---

## 14. Manga Relations

`MangaRelation` representa una relación descubierta desde AniList para un `MangaEntry` local.

Puede apuntar a:

```text
Manga
Light Novel
Novel
One-shot
Anime
```

### Campos conceptuales principales

```text
source_manga
source_mal_id
source_title

target_mal_id
target_title
target_media_type
target_status
target_picture_url

target_num_episodes
target_num_chapters
target_num_volumes

relation_type
relation_type_formatted
relation_source_type   # anime | manga

target_local_list_status
raw_data
last_synced_at
```

La unicidad se define por la combinación:

```text
source_mal_id
+
target_mal_id
+
relation_source_type
+
relation_type
```

### Resolución de target local

Si el target es Anime:

```text
AnimeEntry
→ AnimeMetadata fallback
```

Si el target es Manga:

```text
MangaEntry
```

### Propiedades de presentación

`MangaRelation` expone una capa uniforme:

```text
target_display_title
target_display_picture_url
target_display_status
target_display_media_type
target_display_progress
target_display_score
has_local_target
```

Ejemplo Manga → Anime local:

```text
ADAPTATION
LOCAL NODE
TV
COMPLETED
13/13
SCORE 10
```

Ejemplo Manga → Manga externo:

```text
SIDE STORY
NOT LOCAL
MANGA
-/15
SEARCH / RESCUE
```

### Sincronización

```text
Manga MAL ID
↓
AniList Media(type=MANGA, idMal=...)
↓
relations.edges
↓
separar Anime / Manga
↓
normalizar
↓
guardar / actualizar
↓
eliminar relaciones obsoletas
```

Nodos sin MAL ID se omiten porque no existe una identidad canónica segura para integrarlos con la biblioteca local.

---

## 15. Modelos Anime

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

Command Log:

```text
created
status_changed
episode_changed
score_changed
```

Igual que `MangaSyncEvent`, su timestamp registra cuándo el sistema detectó el cambio, no necesariamente cuándo ocurrió la actividad real.

### ManualTrackedAnime

Fallback persistente para entradas omitidas por el endpoint general de MAL.

### SeasonalAnime

Catálogo estacional sincronizado desde AniList.

---

## 16. AnimeRelation y paridad Anime → Manga

`AnimeRelation` conserva las relaciones Anime ↔ Anime y ahora también resuelve correctamente targets Manga / Light Novel / Novel.

### Relation source type

```text
anime
manga
```

### Target Anime

Puede resolverse contra:

```text
AnimeEntry
o
AnimeMetadata
```

### Target Manga

Puede resolverse contra:

```text
MangaEntry
```

### Datos externos persistidos

Además de título, portada, status y tipo, la relación puede conservar totales externos:

```text
target_num_episodes
target_num_chapters
target_num_volumes
```

Eso permite mostrar progreso aproximado de un nodo externo:

```text
NOT LOCAL
LIGHT NOVEL
-/14
```

### Target local

Cuando existe `MangaEntry`, la UI usa la información personal real:

```text
LOCAL NODE
READING
51/TBD
SCORE 10
```

y ofrece navegación a:

```text
Scan Manga Node
Sources
Open MAL
```

Cuando no existe localmente:

```text
Search / Rescue
Open MAL
```

### Descubrimiento

Anime Relations también usa AniList:

```text
Anime MAL ID
↓
AniList Media(type=ANIME, idMal=...)
↓
relations.edges
↓
Anime targets + Manga targets
↓
normalización
↓
persistencia local
↓
prune de relaciones obsoletas
```

### Franchise Audit

Franchise Audit sigue deliberadamente centrado en las relaciones Anime. Manga / Novels no se incorporan al audit audiovisual.

---

## 17. Relación bidireccional Anime ↔ Manga

La arquitectura final permite navegar en ambas direcciones.

Ejemplo:

```text
Kaoru Hana Anime
MAL 59845
COMPLETED 13/13
        ↓
ADAPTATION
        ↓
Kaoru Hana Manga
MAL 144267
READING 51/TBD
        ↓
ADAPTATION
        ↓
Kaoru Hana Anime
```

Principios:

- AniList descubre la conexión.
- MAL ID ancla la identidad.
- `AnimeEntry` y `MangaEntry` aportan el estado personal.
- Las vistas nunca necesitan duplicar el progreso personal dentro de la relación.
- Una resincronización actualiza relaciones existentes y elimina edges obsoletos.
- La navegación está disponible desde los archivos completos, no solo desde Episode Signals o Chapter Signals.

---

## 18. MALOAuthToken

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

## 19. Fuentes externas y local-first

### MyAnimeList

Fuente principal para:

- Estado personal.
- Progreso.
- Score.
- Rewatch / Reread.
- Biblioteca Anime.
- Biblioteca Manga.
- Detalles individuales.
- Add to Plan.
- MAL ID canónico.

### AniList

Fuente pública para:

- Emisiones.
- Próximo episodio.
- Episodios emitidos.
- Streaming.
- Títulos nativos.
- Search / Rescue.
- Seasonal Board.
- Relaciones Anime.
- Relaciones Manga.

### Proveedores Manga

```text
MANGA Plus
Weeb Central
MangaFire
Mangas.in
Mangabat
```

Aportan disponibilidad de capítulos.

```text
Proveedor
↓
cliente específico
↓
normalización
↓
MangaSourceLink
↓
MangaChapterSignal
↓
dashboard local
```

Las páginas normales no dependen de una respuesta externa para renderizar.

---

## 20. Acceso y seguridad

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
- Source Management.
- Source Coverage owner tooling.

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

## 21. Pruebas

Las pruebas usan:

```text
config.test_settings
SQLite en memoria
```

Nunca modifican Supabase.

El checkpoint final del módulo tiene verdes tanto la suite de `mal_data` como la suite global.

La cobertura relevante incluye:

### Anime

- Rutas públicas y protegidas.
- OAuth.
- Renovación de tokens.
- Retry ante MAL 401.
- Library Sync.
- Episode Signals.
- Manual Rescues.
- Search.
- Seasonal.
- Relations.
- AniList relation sync.
- Anime → Manga / Novel local y externo.
- Progress / score / status local en relation nodes.
- Vistas de relaciones.

### Manga

- Dashboard y archivos.
- Library Sync.
- Reading y Rereading.
- Manual Rescues.
- Search / Rescue.
- Command Logs.
- Chapter Signals canónicos.
- Chapter Signals externos.
- Capítulos decimales.
- Orden por `published_at`.
- Los cinco proveedores.
- Matching.
- Persistencia de fuentes.
- Source Management.
- Source Coverage.
- Prioridad.
- Provider override.
- Fallback automático.
- Error isolation.
- Manga Relations.
- Manga → Anime.
- Manga → Manga.
- Vistas públicas de relations.

---

## 22. Frontera MAL Insights → Hibi Log

MAL Insights queda cerrado sin implementar Hibi Log dentro de `mal_data`.

La relación futura es de consumo:

```text
MAL INSIGHTS
    │
    │ datos locales read-only
    ▼
HIBI LOG
```

### MAL Insights es dueño de

```text
AnimeEntry / MangaEntry
MAL ID
títulos
portadas
estado personal
progreso
score
Episode Signals
Chapter Signals
fechas de emisión/publicación disponibles
AnimeSyncEvent / MangaSyncEvent
```

Una identidad transversal suficiente puede expresarse como:

```text
anime:<mal_id>
manga:<mal_id>
```

### Hibi Log será dueño de

```text
fecha real de actividad
hora real de actividad
duración
sesión
agrupación diaria
activity calendar
content calendar
notas de sesión
analytics temporales
```

### Regla crítica

```text
AnimeSyncEvent.created_at
MangaSyncEvent.created_at
```

indican cuándo MAL Insights **detectó** un cambio.

No demuestran:

```text
"el episodio se vio exactamente a esa hora"
"el capítulo se leyó exactamente a esa hora"
```

Por eso Hibi Log no debe inferir cronología real a partir de timestamps de sincronización.

### Dependencias prohibidas dentro de MAL Insights

No se añaden:

- Foreign keys hacia Hibi Log.
- Modelos de sesiones Hibi.
- Calendarios Hibi.
- Escrituras de Hibi desde `mal_data`.
- Lógica de agregación diaria Hibi.

El contrato final queda:

> MAL Insights proporciona identidad, biblioteca, estado, progreso y señales de contenido. Hibi Log consume esos datos y es dueño de la cronología real.

---

## 23. Estado final de implementación

```text
Documento: mal-insights-data-model.md
Módulo: MAL Insights
Aplicación técnica: mal_data
Estado: FUNCTIONALLY COMPLETE

Anime:
Dashboard y archivos: Implementados
OAuth: Implementado
MAL Library Sync: Implementado y optimizado
Episode Signals: Implementado
Manual Rescues: Implementado
Search / Rescue: Implementado
Seasonal Board: Implementado
Relations Anime ↔ Anime: Implementadas
Relations Anime → Manga / LN / Novel: Implementadas
Relation discovery via AniList: Implementado
Franchise Audit: Implementado
Sequel Radar: Implementado

Manga:
MangaEntry: Implementado
Dashboard: Implementado
Switch Anime / Manga: Implementado
Rutas públicas y archivos: Implementados
Manga Library Sync: Implementado
Reading Progress Sync: Implementado
Manga Command Logs: Implementados
Manual Manga Rescues: Implementados
Search / Rescue via AniList: Implementado
Canonical Chapter Signals: Implementados
External Chapter Signals: Implementados
MangaSourceLink: Implementado
MANGA Plus: Implementado
Weeb Central: Implementado
MangaFire: Implementado
Mangas.in: Implementado
Mangabat: Implementado
Prioridad y fallback: Implementados
Source Management: Implementado
Source Coverage: Implementado
Manga Relations: Implementadas
Manga → Anime Bridge: Implementado
Manga ↔ Manga / Novel: Implementado

Cross-world:
Anime ↔ Manga navigation: Implementada
MAL ID canonical identity: Implementada
AniList relation discovery: Implementada
Local progress enrichment: Implementado

Hibi Log:
Contrato de frontera: Definido
Implementación dentro de mal_data: No corresponde
```

---

## 24. Trabajo futuro

MAL Insights no tiene otro bloque funcional obligatorio pendiente.

Las extensiones futuras son reactivas a necesidades reales:

1. Añadir nuevos proveedores solo cuando una lectura real lo requiera.
2. Detectar automáticamente cuándo un rescate manual vuelve a aparecer en el endpoint normal de MAL.
3. Mejorar casos sin MAL ID confirmado.
4. Ajustar proveedores cuando cambien sus endpoints o medidas anti-bot.
5. Incorporar nuevos análisis solo si el uso cotidiano del módulo revela valor real.

No forman parte del alcance actual:

- Scraping universal.
- Soporte para cada extensión de Mihon.
- Descarga o lectura dentro de MVS Tracker.
- Sincronización permanente en background.
- Múltiples usuarios.
- Construcción de Hibi Log dentro de MAL Insights.
