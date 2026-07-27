# MAL Insights — Modelo de datos y arquitectura

Este documento describe el estado implementado y la dirección aprobada de **MAL Insights — Anime & Manga** dentro de MVS Tracker.

MAL Insights es el módulo más antiguo de la plataforma y nació originalmente como **MAL Insight Lab**. Su lado de Anime se encuentra funcionalmente estable; el siguiente arco corresponde a completar la mitad de Manga sin romper ni mezclar los flujos ya consolidados.

El estado documentado corresponde al repositorio actual con:

```text
Aplicación Django técnica: mal_data
Nombre público del módulo: MAL Insights
Ruta Anime actual: /anime/
Migración actual: mal_data.0010_maloauthtoken
Base de datos operativa: Supabase PostgreSQL
Pruebas globales del proyecto: 242 OK
```

El módulo combina:

- MyAnimeList como fuente principal de la biblioteca personal.
- AniList como fuente de metadatos públicos, emisiones y descubrimiento.
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
Anime
Manga
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

Manga dispone actualmente de una base de datos inicial mediante `MangaEntry`, pero aún no tiene su mundo público completo, rutas, dashboard, archivos por estado ni señales de lectura.

Watchroom administra series, películas, cartoons, documentales y live action fuera del ecosistema anime. Game Kiroku administra videojuegos. Estos dominios no deben mezclarse dentro de MAL Insights.

---

## 2. Principios de arquitectura

MAL Insights sigue estos principios:

- MyAnimeList es la fuente principal de la relación personal con anime y manga.
- AniList es una fuente complementaria, no la biblioteca personal.
- Los datos sincronizados se almacenan localmente en PostgreSQL.
- Las páginas normales cargan desde la base local.
- Una vista GET normal no debe producir sincronizaciones ni escrituras ocultas.
- Las sincronizaciones se ejecutan mediante acciones explícitas del owner.
- Los procesos pesados se dividen por responsabilidad.
- El módulo trabaja con una única biblioteca personal.
- Los modelos no se relacionan con `User`.
- La autenticación decide quién puede escribir.
- El acceso público es de solo lectura.
- Las acciones mutables requieren normalmente login, POST y CSRF.
- OAuth utiliza rutas autenticadas, `state` y PKCE.
- Anime y Manga comparten identidad de módulo, OAuth y cliente MAL.
- Anime y Manga conservan dashboards, navegación y señales propias.
- Hibi Log consumirá actividad derivada de ambos mundos en una etapa posterior.

---

## 3. Dos mundos dentro de MAL Insights

La arquitectura aprobada mantiene Anime y Manga dentro de la misma aplicación Django técnica:

```text
mal_data
```

No se creará una app Django separada para manga.

La experiencia pública se dividirá en dos mundos:

```text
MAL Insights
├── Anime
└── Manga
```

### Mundo Anime

Ruta principal actual:

```text
/anime/
```

Navegación actual:

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

### Mundo Manga

Ruta principal aprobada:

```text
/manga/
```

Navegación prevista:

```text
Dashboard
All
Reading
On Hold
Plan to Read
Completed
Dropped
Search
```

`Rereading` formará parte de Reading, de la misma manera que Rewatching forma parte de Watching.

### Switch Anime / Manga

El encabezado compartido mostrará un selector de mundo:

```text
MAL INSIGHTS                     [ ANIME | MANGA ]
```

El switch no será un filtro menor dentro de una misma página.

Al cambiar de mundo:

- Cambia la ruta principal.
- Cambia la navegación secundaria.
- Cambia el dashboard.
- Cambian las señales.
- Cambian las métricas.
- Se mantiene la identidad visual de MAL Insights.
- Se mantiene el acceso a la plataforma MVS Tracker.
- Se comparte la sesión del owner y la conexión OAuth con MAL.

---

## 4. Modelo conceptual actual

```text
MALOAuthToken

MangaEntry

AnimeEntry
├── AnimeAiringData
├── AnimeSyncEvent
└── AnimeRelation
    └── AnimeMetadata como fallback externo

ManualTrackedAnime
└── reconstruye o actualiza AnimeEntry

SeasonalAnime
```

### Responsabilidad de cada entidad

```text
MALOAuthToken
    Almacena access token, refresh token y expiración de MAL.

MangaEntry
    Almacena la biblioteca personal básica de manga.

AnimeEntry
    Almacena la biblioteca personal local de anime.

AnimeAiringData
    Almacena señales de emisión y streaming desde AniList.

AnimeSyncEvent
    Registra cambios relevantes de estado, episodio y score.

AnimeRelation
    Almacena relaciones descubiertas desde un anime fuente.

ManualTrackedAnime
    Mantiene excepciones que el endpoint normal de la lista MAL omite.

AnimeMetadata
    Almacena metadatos de anime externos que no están en la biblioteca local.

SeasonalAnime
    Almacena el catálogo estacional sincronizado desde AniList.
```

