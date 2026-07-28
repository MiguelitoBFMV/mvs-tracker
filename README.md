# MVS Tracker

MVS Tracker is a modular personal media platform built to organize what I want to consume, record what I actually do, and analyze my progress across anime, manga, video games, series, movies, and music.

The platform is organized around four content-tracking modules and one cross-module activity layer:

```text
MVS Tracker
├── MAL Insights
│   └── Anime & Manga
├── Game Kiroku
│   └── Video Games
├── Watchroom
│   └── Series & Movies
├── Music
│   └── Last.fm listening data
└── Hibi Log
    └── Daily activity across all four trackers
```

The project began as MAL Insight Lab, a personal MyAnimeList analytics dashboard. It is now a broader Django platform composed of independent but connected modules.

## Current Status

MVS Tracker is in active development.

The application currently runs locally and uses Supabase PostgreSQL as its shared database. MAL Insights, Game Kiroku, and Watchroom are available. Game Kiroku and Watchroom have completed their MVP scope.

The anime side of MAL Insights is functionally stable and includes automatic MyAnimeList OAuth renewal, optimized synchronization workflows, manual rescue support for entries omitted by the MAL list API, and unified Episode Signals for normal and manually rescued entries.

The manga side of MAL Insights is now operational. It includes the public Manga Command Center, status archives, optimized MAL library synchronization, Reading and Rereading progress synchronization, manual rescues, Manga Command Logs, canonical completion signals, and live Chapter Signals backed by persistent external source links. MANGA Plus can be used as the preferred official source for supported titles, while Weeb Central can act as a lower-priority source or automatic fallback.

Game Kiroku combines a local-first IGDB workflow, replay-aware playthrough history, additional-content tracking, a dedicated Platinum Collection, franchise timelines, completed-import history, and configurable competitive-rank tracking.

Watchroom combines local movie and series tracking with viewing-run history, MAL-style season progress, TMDB search and import, safe metadata refresh, mixed-media franchises, and automatic TMDB movie-collection synchronization.

The platform supports two access levels:

- Public read-only access for browsing data.
- Authenticated owner access for synchronization, editing, tracking actions, OAuth connection, and administration.

Public registration is intentionally disabled.

## Modules

### MAL Insights

Status: **Available — anime stable; manga foundation and Chapter Signals operational**

MAL Insights is the anime and manga analytics module connected to MyAnimeList and enriched with AniList and explicit chapter-availability sources.

Current anime features include:

- Anime library by MAL list status.
- Watching and rewatching support.
- Unified Episode Signals for Watching, Rewatching, and active manual rescues.
- Progress, score, and status refresh for active Episode Signal entries.
- AniList airing data, next-episode information, pending-episode calculations, and streaming links.
- Seasonal anime discovery.
- Add to Plan behavior that checks the real MAL list status before modifying an entry.
- Franchise relation scanning.
- Franchise Audit.
- Sequel Radar.
- Broadcast Watchlist.
- Search and manual rescue tools.
- Persistent `ManualTrackedAnime` fallbacks for entries omitted by the MAL list API.
- Command Logs for episode, score, and status changes.
- AniList metadata enrichment.
- Separate synchronization actions for MAL Library, Episode Signals, and Manual Rescues.
- Optimized MAL Library synchronization with Created, Updated, and Unchanged classification.
- Automatic MyAnimeList OAuth token renewal.
- A single forced token refresh and retry after a MAL `401 invalid_token` response.
- Public read-only mode.
- Owner-only synchronization and write actions.

Current manga features include:

- Public Manga Command Center and Anime / Manga world switch.
- Manga archive by All, Reading, On Hold, Plan to Read, Completed, and Dropped status.
- Reading and Rereading support.
- Optimized MAL manga-library synchronization.
- Active reading-progress refresh from MAL.
- Persistent `ManualTrackedManga` rescues for entries omitted by the MAL list API.
- Manga Command Logs for status, chapter, volume, and score changes.
- Canonical completion signals for finished manga.
- Live Chapter Signals for publishing manga.
- Persistent `MangaSourceLink` records per manga and provider.
- Configurable source priority where lower numbers are preferred.
- MANGA Plus and Weeb Central provider support.
- Automatic fallback through active sources in priority order.
- Explicit provider override for inspection and synchronization.
- Latest-available and pending-chapter calculations, including decimal chapters.
- Batch external synchronization with per-title error isolation.
- Provider attempts and fallback usage stored with the signal metadata.
- Public read-only visibility and owner-only synchronization actions.

The synchronization controls remain explicit:

- **Anime — Sync MAL Library** updates the five MAL anime-list statuses, personal progress, scores, Command Logs, Broadcast Watchlist data, and the local context used by Sequel Radar.
- **Anime — Sync Signals** refreshes active Watching and Rewatching progress and AniList airing information.
- **Anime — Sync Manual Rescues** rebuilds and refreshes anime entries omitted by the normal MAL list endpoint.
- **Manga — Sync Manga Library** updates the five MAL manga-list statuses and local archive.
- **Manga — Sync Signals** refreshes active Reading and Rereading progress, canonical totals, and linked external chapter sources.
- **Manga — Sync Manual Rescues** rebuilds and refreshes omitted manga entries.
- **Connect / Renew MAL** starts the owner-only OAuth authorization flow when the account must be connected again.

