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

The application currently runs locally and uses Supabase PostgreSQL as its shared database.

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

Game Kiroku is the video game library and playthrough-tracking module.

Current features include:

- Local game library stored in Supabase PostgreSQL.
- Owned and wishlist access records.
- Playing, paused, dropped, completed, Plan to Play, and multiplayer states.
- Platform and storefront selectors.
- Manual franchise grouping.
- Multiple playthroughs per game.
- Text language per playthrough.
- Optional progress, dates, notes, and hours.
- Main-story duration with manual override support.
- Platinum indicator at library-entry level.
- Replay-aware completion analytics.
- Completion analytics that exclude persistent multiplayer games.
- Dynamic dashboard with real library data.
- Public library with search and filters.
- Shared authentication and public read-only access.
- Automated route, permission, model, dashboard, and library tests.

IGDB integration is planned as an explicit import and enrichment workflow. Imported metadata will be stored locally instead of being requested whenever a page loads.

Routes:

```text
/games/
/games/library/
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
/                    MVS Tracker module selector
/accounts/login/     Owner login
/accounts/logout/    Owner logout
/anime/              MAL Insights
/games/              Game Kiroku dashboard
/games/library/      Game Kiroku library
/watchroom/          Watchroom — planned
/music/              Music — planned
/activity/           Hibi Log — planned
/admin/              Django administration
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
- IGDB — planned
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
│   ├── static/games/
│   ├── templates/games/
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   └── library.html
│   ├── web/
│   │   ├── dashboard.py
│   │   └── library.py
│   ├── admin.py
│   ├── apps.py
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

## Data Sources

### MyAnimeList

Primary source for personal anime and manga list data.

### AniList

Public metadata and discovery source for airing data, native titles, streaming links, seasonal anime, and search.

### IGDB

Planned primary metadata source for Game Kiroku. Imported metadata will be stored locally.

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
- [x] Define library and playthrough models.
- [x] Add the Game Kiroku admin.
- [x] Build the dynamic dashboard.
- [x] Build the searchable and filterable library.
- [x] Add wishlist and access modeling.
- [x] Add platinum tracking at library-entry level.
- [x] Add replay-aware completion analytics.
- [ ] Add the individual game detail page.
- [ ] Add owner editing controls.
- [ ] Integrate IGDB metadata imports.
- [ ] Add franchise views.
- [ ] Expand game analytics.

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
- API tokens
- Raw private API responses
- Local virtual environments
- Local database files
- Collected static output

## License

No license has been selected yet.