---

## 5. MangaEntry

`MangaEntry` representa una entrada personal de manga importada desde MyAnimeList.

El modelo ya existe en la base actual, pero todavía no tiene un mundo web completo.

### Campos implementados

| Campo | Tipo | Nulo / vacío | Descripción |
|---|---|---:|---|
| `mal_id` | `PositiveIntegerField` | No | Identificador único de MAL. |
| `title` | `CharField` | No | Título principal. |
| `main_picture_url` | `URLField` | Sí | Portada principal. |
| `media_type` | `CharField` | Sí | Tipo de publicación de MAL. |
| `publication_status` | `CharField` | Sí | Estado editorial o de publicación. |
| `num_volumes` | `PositiveIntegerField` | No | Total conocido de volúmenes. |
| `num_chapters` | `PositiveIntegerField` | No | Total conocido de capítulos. |
| `start_date` | `DateField` | Sí | Fecha de inicio. |
| `end_date` | `DateField` | Sí | Fecha de término. |
| `list_status` | `CharField` | No | Estado personal en MAL. |
| `score` | `PositiveIntegerField` | No | Score personal. |
| `num_volumes_read` | `PositiveIntegerField` | No | Volúmenes leídos. |
| `num_chapters_read` | `PositiveIntegerField` | No | Capítulos leídos. |
| `is_rereading` | `BooleanField` | No | Indica relectura activa. |
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

No necesita convertirse en un estado incompatible con la historia personal almacenada por MAL.

### Orden actual

```text
updated_at_mal descendente
title ascendente
```

### Limitaciones actuales

- No guarda todavía `title_japanese`.
- No guarda todavía `title_english`.
- No tiene Command Logs propios.
- No tiene rescates manuales propios.
- No tiene relaciones con manga como nodo fuente.
- No tiene rutas públicas.
- No tiene dashboard.
- No tiene archivos por estado.
- No tiene Chapter Signals.

Estas limitaciones deben resolverse durante el arco Manga.

---

## 6. AnimeEntry

`AnimeEntry` representa la entrada personal local de un anime de MyAnimeList.

### Campos implementados

| Campo | Tipo | Nulo / vacío | Descripción |
|---|---|---:|---|
| `mal_id` | `PositiveIntegerField` | No | Identificador único de MAL. |
| `title` | `CharField` | No | Título principal. |
| `title_japanese` | `CharField` | Sí | Título japonés. |
| `title_english` | `CharField` | Sí | Título inglés. |
| `main_picture_url` | `URLField` | Sí | Portada principal. |
| `media_type` | `CharField` | Sí | TV, Movie, OVA, Special u otro tipo MAL. |
| `airing_status` | `CharField` | Sí | Estado de emisión. |
| `num_episodes` | `PositiveIntegerField` | No | Total conocido de episodios. |
| `start_date` | `DateField` | Sí | Fecha de inicio. |
| `end_date` | `DateField` | Sí | Fecha de término. |
| `list_status` | `CharField` | No | Estado personal en MAL. |
| `score` | `PositiveIntegerField` | No | Score personal. |
| `num_episodes_watched` | `PositiveIntegerField` | No | Episodios vistos. |
| `is_rewatching` | `BooleanField` | No | Rewatch activo. |
| `updated_at_mal` | `DateTimeField` | Sí | Última actualización conocida en MAL. |
| `raw_data` | `JSONField` | Sí | Payload original almacenado. |
| `last_synced_at` | `DateTimeField` | No | Última sincronización local. |

### Estados personales

```text
watching
completed
on_hold
dropped
plan_to_watch
```

`Rewatching` se deriva de:

```text
is_rewatching = True
```

### Título visible

Cuando existe título japonés:

```text
Título principal (日本語タイトル)
```

En caso contrario se usa el título principal.

### Orden

```text
updated_at_mal descendente
title ascendente
```

---

## 7. AnimeAiringData

`AnimeAiringData` almacena las señales externas de emisión obtenidas desde AniList para una entrada local de anime.

Cada `AnimeEntry` puede tener como máximo un registro asociado.

### Campos implementados