Routes:

```text
/anime/                                  Anime Command Center
/manga/                                  Manga Command Center
/manga/status/<status>/                  Manga archive by status
```

### Game Kiroku / ゲーム記録

Status: **Available — MVP complete**

Game Kiroku is the video game library, playthrough, access, platinum, franchise, additional-content, and competitive-rank tracking module.

Current features include:

- Local game library stored in Supabase PostgreSQL.
- Dynamic dashboard with Owned, Wishlist, Completed, Platinum, Plan to Play, and Multiplayer metrics.
- Replay-aware completion analytics.
- Completion analytics that exclude persistent multiplayer games.
- Public library with search and filters for status, access type, platform, Platinum Unlocked, and Platinum Target.
- Platinum-filtered ordering by acquisition date, with unknown dates placed last.
- Rich individual game detail pages.
- Playing, Paused, Dropped, Completed, Plan to Play, and Multiplayer states.
- Manual status control for games without playthrough history.
- Playthrough-driven status synchronization when playthrough history exists.
- Multiple playthroughs per game.
- Automatic creation of `Playthrough 1` when a newly imported game starts as Completed.
- Historical backfill support for completed entries that predate automatic playthrough creation.
- Text language, platform access, progress, dates, notes, and hours per playthrough.
- `Unspecified` as a valid historical language fallback when the original language is unknown.
- Owned and Wishlist access records by platform and storefront, including Xbox / Game Pass as a store option.
- Owner controls for creating, editing, and deleting eligible access records.
- Historical protection for accesses already referenced by playthroughs.
- Main-story duration from IGDB with manual override support.
- Platinum tracking at `LibraryEntry` level, independent of the current platform.
- Optional platinum acquisition dates.
- Platinum targets for future goals.
- Dedicated Platinum Collection with the latest platinum, yearly history, unknown-date records, and future targets.
- Manual franchise grouping.
- Public franchise list and franchise detail pages.
- Franchise metrics for total, owned, active, Plan to Play, completed, and platinum games.
- Release timelines that can be ordered oldest-first or newest-first.
- Optional franchise logos.
- Dynamic franchise artwork selected from the most relevant library game.
- Representative-game priority of Playing, Completed, Paused, Multiplayer, Plan to Play, and Dropped.
- Owner controls for creating, editing, and safely deleting empty franchises.
- Assignment, movement, and removal of games from franchises without using Django admin.
- Optional franchise assignment during IGDB import.
- Owner-only forms for library entries, franchises, accesses, playthroughs, and additional content.
- Explicit IGDB search, review, import, linking, and refresh actions.
- Local-first storage of imported IGDB metadata.
- Exact-title-first IGDB search ranking with bundles and secondary editions deprioritized.
- Imported cover art, background artwork, synopsis, release date, genres, platforms, raw payload, and synchronization timestamp.
- Linking IGDB metadata to existing local games without replacing their slug, accesses, playthroughs, notes, or status.
- Creating a new `Game`, `LibraryEntry`, and initial `GameAccess` in one transactional import.
- Validation that prevents a platinum-marked entry from existing without at least one Owned access.
- Additional Content records for DLC, expansions, standalone expansions, and manually registered related content.
- IGDB detection of `dlcs`, `expansions`, `standalone_expansions`, and `parent_game` relationships.
- Choice to track detected content under its parent game or review it as a separate library game.
- Status, optional completion date, notes, synopsis, cover, release date, and raw IGDB payload for tracked additional content.
- Configurable competitive modes per game, such as Rocket League `1V1`, `2V2`, and `3V3`.
- Game-specific rank tiers with optional division systems.
- Timestamped competitive-rank history with season, rank, division, notes, and multiple updates on the same day.
- Current rank derived from the latest historical record instead of a separately overwritten field.
- Roman-numeral division display and per-tier maximum-division validation.
- Safe editing and deletion of rank records, with automatic fallback to the previous current rank.
- Mode archiving that preserves history while removing archived modes from new-record forms.
- Protected deletion of modes and tiers already referenced by rank history.
- Idempotent competitive presets for Rocket League and REDSEC inside Battlefield 6.
- Lazy tier management that renders only the selected tier editor on large configurations.
- Public read-only mode and owner-only write actions.
- Automated model, route, permission, dashboard, library, detail, platinum, franchise, playthrough, access, completed-import, competitive-ranking, preset-command, and form tests.

IGDB is treated as an import and enrichment source. Normal Game Kiroku pages read from Supabase and do not contact IGDB automatically. Search, import, linking, and refresh operations happen only after an explicit owner action.

Routes:

```text
/games/                               Dashboard
/games/library/                       Library
/games/library/<slug>/                Game detail
/games/platinum/                      Platinum Collection
/games/franchises/                    Franchise list
/games/franchises/<slug>/             Franchise detail
/games/igdb/search/                   Owner IGDB search
/games/igdb/<igdb_id>/import/         Owner import review
```

### Watchroom

Status: **Available — MVP complete**

