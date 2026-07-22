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

The application currently runs locally and uses Supabase PostgreSQL as its shared database. MAL Insights and Game Kiroku are available; Game Kiroku now includes an explicit local-first IGDB import workflow and additional-content tracking for DLC and expansions.

The platform supports two access levels:

- Public read-only access for browsing data.
- Authenticated owner access for synchronization, editing, tracking actions, and administration.

Public registration is intentionally disabled.

## Modules

### MAL Insights

Status: **Available**

MAL Insights is the anime and manga analytics module connected to MyAnimeList and enriched with AniList metadata.

Current features include:

- Anime library by MAL list status.
- Watching and rewatching support.
- Episode Signals.
- Seasonal anime discovery.
- Franchise relation scanning.
- Franchise Audit.
- Sequel Radar.
- Search and manual rescue tools.
- AniList metadata enrichment.
- Manual synchronization controls.
- Public read-only mode.
- Owner-only write actions.

Route:

```text
/anime/
```

### Game Kiroku / ゲーム記録

Status: **Available — active development**

Game Kiroku is the video game library, playthrough, access, and additional-content tracking module.

Current features include:

- Local game library stored in Supabase PostgreSQL.
- Dynamic dashboard with owned, wishlist, completed, platinum, Plan to Play, and multiplayer metrics.
- Replay-aware completion analytics.
- Completion analytics that exclude persistent multiplayer games.
- Public library with title, franchise, status, access, and platform filters.
- Rich individual game detail pages.
- Playing, paused, dropped, completed, Plan to Play, and multiplayer states.
- Manual status control for games without playthrough history.
- Playthrough-driven status synchronization when history exists.
- Multiple playthroughs per game.
- Text language, platform access, progress, dates, notes, and hours per playthrough.
- Owned and wishlist access records by platform and storefront.
- Owner controls for creating, editing, and deleting eligible access records.
- Manual franchise grouping.
- Main-story duration from IGDB with manual override support.
- Platinum indicator at library-entry level.
- Owner-only forms for library entries, accesses, playthroughs, and additional content.
- Explicit IGDB search, review, import, linking, and refresh actions.
- Local-first storage of imported IGDB metadata.
- Exact-title-first IGDB search ranking with bundles and secondary editions deprioritized.
- Imported cover art, background artwork, synopsis, release date, genres, platforms, raw payload, and synchronization timestamp.
- Linking IGDB metadata to existing local games without replacing their slug, accesses, playthroughs, notes, or status.
- Creating a new `Game`, `LibraryEntry`, and initial `GameAccess` in one transactional import.
- Validation that prevents a platinum-marked entry from existing without at least one Owned access.
- Additional Content records for DLC, expansions, standalone expansions, and manual related content.
- IGDB detection of `dlcs`, `expansions`, `standalone_expansions`, and `parent_game` relationships.
- Choice to track detected content under its parent game or review it as a separate library game.
- Status, optional completion date, notes, synopsis, cover, release date, and raw IGDB payload for tracked additional content.
- Public read-only mode and owner-only write actions.
- Automated model, route, permission, dashboard, library, detail, playthrough, and access tests.

IGDB is treated as an import and enrichment source. Normal Game Kiroku pages read from Supabase and do not contact IGDB automatically. Search, import, linking, and refresh operations happen only after an explicit owner action.

Routes:

```text
/games/                               Dashboard
/games/library/                       Library
/games/library/<slug>/                Game detail
/games/igdb/search/                   Owner IGDB search
/games/igdb/<igdb_id>/import/         Owner import review
```

### Watchroom

Status: **Planned**

Descriptor: **Series & Movies**

Watchroom will manage media outside the anime ecosystem, including:

- Live-action series.
- Movies.
- Western cartoons.
- Animated films.
- Documentaries.
- Franchises and connected works.
- Personal status and progress.
- Rewatches.
- Library and backlog analytics.

Planned route:

```text
/watchroom/
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
/                                  MVS Tracker module selector
/accounts/login/                   Owner login
/accounts/logout/                  Owner logout
/anime/                            MAL Insights
/games/                            Game Kiroku dashboard
/games/library/                    Game Kiroku library
/games/library/<slug>/             Game Kiroku game detail
/games/igdb/search/                Owner-only IGDB search
/games/igdb/<igdb_id>/import/      Owner-only IGDB import review
/watchroom/                        Watchroom — planned
/music/                            Music — planned
/activity/                         Hibi Log — planned
/admin/                            Django administration
```

Hibi Log will serve as the future cross-module activity dashboard, so a separate global `/dashboard/` route is not currently planned.

## Access Model

Read-only views are publicly accessible.

Actions that modify external services, Supabase, or local application data require:

- An authenticated user.
- A POST request.
- CSRF validation.

Opening a normal page never triggers an automatic synchronization.

## Tech Stack

- Python
- Django
- PostgreSQL
- Supabase PostgreSQL
- MyAnimeList API v2
- AniList GraphQL API
- IGDB API
- Twitch application authentication for IGDB
- Last.fm API — planned
- HTML
- CSS
- Django Authentication
- python-dotenv
- requests
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
│   ├── migrations/
│   ├── services/
│   │   ├── igdb_client.py
│   │   ├── igdb_importer.py
│   │   ├── igdb_normalizer.py
│   │   └── playthrough_state.py
│   ├── static/games/
│   ├── templates/games/
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── detail.html
│   │   ├── igdb_import.html
│   │   ├── igdb_search.html
│   │   └── library.html
│   ├── web/
│   │   ├── dashboard.py
│   │   ├── detail.py
│   │   ├── igdb.py
│   │   └── library.py
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
│   │   ├── dashboard.py
│   │   ├── library.py
│   │   ├── relations.py
│   │   ├── search.py
│   │   ├── seasonal.py
│   │   └── sync.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   └── urls.py
│
├── templates/
│   ├── registration/
│   ├── mal_data/
│   └── base.html
│
├── docs/
│   └── game-kiroku-data-model.md
│
├── manage.py
├── requirements.txt
└── README.md
```

The technical Django app name `mal_data` is intentionally preserved to avoid unnecessary migration and database table changes. Its public module name is **MAL Insights**.

Watchroom, Music, and Hibi Log do not yet have Django apps. Their selector cards define the platform roadmap without introducing unused database structures.

## Environment Variables

Create a `.env` file in the project root.

```env
SECRET_KEY=your-django-secret-key
DEBUG=True
DATABASE_URL=postgresql://...
MAL_ACCESS_TOKEN=your-mal-access-token
IGDB_CLIENT_ID=your-twitch-client-id
IGDB_CLIENT_SECRET=your-twitch-client-secret
ALLOWED_HOSTS=127.0.0.1,localhost
```

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

## Running Tests

MVS Tracker uses an isolated SQLite in-memory database for automated tests.

```bash
python manage.py test \
  core \
  mal_data \
  games \
  --settings=config.test_settings \
  --verbosity=2
```

The test database is created and destroyed automatically. It does not modify Supabase.

At the current project checkpoint, the automated suite contains **89 passing tests**.

## Data Sources

### MyAnimeList

Primary source for personal anime and manga list data.

### AniList

Public metadata and discovery source for airing data, native titles, streaming links, seasonal anime, and search.

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
- [ ] Add platinum acquisition dates and a dedicated Platinum History view.
- [ ] Add a Platinum-only library filter.
- [ ] Add franchise views.
- [ ] Add manual competitive-rank tracking per game and mode.
- [ ] Expand game analytics.
- [ ] Connect Game Kiroku activity to Hibi Log.

### Watchroom

- [x] Define the module name and descriptor.
- [ ] Create the Django app.
- [ ] Define its media and library models.
- [ ] Build the Series & Movies library.
- [ ] Add progress and rewatch tracking.
- [ ] Connect activity to Hibi Log.

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

- [ ] Expand manga support.
- [ ] Add manga archive views.
- [ ] Explore chapter availability signals.
- [ ] Improve token renewal workflow.
- [ ] Improve entries without confirmed MAL IDs.

## Security

Never commit:

- `.env`
- Database credentials
- MAL access tokens
- IGDB client secrets
- API tokens
- Raw private API responses
- Local virtual environments
- Local database files
- Collected static output

## License

No license has been selected yet.