| Campo | Tipo | Nulo / vacío | Descripción |
|---|---|---:|---|
| `anime` | `OneToOneField` | No | Entrada local asociada. |
| `mal_id` | `PositiveIntegerField` | No | MAL ID único. |
| `anilist_id` | `PositiveIntegerField` | Sí | ID correspondiente en AniList. |
| `title_romaji` | `CharField` | Sí | Título romaji. |
| `title_english` | `CharField` | Sí | Título inglés. |
| `title_native` | `CharField` | Sí | Título nativo. |
| `anilist_status` | `CharField` | Sí | Estado en AniList. |
| `anilist_episodes` | `PositiveIntegerField` | No | Total de episodios reportado. |
| `next_airing_episode` | `PositiveIntegerField` | Sí | Próximo episodio. |
| `next_airing_at` | `DateTimeField` | Sí | Fecha y hora del próximo episodio. |
| `time_until_airing_seconds` | `PositiveIntegerField` | Sí | Tiempo restante informado. |
| `episodes_aired_estimated` | `PositiveIntegerField` | No | Episodios estimados como emitidos. |
| `streaming_links` | `JSONField` | No | Enlaces externos relevantes. |
| `streaming_episodes` | `JSONField` | No | Episodios y enlaces detectados. |
| `raw_data` | `JSONField` | Sí | Payload original almacenado. |
| `last_synced_at` | `DateTimeField` | No | Última actualización. |

### Episodios pendientes

```text
episodes_aired_estimated
-
anime.num_episodes_watched
```

El resultado nunca baja de cero.

### Episode Signal

Existe una señal cuando:

```text
pending_episodes_for_user > 0
```

---

## 8. AnimeSyncEvent

`AnimeSyncEvent` implementa el Command Log de Anime.

### Tipos implementados

```text
created
status_changed
episode_changed
score_changed
```

### Campos

| Campo | Tipo | Nulo / vacío | Descripción |
|---|---|---:|---|
| `anime` | `ForeignKey` | Sí | Entrada relacionada. |
| `mal_id` | `PositiveIntegerField` | No | Snapshot del MAL ID. |
| `title_snapshot` | `CharField` | No | Título al momento del evento. |
| `event_type` | `CharField` | No | Tipo de cambio. |
| `old_value` | `CharField` | Sí | Valor anterior. |
| `new_value` | `CharField` | Sí | Valor nuevo. |
| `created_at` | `DateTimeField` | No | Fecha del evento. |

### Uso

Se generan eventos cuando la sincronización detecta cambios relevantes.

Ejemplos:

```text
EP_UPDATE
Kore Kaite Shine [EP. 2 → EP. 3]

STATUS_UPDATE
Anime X [Watching → Completed]

SCORE_UPDATE
Anime Y [7 → 8]
```

La futura mitad Manga deberá añadir una entidad equivalente, por ejemplo `MangaSyncEvent`, con eventos de capítulos y volúmenes.

---

## 9. ManualTrackedAnime

`ManualTrackedAnime` protege entradas que existen en la lista real del usuario, pero que el endpoint general de lista de MAL omite.

### Campos

| Campo | Tipo | Nulo / vacío | Descripción |
|---|---|---:|---|
| `mal_id` | `PositiveIntegerField` | No | MAL ID único. |
| `title_snapshot` | `CharField` | Sí | Título visible de respaldo. |
| `status` | `CharField` | No | Estado personal fallback. |
| `episodes_watched` | `PositiveIntegerField` | No | Episodios vistos fallback. |
| `score` | `PositiveIntegerField` | No | Score fallback. |
| `is_rewatching` | `BooleanField` | No | Rewatch fallback. |
| `active` | `BooleanField` | No | Activa o desactiva el rescate. |
| `notes` | `TextField` | Sí | Contexto manual. |
| `created_at` | `DateTimeField` | No | Fecha de creación. |
| `updated_at` | `DateTimeField` | No | Última actualización. |

### Estados permitidos

```text
watching
completed
on_hold
dropped
plan_to_watch
```

### Semántica

`ManualTrackedAnime` no reemplaza a MAL como fuente personal principal.

El flujo correcto es:

```text
El endpoint general omite el anime
↓
ManualTrackedAnime recuerda la excepción
↓
El detalle individual de MAL entrega el estado real cuando es posible
↓
AnimeEntry se reconstruye o actualiza
↓
El tracker manual se mantiene alineado como fallback
```

### Rescate inicial

```bash
python manage.py rescue_anime_entry MAL_ID   --status watching   --episodes-watched 1   --sync-airing
```

Después del rescate, Sync Signals puede actualizar normalmente su progreso cotidiano.

---

## 10. AnimeRelation

`AnimeRelation` almacena relaciones descubiertas desde un anime fuente.

### Campos principales

| Campo | Tipo | Nulo / vacío | Descripción |
|---|---|---:|---|
| `source_anime` | `ForeignKey` | Sí | Anime local fuente cuando existe. |
| `source_mal_id` | `PositiveIntegerField` | No | MAL ID del nodo fuente. |
| `source_title` | `CharField` | No | Título fuente. |
| `target_mal_id` | `PositiveIntegerField` | No | MAL ID del objetivo. |
| `target_title` | `CharField` | No | Título del objetivo. |
| `target_media_type` | `CharField` | Sí | Tipo de medio objetivo. |
| `target_status` | `CharField` | Sí | Estado externo objetivo. |
| `target_picture_url` | `URLField` | Sí | Imagen objetivo. |
| `relation_type` | `CharField` | No | Tipo original de relación. |
| `relation_type_formatted` | `CharField` | Sí | Etiqueta formateada. |
| `relation_source_type` | `CharField` | No | Anime o manga. |
| `target_local_list_status` | `CharField` | Sí | Snapshot del estado local. |
| `raw_data` | `JSONField` | Sí | Payload original. |
| `last_synced_at` | `DateTimeField` | No | Último escaneo. |