Descriptor: **Series & Movies**

Watchroom manages media outside the anime ecosystem through two core behaviour types:

```text
movie
series
```

Presentation remains independent from progress behaviour:

```text
animation
live_action
documentary
mixed
other
```

Current features include:

- Dedicated Django app with migrations through `watchroom.0006`.
- Local `MediaWork`, `WatchEntry`, `Season`, `ViewingRun`, `SeasonProgress`, `Franchise`, and `FranchiseMembership` models.
- Movie and Series as the only progress engines.
- Presentation classification for Animation, Live Action, Documentary, Mixed, and Other.
- Stable local slugs and type-scoped TMDB identities.
- Public dashboard with Total, Watching, Completed, Plan to Watch, Movies, and Series metrics.
- Public searchable and filterable library.
- Filters for type, personal status, presentation, and active rewatches.
- Ordering by title, recent updates, and release date.
- Public movie and series detail pages.
- Public franchise index and franchise detail pages.
- Season 0 / Specials stored separately from ordinary completion totals.
- Canonical episode totals without per-episode database rows.
- MAL-style aggregate series progress such as `12 / 38`.
- `SeasonProgress` stores only `episodes_watched`; run dates belong exclusively to `ViewingRun`.
- First-watch and rewatch history with automatic sequential numbering.
- Pause, resume, complete, and drop transitions.
- Historical Completed status preserved while a rewatch is active, paused, or dropped.
- Movie progress in optional watched minutes.
- Automatic movie completion progress when a known runtime exists.
- Automatic series-run completion after an explicit owner progress update completes every known regular season.
- Specials excluded from automatic series completion.
- Completed series progress remains visible but read only until a new rewatch starts.
- Derived Rewatching, Rewatch Paused, and Up to Date display states.
- Manual local movie and series creation.
- Owner editing and permanent work deletion.
- Owner season creation, editing, safe deletion, and protection for seasons referenced by progress.
- Owner run creation, detail editing, transitions, notes, and optional dates.
- Owner season-progress upserts for the active run only.
- TMDB client with bearer-token authentication and normalized movie, series, season, and collection payloads.
- Owner-only TMDB search with Movie / Series selection and imported-work detection.
- Review-before-import workflow for movies and series.
- Transactional TMDB import with duplicate protection.
- Completed movie imports initialized with full runtime progress when known.
- Completed series imports initialized with full progress for known regular seasons.
- Explicit safe TMDB refresh for metadata, runtime, images, external status, and canonical seasons.
- Refresh protection for personal status, notes, runs, dates, movie progress, and season progress.
- Episode totals and movie runtimes preserved when incoming TMDB values would fall below stored progress.
- Missing local seasons, including Specials, restored when TMDB returns them again.
- Manual mixed-media franchises that can combine movies, series, specials, spin-offs, and extras.
- Ordered franchise memberships with roles and optional notes.
- Automatic TMDB movie-collection creation and reuse during movie import or refresh.
- Existing manual franchise positions and roles preserved during TMDB synchronization.
- Franchise background images based on `backdrop_url`, with TMDB poster metadata retained as a fallback.
- Safe franchise deletion that preserves library works.
- Shared optimized query and decoration helpers for dashboard, library, and detail views.
- Shared services for viewing state, TMDB import, refresh, normalization, and collection synchronization.
- TMDB attribution in the Watchroom footer.
- Public read-only access.
- Authenticated, POST-only, CSRF-protected write actions.
- **155 passing Watchroom tests** covering models, constraints, forms, services, TMDB workflows, routes, permissions, dashboard, library, detail, owner workflows, transitions, history, and franchises.

TMDB is treated as an explicit import and synchronization source. Normal Watchroom pages read from Supabase PostgreSQL and do not contact TMDB automatically.

Routes:

```text
/watchroom/                                                    Dashboard
/watchroom/library/                                            Library
/watchroom/library/create/                                     Owner manual creation
/watchroom/library/<slug>/                                     Work detail
/watchroom/library/<slug>/delete/                              Owner permanent deletion
/watchroom/library/<slug>/entry/update/                        Owner entry update
/watchroom/library/<slug>/seasons/create/                      Owner season creation
/watchroom/library/<slug>/seasons/<id>/update/                 Owner season update
/watchroom/library/<slug>/seasons/<id>/delete/                 Owner season deletion
/watchroom/library/<slug>/runs/create/                         Owner run creation
/watchroom/library/<slug>/runs/<id>/update/                    Owner run update
/watchroom/library/<slug>/runs/<id>/<action>/                  Owner run transition
/watchroom/library/<slug>/runs/<id>/progress/<id>/update/      Owner season progress
/watchroom/library/<slug>/tmdb/refresh/                        Owner TMDB refresh
/watchroom/search/                                             Owner TMDB search
/watchroom/import/<media_type>/<tmdb_id>/                      Owner TMDB import review
/watchroom/franchises/                                         Franchise index
/watchroom/franchises/create/                                  Owner franchise creation
/watchroom/franchises/<slug>/                                  Franchise detail
/watchroom/franchises/<slug>/update/                           Owner franchise update
/watchroom/franchises/<slug>/delete/                           Owner empty-franchise deletion
/watchroom/franchises/<slug>/members/add/                      Owner membership creation
/watchroom/franchises/<slug>/members/<id>/update/              Owner membership update
/watchroom/franchises/<slug>/members/<id>/remove/              Owner membership removal
```

### Music

Status: **Planned — final module**

The music module will use Last.fm as its primary listening-data source.

Planned features include:

- Artists, albums, and tracks.
- Scrobble history.
- Listening totals by period.
- Rankings and trends.
- Personal listening analytics.
- Yearly and monthly summaries.
- Data that can later feed Hibi Log.

Its final public name has not been selected yet.

Planned route:

```text
/music/
```

### Hibi Log / 日々ログ

Status: **Planned**

Hibi Log is the cross-module activity layer and the natural general dashboard of MVS Tracker.

The four tracking modules describe what content exists and the user's relationship with it. Hibi Log records what was actually done each day.

It will eventually connect activity from:

- MAL Insights.
- Game Kiroku.
- Watchroom.
- Music.

Planned features include:

- Daily sessions.
- Calendar view.
- Time spent.
- Episodes, chapters, and game progress.
- Series and movie activity.
- Music activity summaries.
- Progress ranges.
- Notes and session impressions.
- Weekly summaries.
- Activity analytics.
- Comparison between plans and actual activity.

Planned route:

```text
/activity/
```

## Platform Routes

```text
/                                          MVS Tracker module selector
/accounts/login/                           Owner login
/accounts/logout/                          Owner logout
/anime/                                    MAL Insights — Anime
/manga/                                    MAL Insights — Manga
/manga/status/<status>/                    Manga archive by status
/games/                                    Game Kiroku dashboard
/games/library/                            Game Kiroku library
/games/library/<slug>/                     Game Kiroku game detail
/games/platinum/                           Game Kiroku Platinum Collection
/games/franchises/                         Game Kiroku franchise list
/games/franchises/<slug>/                  Game Kiroku franchise detail
/games/igdb/search/                        Owner-only IGDB search
/games/igdb/<igdb_id>/import/              Owner-only IGDB import review
/watchroom/                                Watchroom dashboard
/watchroom/library/                        Watchroom library
/watchroom/library/<slug>/                 Watchroom work detail
/watchroom/franchises/                     Watchroom franchise index
/watchroom/franchises/<slug>/              Watchroom franchise detail
/watchroom/search/                         Owner-only TMDB search
/watchroom/import/<type>/<tmdb_id>/        Owner-only TMDB import review
/music/                                    Music — planned
/activity/                                 Hibi Log — planned
/admin/                                    Django administration
```

Hibi Log will serve as the future cross-module activity dashboard, so a separate global `/dashboard/` route is not currently planned.

## Access Model

Read-only views are publicly accessible.

Actions that modify external services, Supabase, or local application data normally require:

- An authenticated user.
- A POST request.
- CSRF validation.

The MyAnimeList OAuth connect and callback routes are authenticated owner flows that use OAuth state validation and PKCE rather than normal write-form POST handling.

Opening a normal page never triggers an automatic synchronization.

## Tech Stack

- Python
- Django
- PostgreSQL
- Supabase PostgreSQL
- MyAnimeList API v2
- OAuth 2.0 with PKCE and refresh tokens
- AniList GraphQL API
- MANGA Plus chapter metadata integration
- Weeb Central HTML chapter metadata integration
- IGDB API
- Twitch application authentication for IGDB
- TMDB API with application bearer-token authentication
- Last.fm API — planned
- HTML
- CSS
- Django Authentication
- python-dotenv
- requests
- Beautiful Soup
- Protocol Buffers
- dj-database-url

## Project Structure

```text
mvs-tracker/
├── config/
│   ├── settings.py
│   ├── test_settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── core/
│   ├── static/core/
│   ├── templates/core/
│   ├── apps.py
│   ├── tests.py
│   ├── urls.py
│   └── views.py
│
├── games/
│   ├── management/commands/
│   │   ├── backfill_completed_playthroughs.py
│   │   └── setup_competitive_presets.py
│   ├── migrations/
│   ├── services/
│   │   ├── igdb_client.py
│   │   ├── igdb_importer.py
│   │   ├── igdb_normalizer.py
│   │   └── playthrough_state.py
│   ├── static/games/
│   ├── templates/games/
│   ├── web/
│   ├── admin.py
│   ├── apps.py
│   ├── forms.py
│   ├── models.py
│   ├── tests.py
│   └── urls.py
│
├── mal_data/
│   ├── management/commands/
│   ├── migrations/
│   ├── services/
│   ├── static/mal_data/
│   ├── web/
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── tests.py
│   └── urls.py
│
├── watchroom/
│   ├── migrations/
│   ├── services/
│   │   ├── tmdb_client.py
│   │   ├── tmdb_collections.py
│   │   ├── tmdb_importer.py
│   │   ├── tmdb_normalizer.py
│   │   ├── tmdb_refresh.py
│   │   └── viewing.py
│   ├── static/watchroom/
│   ├── templates/watchroom/
│   │   ├── base.html
│   │   ├── create_work.html
│   │   ├── dashboard.html
│   │   ├── detail.html
│   │   ├── franchise_create.html
│   │   ├── franchise_detail.html
│   │   ├── franchise_index.html
│   │   ├── library.html
│   │   ├── tmdb_import.html
│   │   └── tmdb_search.html
│   ├── web/
│   │   ├── common.py
│   │   ├── dashboard.py
│   │   ├── detail.py
│   │   ├── franchises.py
│   │   ├── library.py
│   │   ├── owner.py
│   │   └── tmdb.py
│   ├── admin.py
│   ├── apps.py
│   ├── forms.py
│   ├── models.py
│   ├── tests.py
│   └── urls.py
│
├── templates/
│   ├── registration/
│   ├── mal_data/
│   └── base.html
│
├── docs/
│   ├── game-kiroku-data-model.md
│   ├── mal-insights-data-model.md
│   └── watchroom-data-model.md
│
├── manage.py
├── requirements.txt
└── README.md
```