### Restricción de unicidad

```text
source_mal_id
target_mal_id
relation_source_type
relation_type
```

### Funciones derivadas

El modelo puede resolver para objetivos anime:

- Entrada local.
- Metadatos externos.
- Estado visible.
- Tipo de medio.
- Estado de emisión.
- Progreso.
- Score.
- Título.
- Imagen.
- Si el nodo depende solo de metadata externa.

### Limitación actual

El modelo está orientado a un `AnimeEntry` como fuente.

Aunque puede almacenar objetivos anime o manga, todavía no permite que un manga local sea el nodo central con su propio flujo completo de relaciones.

La mitad Manga deberá resolverlo sin romper la arquitectura estable de Anime.

La opción aprobada más segura es añadir una entidad específica:

```text
MangaRelation
```

en lugar de convertir inmediatamente `AnimeRelation` en un modelo genérico con una migración más riesgosa.

---

## 11. AnimeMetadata

`AnimeMetadata` almacena información de anime que no pertenece a la biblioteca local, pero que es necesaria para Search, relaciones y Franchise Audit.

### Campos

| Campo | Tipo | Nulo / vacío | Descripción |
|---|---|---:|---|
| `mal_id` | `PositiveIntegerField` | No | MAL ID único. |
| `title` | `CharField` | No | Título principal. |
| `title_japanese` | `CharField` | Sí | Título japonés. |
| `title_english` | `CharField` | Sí | Título inglés. |
| `main_picture_url` | `URLField` | Sí | Portada. |
| `media_type` | `CharField` | Sí | Tipo de medio. |
| `airing_status` | `CharField` | Sí | Estado de emisión. |
| `num_episodes` | `PositiveIntegerField` | No | Episodios conocidos. |
| `start_date` | `DateField` | Sí | Fecha de inicio. |
| `end_date` | `DateField` | Sí | Fecha de término. |
| `raw_data` | `JSONField` | No | Payload almacenado. |
| `last_synced_at` | `DateTimeField` | Sí | Última sincronización. |

### Uso

Permite que una relación hacia un anime externo muestre:

- Título.
- Portada.
- Tipo.
- Estado.
- Episodios.

sin convertirlo en una entrada falsa de la biblioteca personal.

---

## 12. SeasonalAnime

`SeasonalAnime` almacena el catálogo de temporada importado desde AniList.

### Campos

| Campo | Tipo | Nulo / vacío | Descripción |
|---|---|---:|---|
| `anilist_id` | `PositiveIntegerField` | No | ID único de AniList. |
| `mal_id` | `PositiveIntegerField` | Sí | Mapping a MAL cuando existe. |
| `title_romaji` | `CharField` | No | Título romaji. |
| `title_english` | `CharField` | Sí | Título inglés. |
| `title_native` | `CharField` | Sí | Título nativo. |
| `cover_image_url` | `URLField` | Sí | Portada. |
| `season` | `CharField` | No | Winter, Spring, Summer, Fall o TBA. |
| `season_year` | `PositiveIntegerField` | No | Año del bucket. |
| `format` | `CharField` | Sí | Formato. |
| `status` | `CharField` | Sí | Estado de publicación. |
| `episodes` | `PositiveIntegerField` | No | Episodios conocidos. |
| `next_airing_episode` | `PositiveIntegerField` | Sí | Próximo episodio. |
| `next_airing_at` | `DateTimeField` | Sí | Próxima emisión. |
| `genres` | `JSONField` | No | Géneros. |
| `studios` | `JSONField` | No | Estudios. |
| `external_links` | `JSONField` | No | Enlaces externos. |
| `raw_data` | `JSONField` | No | Payload almacenado. |
| `last_synced_at` | `DateTimeField` | No | Último sync. |

### Funciones actuales

- Consultar temporada y año.
- Consultar `ALL` para un año.
- Ordenar por countdown o título.
- Filtrar por formato.
- Comparar contra la biblioteca local.
- Añadir a Plan to Watch.
- Mantener un bucket TBA provisional.
- Sincronizar temporadas explícitamente.

### Regla defensiva de Add to Plan

Antes de modificar MAL:

```text
Consultar el estado real en MAL
```

Si la entrada ya existe:

```text
Sincronizar localmente
No sobrescribirla como Plan to Watch
```

Si no existe:

```text
Agregar a Plan to Watch
Sincronizar la entrada local
```

---