The technical Django app name `mal_data` is intentionally preserved to avoid unnecessary migration and database table changes. Its public module name is **MAL Insights**.

Watchroom is an active Django app with a completed MVP, local-first TMDB workflows, public franchise views, and authenticated owner management. Music and Hibi Log do not yet have Django apps; their selector cards continue to define the remaining platform roadmap.

## Environment Variables

Create a `.env` file in the project root.

```env
SECRET_KEY=your-django-secret-key
DEBUG=True
DATABASE_URL=postgresql://...

MAL_CLIENT_ID=your-mal-client-id
MAL_CLIENT_SECRET=your-mal-client-secret
MAL_REDIRECT_URI=http://127.0.0.1:8000/anime/oauth/mal/callback/

MANGAPLUS_DEVICE_ID=your-generated-device-uuid
MANGAPLUS_DEVICE_SECRET=optional-existing-device-secret

IGDB_CLIENT_ID=your-twitch-client-id
IGDB_CLIENT_SECRET=your-twitch-client-secret

TMDB_READ_ACCESS_TOKEN=your-tmdb-read-access-token
TMDB_LANGUAGE=en-US
TMDB_REGION=CL

ALLOWED_HOSTS=127.0.0.1,localhost
```

MyAnimeList access and refresh tokens are obtained through the owner-only OAuth flow and stored in the database. A permanent `MAL_ACCESS_TOKEN` is no longer required in `.env`.

The Redirect URL configured in the MyAnimeList API client must match `MAL_REDIRECT_URI` exactly, including host, port, path, and trailing slash.

`MANGAPLUS_DEVICE_ID` identifies the local MANGA Plus client installation. `MANGAPLUS_DEVICE_SECRET` is optional when an existing registered secret is available. Both values are local credentials and must not be committed.

`TMDB_READ_ACCESS_TOKEN` must contain only the API Read Access Token. Do not prefix the stored value with `Bearer`; the Watchroom client builds the authorization header.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

After logging in as the owner, use **Connect / Renew MAL** once to authorize the application. Future MAL access-token expiration is handled automatically through the stored refresh token.

## MAL Insights Synchronization

MAL Insights keeps Anime and Manga synchronization explicit and separated by responsibility.

### Anime — Sync MAL Library

Fetches the five MAL anime-list statuses and updates the local archive.

The sync loads existing records in bulk, compares relevant fields in memory, and writes only entries that actually changed.

A normal result may look like:

```text
Total: 675
Created: 0
Updated: 1
Unchanged: 674
```

### Anime — Sync Signals

Processes only locally active Watching and Rewatching entries, including active manual rescues.

For each active entry it:

- Reads the real personal status and progress from MAL.
- Updates local progress, score, and rewatch state.
- Keeps active manual trackers aligned.
- Creates Command Log events for relevant changes.
- Refreshes AniList airing data.
- Recalculates aired, pending, and next-episode information.

### Anime — Sync Manual Rescues

Refreshes active `ManualTrackedAnime` records and reconstructs their local `AnimeEntry` data when necessary.

This workflow exists for rare cases where an anime appears in the user's real MAL list but is omitted by the normal MAL list API response.

### Manga — Sync Manga Library

Fetches the five MAL manga-list statuses and updates the local manga archive using the same Created, Updated, and Unchanged strategy.

### Manga — Sync Signals

The Manga Sync Signals action performs:

1. Active Reading and Rereading progress synchronization from MAL.
2. Canonical chapter-signal synchronization.
3. External source synchronization for manga with active `MangaSourceLink` records.
4. Final actionable-signal ordering and pending-chapter calculation.

External titles are processed independently. One provider or title failure does not stop the remaining manga from being synchronized.

### Manga — Sync Manual Rescues

Refreshes active `ManualTrackedManga` records and reconstructs omitted local `MangaEntry` data when necessary.

### Rescue an omitted anime

```bash
python manage.py rescue_anime_entry MAL_ID   --status watching   --episodes-watched 1   --sync-airing
```

### Manga Chapter Signal commands

Search for source candidates:

```bash
python manage.py search_manga_source MAL_ID   --provider manga_plus   --query SOURCE_ID_OR_URL
```

Save one result and assign priority:

```bash
python manage.py search_manga_source MAL_ID   --provider manga_plus   --query SOURCE_ID_OR_URL   --save 1   --priority 1
```

Inspect the preferred active source without modifying data:

```bash
python manage.py inspect_manga_source MAL_ID
```

Inspect one explicit provider without fallback:

```bash
python manage.py inspect_manga_source MAL_ID   --provider weeb_central
```

Synchronize one external Chapter Signal:

```bash
python manage.py sync_manga_source_signal MAL_ID
```

When no provider override is supplied, active sources are tried in ascending priority order. A lower-priority source becomes the fallback when a preferred source fails or returns no usable chapters.

## Game Kiroku Maintenance Commands

### Backfill completed playthrough history

Preview completed entries that still lack playthrough history:

```bash
python manage.py backfill_completed_playthroughs --dry-run
```

Create one completed historical playthrough for every eligible entry:

```bash
python manage.py backfill_completed_playthroughs
```

The command is idempotent. Entries that already have playthroughs are skipped.

### Install competitive presets

Preview or apply the Rocket League configuration:

```bash
python manage.py setup_competitive_presets \
  --game "Rocket League" \
  --preset rocket-league \
  --dry-run

python manage.py setup_competitive_presets \
  --game "Rocket League" \
  --preset rocket-league
```

Apply REDSEC ranks to the existing Battlefield 6 library entry:

```bash
python manage.py setup_competitive_presets \
  --game "Battlefield 6" \
  --preset redsec
```

The preset command preserves existing history, creates missing modes and tiers, normalizes preset ordering, supports dry runs, and can be executed repeatedly without creating duplicates.

## Running Tests

MVS Tracker uses an isolated SQLite in-memory database for automated tests.

```bash
python manage.py test   core   mal_data   games   watchroom   --settings=config.test_settings   --verbosity=2
```

The test database is created and destroyed automatically. It does not modify Supabase.

The current four-app regression checkpoint contains **349 passing tests** across `core`, `mal_data`, `games`, and `watchroom`. MAL Insights contributes **46 module tests**, and Watchroom contributes **155 module tests**.

The MAL Insights regression suite covers:

- Public and protected routes.
- OAuth token exchange and storage.
- Automatic refresh of expired MAL tokens.
- A single refresh and retry after a MAL 401 response.
- Created, Updated, and Unchanged MAL library synchronization paths.
- Watching, Rewatching, Reading, Rereading, and manual-rescue target selection.
- Anime and manga progress synchronization.
- Anime and manga Command Log generation.
- Canonical and live Chapter Signals.
- MANGA Plus and Weeb Central parsing and normalization.
- Persistent source links and configurable provider priority.
- Explicit provider overrides and automatic fallback.
- External signal updates, canonical-total preservation, and batch error isolation.
- Anime and Manga dashboard synchronization integration.

The Game Kiroku regression suite covers:

- Public routes and owner-only write actions.
- Dashboard, library, detail, Platinum Collection, and franchise views.
- Platinum dates, targets, filters, ordering, and model validation.
- Franchise visibility, creation, editing, safe deletion, assignment, movement, removal, and timeline ordering.
- Library-entry and playthrough state synchronization.
- Playthrough creation, editing, transitions, numbering, dates, and access validation.
- Access creation, editing, duplicate prevention, historical locking, and safe deletion.
- IGDB import-form validation and franchise selection.
- Automatic completed-playthrough creation during IGDB import.
- Historical completed-playthrough backfill and dry-run behavior.
- Competitive mode, tier, record, division, ordering, and cross-game validation.
- Owner-only competitive CRUD, archived-mode behavior, protected deletion, and current-rank fallback.
- Lazy tier-editor rendering for large configurations.
- Rocket League and REDSEC preset creation, normalization, dry runs, history preservation, and idempotence.

The Watchroom regression suite covers:

- Movie and Series metadata rules.
- Stable unique slugs and type-scoped TMDB identities.
- One personal `WatchEntry` per work.
- Season ownership, Season 0 / Specials, canonical episode totals, duplicate prevention, and protected history.
- Viewing-run numbering, dates, active-run uniqueness, movie-minute progress, and rewatches.
- Run creation, pause, resume, complete, drop, notes, progress, and entry-status synchronization.
- Historical Completed preservation during active or dropped rewatches.
- Aggregate `SeasonProgress`, cross-series validation, episode-count limits, and active-run-only editing.
- Automatic series completion after explicit full regular-season progress.
- Completed-series progress visibility without historical editing.
- Manual creation, editing, permanent deletion, and safe season management.
- TMDB client authentication, endpoints, errors, normalization, search, import review, duplicate protection, and safe refresh.
- Movie-collection normalization, automatic franchise creation, franchise reuse, and refresh-time linking.
- Runtime and episode-total preservation when external values conflict with stored progress.
- Public dashboard, library, work detail, franchise index, and franchise detail views.
- Mixed Movie / Series franchises, ordering, roles, notes, background images, membership management, and safe deletion.
- Login, POST-only, CSRF-backed, cross-work, and 404 protections.
- Core selector behavior for Watchroom as an available module.

## Data Sources