## 13. MALOAuthToken

`MALOAuthToken` almacena la conexión OAuth de MyAnimeList.

### Campos

| Campo | Tipo | Nulo / vacío | Descripción |
|---|---|---:|---|
| `access_token` | `TextField` | No | Token de acceso vigente. |
| `refresh_token` | `TextField` | No | Token de renovación. |
| `token_type` | `CharField` | No | Tipo, normalmente Bearer. |
| `expires_at` | `DateTimeField` | No | Fecha de expiración. |
| `created_at` | `DateTimeField` | No | Fecha de creación. |
| `updated_at` | `DateTimeField` | No | Última renovación. |

### Flujo inicial

```text
Owner autenticado
↓
Connect / Renew MAL
↓
state + PKCE
↓
Autorización en MyAnimeList
↓
Callback local
↓
Intercambio de authorization code
↓
Access token + Refresh token
↓
Persistencia en PostgreSQL
```

### Renovación automática

```text
Token válido
→ usarlo

Token próximo a expirar
→ usar refresh token
→ guardar credenciales nuevas
→ continuar
```

### Retry ante 401

```text
Petición a MAL
↓
401 invalid_token
↓
Refresh forzado
↓
Reintento único
```

No se permite un bucle infinito de renovación.

---

## 14. Fuentes externas

### MyAnimeList

MyAnimeList es la fuente principal para:

- Estado personal.
- Progreso personal.
- Score.
- Rewatch / Reread.
- Biblioteca Anime.
- Biblioteca Manga.
- Detalles individuales.
- Relaciones.
- Acciones Add to Plan.

### AniList

AniList se utiliza para:

- Emisiones.
- Próximo episodio.
- Estimación de episodios emitidos.
- Enlaces de streaming.
- Títulos nativos.
- Metadatos externos.
- Search.
- Seasonal Board.
- Catálogo TBA.

AniList no reemplaza a MyAnimeList como fuente de la relación personal.

### Estrategia local-first

```text
API externa
↓
Servicio explícito
↓
Normalización
↓
PostgreSQL
↓
Vistas públicas locales
```

Las páginas normales no deben depender permanentemente de una respuesta externa para renderizar.

---

## 15. Sincronizaciones de Anime

Las sincronizaciones se encuentran divididas por responsabilidad.

### Sync MAL Library

Actualiza los cinco estados de la lista:

```text
watching
completed
on_hold
dropped
plan_to_watch
```

Flujo optimizado:

```text
Descargar páginas de MAL
↓
Normalizar entradas
↓
Cargar entradas existentes en bloque
↓
Comparar en memoria
↓
Created
Updated
Unchanged
↓
Escribir solo cambios reales
```

Resultado típico:

```text
Total: 675
Created: 0
Updated: 1
Unchanged: 674
```

Responsabilidades derivadas:

- Biblioteca.
- Progreso.
- Score.
- Estado personal.
- Command Logs.
- Broadcast Watchlist.
- Contexto local de Sequel Radar.

### Sync Signals

Targets:

```text
list_status = watching
OR
is_rewatching = True
```

Incluye:

- Entradas normales.
- Rewatching.
- Rescates manuales activos que estén Watching o Rewatching.

Flujo:

```text
Seleccionar entradas activas locales
↓
Consultar my_list_status individual en MAL
↓
Actualizar progreso, score y estado
↓
Crear Command Logs
↓
Alinear ManualTrackedAnime cuando existe
↓
Volver a filtrar activos
↓
Consultar AniList
↓
Actualizar señales de emisión
```

No recorre toda la biblioteca.

### Sync Manual Rescues

Procesa:

```text
ManualTrackedAnime.objects.filter(active=True)
```

Responsabilidades:

- Reconstruir entradas omitidas.
- Obtener detalles individuales.
- Resolver estado real desde MAL cuando es posible.
- Usar valores manuales como fallback.
- Mantener el tracker alineado.
- Generar Command Logs.
- Reportar errores por título.

### Relation Scan

Procesa relaciones de un anime específico.

Responsabilidades:

- Importar nodos relacionados.
- Clasificar objetivos anime y manga.
- Resolver targets locales.
- Completar metadatos externos.
- Alimentar Franchise Audit.
- Alimentar Sequel Radar.

### Seasonal Sync

Sincroniza una temporada, año o bucket TBA mediante acciones explícitas.

Las cargas amplias pueden ejecutarse mediante comandos de administración.

---

## 16. Dashboard de Anime

El dashboard funciona como Anime Command Center.

### Métricas y secciones

- Totales por estado.
- Backlog clear ratio.
- Last Sync.
- Episode Signals.
- Broadcast Watchlist.
- Sequel Radar.
- Command Logs.
- Controles privados de sincronización.

### Episode Signals

Muestra:

- Progreso personal.
- Episodios emitidos.
- Episodios pendientes.
- Próxima emisión.
- Streaming cuando existe.