### MyAnimeList

Primary source for personal anime and manga list data.

MyAnimeList OAuth credentials are handled through an owner-authorized flow. Access and refresh tokens are stored in Supabase, access tokens are renewed automatically before expiration, and a failed API request caused by an invalid access token is retried once after a forced refresh.

### AniList

Public metadata and discovery source for anime airing data, native titles, streaming links, seasonal anime, and search.

### MANGA Plus

Preferred official chapter-availability source for supported Shueisha manga.

MVS Tracker stores the selected title link locally and reads recent chapter metadata only during explicit inspection or Chapter Signal synchronization. The latest available chapter is enough to calculate pending progress even when only a limited recent chapter window is exposed.

### Weeb Central

External manga chapter metadata source.

A title can use Weeb Central as its primary source or keep it as a lower-priority fallback. Search results, source IDs, URLs, chapter numbers, labels, timestamps, and selected links are normalized before being stored locally.

### IGDB

Primary metadata and relationship source for Game Kiroku.

IGDB is used through explicit owner actions to:

- Search for games.
- Review the correct title or edition.
- Link metadata to an existing local record.
- Create a new local library record.
- Refresh stored metadata.
- Detect DLC, expansions, standalone expansions, and parent-game relationships.

Imported metadata and raw payloads are stored locally in Supabase. Normal page loads do not require an IGDB request.

### TMDB

Primary metadata and collection source for Watchroom movies and series.

TMDB is used through explicit owner actions to:

- Search for movies and television series.
- Review complete metadata before import.
- Import a new local `MediaWork` and `WatchEntry`.
- Import canonical season summaries for series.
- Detect already imported works.
- Refresh stored titles, descriptions, dates, runtime, images, external status, genres, countries, networks, and raw payloads.
- Create missing seasons and restore locally removed seasons or Specials when TMDB returns them again.
- Preserve local runtime and episode totals when lower external values would conflict with stored progress.
- Detect movie collections.
- Create or reuse local franchises for TMDB movie collections.
- Add imported or refreshed movies to the correct collection position.

Imported metadata and raw payloads are stored locally in Supabase. Normal Watchroom page loads do not require a TMDB request.

Linking an already existing manual work to TMDB remains a post-MVP extension.

### Last.fm

Planned primary listening-data source for the music module. Music will be the final module developed.

## Development Principles

- One Django project containing multiple connected modules.
- Four domain trackers connected through Hibi Log.
- Shared authentication and database.
- Public reading, private writing.
- Local-first storage for imported metadata.
- Explicit synchronization instead of hidden writes during page loads.
- Semantic HTML when appropriate.
- Services separated from HTTP views.
- Modules organized by domain.
- External APIs treated as import and synchronization sources, not permanent runtime dependencies.
- Automated tests use an isolated in-memory database and never modify Supabase.

## Roadmap

### Platform Foundation

- [x] Create the MVS Tracker module selector.
- [x] Move MAL Insights under `/anime/`.
- [x] Add Game Kiroku under `/games/`.
- [x] Add shared authentication.
- [x] Add public read-only mode.
- [x] Protect write actions with login and POST.
- [x] Remove synchronization side effects from GET requests.
- [x] Modularize MAL Insights views.
- [x] Add automated access and route tests.
- [x] Define the four-tracker and Hibi Log architecture.
- [ ] Build Hibi Log as the cross-module activity dashboard.

### Game Kiroku

- [x] Create the Django app.
- [x] Add the module dashboard and navigation.
- [x] Define library, access, playthrough, and additional-content models.
- [x] Add the Game Kiroku admin.
- [x] Build the dynamic dashboard.
- [x] Build the searchable and filterable library.
- [x] Add wishlist and access modeling.
- [x] Add platinum tracking at library-entry level.
- [x] Add platinum acquisition dates and Platinum Targets.
- [x] Add the dedicated Platinum Collection.
- [x] Add Platinum Unlocked and Platinum Target library filters.
- [x] Add replay-aware completion analytics.
- [x] Add the individual game detail page.
- [x] Add owner editing controls.
- [x] Integrate IGDB search, import, linking, and refresh actions.
- [x] Store IGDB metadata locally.
- [x] Add exact-title-first IGDB result ranking.
- [x] Add additional-content tracking for DLC and expansions.
- [x] Detect IGDB DLC, expansion, standalone-expansion, and parent-game relations.
- [x] Allow related content to be tracked under a game or imported separately.
- [x] Add manual additional-content records.
- [x] Protect platinum entries from losing their final Owned access.
- [x] Add public franchise list and detail views.
- [x] Add franchise logos and dynamic representative artwork.
- [x] Add franchise creation, editing, safe deletion, and game assignment.
- [x] Add reversible franchise release-timeline ordering.
- [x] Add manual competitive-rank tracking per game and mode.
- [x] Add completed-import playthrough creation and historical backfill.
- [x] Add competitive presets for Rocket League and REDSEC.
- [x] Complete the final responsive, empty-state, navigation, and documentation review.
- [x] Mark the Game Kiroku MVP as complete.
- [ ] Add an optional full-entry deletion workflow after the MVP.
- [ ] Expand game analytics after the MVP.
- [ ] Connect Game Kiroku activity to Hibi Log.

### Watchroom

- [x] Define the module name and descriptor.
- [x] Select TMDB as the metadata source.
- [x] Create the Django app and migrations through `watchroom.0006`.
- [x] Implement `MediaWork`, `WatchEntry`, `Season`, `ViewingRun`, and `SeasonProgress`.
- [x] Add Movie and Series behaviour types.
- [x] Add Animation, Live Action, Documentary, Mixed, and Other presentation classes.
- [x] Add MAL-style aggregate season progress without per-episode rows.
- [x] Keep run dates on `ViewingRun` and episode counts on `SeasonProgress`.
- [x] Add first-watch and rewatch history.
- [x] Build the public dashboard and module navigation.
- [x] Build the searchable and filterable public library.
- [x] Build public movie and series detail pages.
- [x] Add seasons, Specials, runs, and derived progress displays.
- [x] Add authenticated owner forms and POST-only write actions.
- [x] Add local work creation, personal-status editing, and permanent deletion.
- [x] Add season creation, editing, protected deletion, and progress-safe count validation.
- [x] Add viewing-run creation, transitions, notes, optional dates, and movie-minute progress.
- [x] Add active-run-only season-progress editing and automatic explicit completion.
- [x] Preserve historical Completed state across rewatches.
- [x] Add the TMDB attribution footer.
- [x] Implement the TMDB client and normalized movie, series, season, and collection payloads.
- [x] Add owner-only TMDB search and imported-work detection.
- [x] Add review-before-import for movies and series.
- [x] Add transactional TMDB import and duplicate protection.
- [x] Add safe metadata and season refresh.
- [x] Preserve personal status, runs, dates, notes, and progress during refresh.
- [x] Add runtime and episode-total conflict protection.
- [x] Implement `Franchise` and `FranchiseMembership`.
- [x] Add public franchise index and detail pages.
- [x] Add owner franchise and membership management.
- [x] Support mixed Movie / Series franchises.
- [x] Add automatic TMDB movie-collection synchronization.
- [x] Add franchise ordering, roles, notes, and background images.
- [x] Reach 155 passing Watchroom tests and validate the MVP in the global regression suite.
- [x] Complete and validate the Watchroom MVP.
- [ ] Add optional linking from an existing manual work to TMDB.
- [ ] Add missing-work discovery from TMDB movie collections.
- [ ] Add streaming-provider availability.
- [ ] Connect Watchroom activity to Hibi Log.

### Music

- [ ] Select the final module name.
- [ ] Create the Django app.
- [ ] Integrate Last.fm.
- [ ] Build artist, album, and track views.
- [ ] Add listening-period analytics.
- [ ] Connect music activity to Hibi Log.

### Hibi Log

- [x] Define Hibi Log as the cross-module activity layer.
- [ ] Define the shared activity-session model.
- [ ] Connect sessions to MAL Insights.
- [ ] Connect sessions to Game Kiroku.
- [ ] Connect sessions to Watchroom.
- [ ] Connect summaries to Music.
- [ ] Build the daily calendar.
- [ ] Add weekly summaries.
- [ ] Add activity analytics.

### MAL Insights

- [x] Add automatic MyAnimeList OAuth token renewal.
- [x] Add one-time forced refresh and retry after MAL 401 responses.
- [x] Split MAL Library, Episode Signals, and Manual Rescue synchronization.
- [x] Optimize MAL Library synchronization to skip unchanged entries.
- [x] Unify Episode Signals for normal Watching, Rewatching, and manual rescues.
- [x] Synchronize active Episode Signal progress directly from MAL.
- [x] Generate Command Logs for rescued-entry progress changes.
- [x] Add persistent manual rescue fallbacks for MAL list API omissions.
- [x] Add the Anime / Manga world switch.
- [x] Build the Manga Command Center and public status archives.
- [x] Add optimized manga-library synchronization.
- [x] Add Reading and Rereading progress synchronization.
- [x] Add Manga Command Logs.
- [x] Add persistent manual manga rescues.
- [x] Add canonical completion signals.
- [x] Add persistent external manga source links.
- [x] Add MANGA Plus and Weeb Central providers.
- [x] Add source priority, explicit provider overrides, and automatic fallback.
- [x] Integrate external Chapter Signals into the Manga Sync Signals action.
- [x] Validate the four-app suite at 349 passing tests.
- [ ] Build owner UI for manga source search, linking, activation, and priority management.
- [ ] Add Manga Relations.
- [ ] Add the Anime ↔ Manga adaptation bridge.
- [ ] Expand source support only where a real reading workflow requires it.
- [ ] Detect when a manually rescued anime or manga begins appearing normally in the MAL list API.
- [ ] Improve entries without confirmed MAL IDs.

## Security

Never commit:

- `.env`
- Database credentials
- MAL client secrets
- MAL access tokens
- MAL refresh tokens
- IGDB client secrets
- TMDB read access tokens
- MANGA Plus device IDs or device secrets
- API tokens
- Raw private API responses
- Local virtual environments
- Local database files
- Collected static output

## License

No license has been selected yet.