El botón `Sync Signals` pertenece directamente al encabezado de esta sección.

### Broadcast Watchlist

Se deriva de entradas locales:

```text
plan_to_watch
+
currently_airing
```

No requiere un botón de sincronización propio.

### Sequel Radar

Se deriva de:

```text
AnimeRelation guardadas
+
estados actuales de AnimeEntry
```

Relation Scan descubre relaciones.

Sync MAL Library puede cambiar qué candidatos son relevantes al actualizar estados locales.

### Command Logs

Se derivan de `AnimeSyncEvent`.

No necesitan un sync independiente.

---

## 17. Anime Archive

La biblioteca de anime ofrece estados:

```text
All
Watching
Completed
Plan to Watch
On Hold
Dropped
```

Watching incluye:

```text
list_status = watching
OR
is_rewatching = True
```

La biblioteca admite:

- Filtros múltiples de estado.
- Filtros por emisión.
- Paginación.
- Navegación a Relation Scan.
- Etiquetas de Rewatching.
- Portadas y progreso.
- Acceso público de solo lectura.

---

## 18. Search / Rescue

Search utiliza AniList para encontrar candidatos y compararlos con la biblioteca local.

Puede:

- Buscar por título.
- Detectar una entrada local.
- Abrir Relation Scan.
- Rescatar una entrada por MAL ID.
- Completar metadatos públicos.
- Crear una excepción manual cuando MAL omite una entrada real.

Los rescates no deben convertirse en una segunda biblioteca paralela.

Son una capa excepcional y explícita.

---

## 19. Rutas actuales de Anime

```text
/anime/                              Dashboard
/anime/status/<status>/              Archivo por estado
/anime/<mal_id>/relations/           Relation Scan
/anime/<mal_id>/relations/sync/      Sincronizar relaciones
/anime/search/                       Search
/anime/search/rescue/                Rescue desde Search
/anime/seasonal/                     Seasonal Board
/anime/seasonal/sync/                Sincronizar Seasonal
/anime/seasonal/add-to-plan/         Add to Plan
/anime/sync/                         Alias de Sync MAL Library
/anime/sync/library/                 Sync MAL Library
/anime/sync/episode-signals/         Sync Signals
/anime/sync/manual-rescues/          Sync Manual Rescues
/anime/oauth/mal/connect/             Iniciar OAuth
/anime/oauth/mal/callback/            Callback OAuth
```

---

## 20. Comandos actuales

```text
fetch_anime_status
fetch_anime_relations
inspect_airing_data
rescue_anime_entry
sync_airing_data
sync_anime_metadata
sync_seasonal_anime
```

### Ejemplos

```bash
python manage.py fetch_anime_status watching
```

```bash
python manage.py fetch_anime_relations 32182
```

```bash
python manage.py inspect_airing_data 63832
```

```bash
python manage.py rescue_anime_entry 46488   --status watching   --episodes-watched 1   --sync-airing
```

```bash
python manage.py sync_seasonal_anime SUMMER 2026
```

Los comandos se utilizan para mantenimiento, inspección y cargas amplias.

---

## 21. Acceso y seguridad

### Acceso público

Las vistas de lectura son públicas.

Ejemplos:

- Dashboard.
- Anime Archive.
- Search.
- Seasonal.
- Relation Scan.

### Acceso owner

Las acciones mutables requieren autenticación.

Normalmente requieren:

```text
login
POST
CSRF
```

Ejemplos:

- Sync MAL Library.
- Sync Signals.
- Sync Manual Rescues.
- Relation Sync.
- Seasonal Sync.
- Add to Plan.
- Rescue.

### OAuth

Connect y Callback son flujos GET autenticados.

Su seguridad se apoya en:

- Sesión owner.
- `state`.
- PKCE.
- Redirect URL exacta.
- Client ID y Client Secret privados.
- Tokens almacenados en PostgreSQL.

### Secretos

Nunca deben versionarse:

- `.env`.
- MAL Client Secret.
- Access tokens.
- Refresh tokens.
- Database credentials.
- Payloads privados.

---

## 22. Arquitectura prevista de Manga

La mitad Manga reutilizará la infraestructura estable de Anime:

- OAuth.
- Cliente MAL.
- Supabase.
- Permisos.
- Toasts.
- Tests aislados.
- Sincronización optimizada.
- Layout de MAL Insights.
- Separación web / services.
- Created / Updated / Unchanged.

La estructura prevista es:

```text
mal_data/
├── manga_urls.py
├── services/
│   ├── manga_list_sync.py
│   ├── manga_reading_sync.py
│   └── manual_tracked_manga_sync.py
└── web/
    ├── manga_dashboard.py
    ├── manga_library.py
    ├── manga_search.py
    └── manga_sync.py
```

Los nombres exactos pueden ajustarse durante implementación, pero la separación por responsabilidad debe conservarse.

---

## 23. Manga Library Sync

Manga debe utilizar desde el inicio la estrategia optimizada:

```text
Fetch MAL manga list
↓
Normalizar
↓
in_bulk por mal_id
↓
Comparar campos relevantes
↓
Created
Updated
Unchanged
↓
Guardar solo cambios reales
```

Estados:

```text
reading
completed
on_hold
dropped
plan_to_read
```

Campos comparables:

- Título.
- Portada.
- Tipo.
- Estado de publicación.
- Volúmenes totales.
- Capítulos totales.
- Fechas.
- Estado personal.
- Score.
- Volúmenes leídos.
- Capítulos leídos.
- Rereading.
- Updated at MAL.

---

## 24. Manga Archive

Vistas previstas:

```text
/manga/
/manga/status/all/
/manga/status/reading/
/manga/status/completed/
/manga/status/plan-to-read/
/manga/status/on-hold/
/manga/status/dropped/
```

La ruta exacta de `all` podrá resolverse como dashboard o archivo general.

Reading incluirá:

```text
list_status = reading
OR
is_rereading = True
```

Filtros previstos:

- Estado personal.
- Estado de publicación.
- Tipo de manga.
- Reading / Rereading.
- Finished / Publishing / On Hiatus cuando MAL lo permita.

Orden previsto:

- Actualización MAL.
- Título.
- Progreso.
- Score.

---

## 25. Manga Dashboard

El dashboard de Manga no copiará Episode Signals.

Métricas iniciales:

- Total Manga.
- Reading.
- Completed.
- Plan to Read.
- On Hold.
- Dropped.
- Rereading.
- Chapters Read.
- Volumes Read.
- Completion Ratio.
- Currently Publishing.
- Finished Publications.

Secciones previstas:

```text
Reading Signals
Manga Command Logs
Publication Watchlist
Anime Adaptation Bridge
Recent Changes
```

Las secciones que dependan de fuentes aún no implementadas deben introducirse por etapas.

---

## 26. Reading Progress Sync

El equivalente inicial de Sync Signals será:

```text
Sync Reading Progress
```

Targets:

```text
list_status = reading
OR
is_rereading = True
```

Flujo inicial:

```text
Seleccionar mangas activos locales
↓
Consultar my_list_status individual en MAL
↓
Actualizar capítulos
↓
Actualizar volúmenes
↓
Actualizar score
↓
Actualizar estado
↓
Alinear rescates manuales
↓
Crear Manga Command Logs
```

No debe recorrer toda la biblioteca.

No debe depender inicialmente de scrapers de capítulos.

---

## 27. MangaSyncEvent previsto

La mitad Manga necesita Command Logs propios.

Tipos previstos:

```text
created
status_changed
chapter_changed
volume_changed
score_changed
```

Ejemplos:

```text
CHAPTER_UPDATE
Ao Ashi [CH. 392 → CH. 393]

VOLUME_UPDATE
Manga X [VOL. 8 → VOL. 9]

STATUS_UPDATE
Manga Y [Reading → Completed]
```

No se recomienda reutilizar `AnimeSyncEvent` porque su FK y sus tipos están ligados al dominio anime.

---

## 28. Rescates de Manga previstos

Manga puede sufrir omisiones equivalentes a Tai-Ari.

Se prevé:

```text
ManualTrackedManga
```

Campos equivalentes:

- MAL ID.
- Título snapshot.
- Estado.
- Capítulos leídos.
- Volúmenes leídos.
- Score.
- Rereading.
- Active.
- Notes.
- Timestamps.

Comando previsto:

```text
rescue_manga_entry
```

Flujo:

```text
MAL list API omite manga
↓
Rescate explícito por MAL ID
↓
Detalle individual MAL
↓
MangaEntry
↓
ManualTrackedManga
↓
Reading Progress Sync cotidiano
```

---

## 29. Relaciones Manga y puente Anime ↔ Manga

El objetivo futuro es navegar:

```text
Anime → Manga original
Manga → Anime adaptation
Manga → Sequel
Manga → Prequel
Manga → Side Story
Manga → Spin-off
Manga → Alternative Version
```

Se prevé `MangaRelation` como fuente específica de manga.

No se recomienda modificar agresivamente `AnimeRelation` al inicio del arco Manga.

### Puente

El puente permitirá:

- Abrir el manga relacionado desde un anime.
- Abrir adaptaciones anime desde un manga.
- Comparar estado local en ambos mundos.
- Mostrar si una adaptación está en Watching, Completed o Plan to Watch.
- Mostrar si el manga está Reading, Completed o Plan to Read.

El puente no implica compartir estados.

Anime y Manga mantienen relaciones personales independientes.

---

## 30. Chapter Signals futuros

Chapter Signals es un sistema posterior a Manga Base.

MAL informa progreso personal, pero no siempre informa de forma útil el último capítulo disponible según scans o publicación internacional.

El modelo conceptual futuro puede incluir:

```text
MangaEntry
└── MangaSource
    └── ChapterAvailabilitySnapshot
```

Datos posibles:

```text
preferred_source
source_type
source_url
latest_available_chapter
last_checked_at
active
notes
```

Fuentes consideradas en el flujo personal:

- MangaPlus.
- Weeb Central.
- MangaFire EN.
- Mangas.in.
- Mihon como referencia local.
- Fuentes japonesas específicas cuando corresponda.

### Cálculo futuro

```text
latest_available_chapter
-
num_chapters_read
=
pending chapters
```

### Regla de implementación

Chapter Signals no bloqueará el MVP inicial de Manga.

Orden correcto:

```text
Manga Library
↓
Manga Dashboard
↓
Reading Progress
↓
Search / Rescue
↓
Relations
↓
Chapter Signals
```

---

## 31. Integración futura con Hibi Log

Hibi Log podrá relacionar actividad con:

- `AnimeEntry`.
- `MangaEntry`.
- Rewatch / Reread.
- Episodios.
- Capítulos.
- Rangos de progreso.

Ejemplo Anime:

```text
ActivitySession
module: MAL Insights
media_type: anime
entry: Tennis no Oujisama
progress_from: Episode 12
progress_to: Episode 15
duration_minutes: 72
```

Ejemplo Manga:

```text
ActivitySession
module: MAL Insights
media_type: manga
entry: Tennis no Oujisama
progress_from: Chapter 15
progress_to: Chapter 19
language: en
```

MAL Insights debe mantener identificadores estables para esta integración.

---

## 32. Pruebas

La suite global actual contiene:

```text
242 pruebas aprobadas
```

La suite de MAL Insights cubre actualmente:

- Rutas públicas.
- Rutas protegidas.
- OAuth token exchange.
- Persistencia de tokens.
- Refresh automático.
- Retry único ante MAL 401.
- Created / Updated / Unchanged.
- Selección de Watching.
- Selección de Rewatching.
- Selección de rescates manuales.
- Actualización de progreso.
- Generación de Command Logs.
- Sincronización manual desde estado real de MAL.

La mitad Manga deberá añadir pruebas para:

- MangaEntry.
- Manga Library Sync.
- Reading y Rereading.
- Created / Updated / Unchanged.
- Capítulos y volúmenes.
- Manga Command Logs.
- Rutas públicas.
- Acciones POST protegidas.
- Rescates manuales.
- Switch Anime / Manga.
- Relaciones Manga.
- Chapter Signals cuando se implementen.

Las pruebas utilizan:

```text
config.test_settings
SQLite en memoria
```

No modifican Supabase.

---

## 33. Decisiones fuera del primer MVP de Manga

No deben bloquear Manga Base:

- Scraping universal de todos los sitios.
- Sincronización permanente en background.
- Soporte para cada extensión de Mihon.
- Detección perfecta del último capítulo en todas las fuentes.
- Descarga de capítulos.
- Lectura dentro de MVS Tracker.
- Seguimiento por página.
- Registro de paneles.
- Múltiples usuarios.
- Reconciliación automática completa de todas las diferencias MAL.
- Refactor genérico total de AnimeRelation.
- Calendario completo de publicación sin fuente confiable.

---

## 34. Estado de implementación

```text
Documento: mal-insights-data-model.md
Módulo: MAL Insights
Aplicación técnica: mal_data
Migración actual: mal_data.0010_maloauthtoken
Pruebas globales: 242 OK

Anime:
Estado: Funcionalmente estable
Rutas: Implementadas bajo /anime/
OAuth: Implementado
MAL Library Sync: Implementado y optimizado
Episode Signals: Implementado
Manual Rescues: Implementado
Seasonal Board: Implementado
Relations / Franchise Audit / Sequel Radar: Implementados
Search: Implementado

Manga:
MangaEntry: Implementado
Cliente MAL manga: Base disponible
Dashboard: Pendiente
Rutas públicas: Pendientes
Manga Library Sync: Pendiente
Reading Progress Sync: Pendiente
Manga Command Logs: Pendientes
Manual Manga Rescues: Pendientes
Manga Relations: Pendientes
Anime ↔ Manga Bridge: Pendiente
Chapter Signals: Pendiente

Siguiente bloque:
Manga Foundation
```

Este documento debe actualizarse durante el arco Manga cada vez que:

- Se amplíe `MangaEntry`.
- Se creen migraciones nuevas.
- Se implemente el switch Anime / Manga.
- Se añada Manga Library Sync.
- Se incorporen Command Logs de Manga.
- Se creen rescates manuales de Manga.
- Se implemente Manga Relations.
- Se introduzcan Chapter Signals.
