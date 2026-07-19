# MAL Insight Lab

MAL Insight Lab is a Django-based personal anime and manga analytics dashboard built around MyAnimeList data and enriched with AniList metadata.

The project started as a personal MAL list viewer, but evolved into a command-center style tool for auditing anime progress, tracking seasonal anime, detecting franchise gaps, monitoring episode signals, and managing Plan to Watch decisions directly from the app.

The current production build is deployed on Render and uses Supabase PostgreSQL as the shared database.

## Current Status

This project is in active development.

The current MVP focuses on **Anime Mode**, which is already functional and deployed as a personal production dashboard.

Anime Mode currently includes:

- Dashboard analytics.
- Episode Signals.
- Rewatch support.
- Seasonal discovery.
- Seasonal yearly `ALL` mode.
- TBA seasonal bucket.
- Relation scanning.
- Franchise auditing.
- Plan to Watch actions.
- AniList-powered metadata enrichment.
- Render deployment.
- Supabase PostgreSQL database.

Manga support exists partially at the model/admin level and is the next major module planned for development.

## Main Features

### Command Center Dashboard

The dashboard acts as the main anime control panel.

It includes:

- Anime totals by list status.
- Backlog clear ratio.
- Latest sync logs.
- Episode signals for active watching entries.
- Rewatch episode signals.
- Broadcast watchlist for Plan to Watch anime that are currently airing.
- Sequel Radar based on MyAnimeList relations.
- Manual resync flow for MAL, manual tracked entries, and AniList airing data.

### Episode Signals

Episode Signals use AniList airing data to estimate pending episodes.

They help detect:

- New aired episodes for currently watched anime.
- Long-running anime with accumulated pending episodes.
- Finished anime that still have unseen episodes.
- Rewatch entries with pending episodes.

Rewatch entries are included in the dashboard and Watching archive.

### Sequel Radar

Sequel Radar uses imported MyAnimeList relations to recommend relevant next entries.

It prioritizes:

1. Currently watching anime.
2. Rewatching anime.
3. Completed anime.

If an anime is being rewatched, completed sequels may still appear as natural rewatch-next candidates.

### Anime Archive

The archive includes list views for:

- All Anime
- Watching
- Completed
- Plan to Watch
- On Hold
- Dropped

The All Anime view supports multi-status filtering, allowing multiple list states to be enabled or disabled at once.

The archive also includes filters by airing status:

- All
- Finished
- Airing
- Queued

The Watching archive also includes rewatching entries.

### Relation Scan

Relation Scan imports anime and manga relations from MyAnimeList.

It is useful for franchise auditing and finding missing related entries such as:

- Sequels
- Prequels
- Movies
- OVAs
- Specials
- Side stories
- Alternative versions
- Summary episodes
- Character specials
- Low-priority extras

Related anime are classified by local status, external metadata availability, and priority.

### Franchise Audit

Each Relation Scan page includes a Franchise Audit section that groups related anime into:

- Local Priority
- Local Completed
- External Priority
- Low Priority / Extras
- Unknown Nodes

The Franchise Audit can be collapsed or expanded from the relation page.

### External Anime Metadata

The app stores public metadata for anime that are not in the local MAL list.

This allows non-local relation nodes to show better information, including:

- Title
- Cover image
- Media type
- Airing status
- Episode count

### Search / Rescue

Search Anime uses AniList search to find anime candidates and compare them with the local MAL archive.

It helps with:

- Finding anime by title.
- Opening local nodes.
- Detecting whether an anime is already in the local database.
- Rescuing entries that MAL web may show but the MAL list API does not return correctly.

Manual rescue is used for edge cases where a MAL entry needs to be tracked locally.

### Seasonal Board

Seasonal Board is a LiveChart-style personal seasonal anime view powered by AniList data.

It supports:

- Viewing anime by specific season and year.
- Viewing all seasons for a selected year using Season `ALL`.
- Filtering by format.
- Filtering by local status.
- Sorting by countdown or title.
- Comparing AniList seasonal entries against the local MAL archive.
- Showing whether an anime is local, not local, watching, rewatching, completed, or Plan to Watch.
- Adding seasonal anime directly to the official MyAnimeList Plan to Watch list.
- Syncing local data after adding an anime to MAL.
- Tracking announced anime without a confirmed season through a provisional TBA yearly bucket.

This makes Seasonal Board useful as a personal discovery and planning tool.

## Tech Stack

- Python
- Django
- PostgreSQL
- Supabase PostgreSQL
- Render
- MyAnimeList API v2
- AniList GraphQL API
- HTML
- CSS
- python-dotenv
- requests
- dj-database-url
- gunicorn
- WhiteNoise

## Project Structure

```text
mal-insight-lab/
├── config/                         # Django project settings
├── mal_data/                       # Main Django app
│   ├── management/commands/        # Sync and inspection commands
│   ├── migrations/                 # Database migrations
│   ├── services/                   # MAL, AniList and sync services
│   ├── static/mal_data/css/        # App CSS
│   ├── admin.py
│   ├── models.py
│   ├── urls.py
│   └── views.py
├── templates/
│   ├── base.html
│   └── mal_data/                   # Dashboard, archive, relation, search and seasonal templates
├── manage.py
├── requirements.txt
└── README.md
```

## Environment Variables

Create a `.env` file in the project root.

### Local PostgreSQL setup

```env
SECRET_KEY=your-django-secret-key
DEBUG=True

DB_NAME=mal_insight_lab
DB_USER=mal_user
DB_PASSWORD=your-db-password
DB_HOST=localhost
DB_PORT=5432

MAL_ACCESS_TOKEN=your-mal-access-token
```

### Supabase / production-style local setup

When working locally against Supabase, use:

```env
SECRET_KEY=your-django-secret-key
DEBUG=True

DATABASE_URL=postgresql://...

MAL_ACCESS_TOKEN=your-mal-access-token
```

When `DATABASE_URL` is present, Django uses it instead of the local `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT` variables.

### Render deployment variables

Render requires:

```env
SECRET_KEY=your-production-secret-key
DEBUG=False
DATABASE_URL=postgresql://...
MAL_ACCESS_TOKEN=your-mal-access-token
ALLOWED_HOSTS=your-app.onrender.com
CSRF_TRUSTED_ORIGINS=https://your-app.onrender.com
```

Do not commit `.env`, access tokens, raw API responses, local databases, or virtual environments.

## Local Setup

Clone the repository:

```bash
git clone https://github.com/MiguelitoBFMV/mal-insight-lab.git
cd mal-insight-lab
```

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create the PostgreSQL database and user according to your local setup.

Run migrations:

```bash
python manage.py migrate
```

Start the development server:

```bash
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

## Deployment

The project is deployed on Render as a Python web service.

Recommended Render commands:

### Build Command

```bash
pip install -r requirements.txt && python manage.py collectstatic --noinput
```

### Start Command

```bash
python manage.py migrate && gunicorn config.wsgi:application
```

The production database is hosted on Supabase PostgreSQL.

For heavy sync jobs, it is recommended to run local management commands while pointing local `.env` to the Supabase `DATABASE_URL`, instead of running large sync operations from Render Free.

## Useful Commands

### Sync anime from MyAnimeList

```bash
python manage.py fetch_anime_status watching
python manage.py fetch_anime_status completed
python manage.py fetch_anime_status on_hold
python manage.py fetch_anime_status dropped
python manage.py fetch_anime_status plan_to_watch
```

### Sync AniList airing data

```bash
python manage.py sync_airing_data --dashboard
```

### Inspect AniList airing data for a MAL ID

```bash
python manage.py inspect_airing_data 63832
```

### Fetch or update relations for an anime

```bash
python manage.py fetch_anime_relations 32182
```

### Rescue a manually tracked anime

Useful when MAL web shows an anime in the list but the MAL list API does not return it correctly.

```bash
python manage.py rescue_anime_entry 46488 --status watching --episodes-watched 1 --sync-airing
```

### Sync a seasonal anime board

```bash
python manage.py sync_seasonal_anime SUMMER 2026
```

### Sync multiple seasonal years from local against Supabase

```bash
for year in 2023 2024 2025 2026 2027; do
  for season in WINTER SPRING SUMMER FALL; do
    echo "Syncing $season $year..."
    python manage.py sync_seasonal_anime "$season" "$year"
    sleep 3
  done
done
```

### Sync provisional TBA seasonal bucket

```bash
python manage.py shell -c "from mal_data.services.seasonal_sync import sync_tba_upcoming_anime; print(sync_tba_upcoming_anime(2027))"
```

## Data Sources

MAL Insight Lab uses MyAnimeList as the main source for personal list data.

AniList is used as an external metadata source for:

- Airing information.
- Next episode data.
- Estimated aired episodes.
- Streaming links.
- Native titles.
- Seasonal anime data.
- Search support.
- TBA upcoming anime support.

AniList is not used as the personal list source.

## Local and Production Workflow

The project can be used in two local modes.

### Local development mode

Use local PostgreSQL when testing risky changes, model changes, migrations, or experimental development.

```env
# DATABASE_URL disabled
DB_NAME=mal_insight_lab
DB_USER=mal_user
DB_PASSWORD=your-db-password
DB_HOST=localhost
DB_PORT=5432
```

### Production data mode

Use Supabase `DATABASE_URL` locally when running heavy sync jobs or rebuilding production data.

```env
DATABASE_URL=postgresql://...
```

In this mode, local commands write directly to the production Supabase database used by Render.

General rule:

- Code changes: local development → commit → push → Render deploy.
- Heavy data sync: local terminal → Supabase database → visible in Render.
- Risky schema changes: test locally first, then deploy.

## Current Limitations

- Manga Mode is not fully implemented yet.
- Heavy sync actions may timeout or be killed on Render Free, so large sync jobs should be run locally against Supabase.
- Manual Resync is useful but may be too heavy for production usage on the free tier.
- Some MyAnimeList API edge cases may still require manual rescue.
- Streaming availability depends on what AniList exposes through external links.
- MAL access tokens may expire and currently need to be refreshed manually.
- Seasonal entries without MAL IDs cannot be added to Plan to Watch until a MAL ID is available or manually rescued.

## Roadmap

Planned next steps:

- Build Manga Mode as a separate archive/world.
- Add Manga dashboard integration.
- Add Reading / Plan to Read / Completed manga views.
- Add manga sync from MyAnimeList.
- Explore Chapter Signals for currently reading manga.
- Build Anime ↔ Manga bridge views.
- Add Calendar Hub for anime episodes, manga releases, and news events.
- Add lightweight news/embed module.
- Improve production-safe background jobs for heavy sync operations.
- Improve Seasonal MAL ID rescue for entries missing MyAnimeList IDs.

## Security Notes

This project uses API tokens and database credentials through environment variables.

Never commit:

- `.env`
- `tokens.json`
- raw API dumps
- local virtual environments
- private credentials
- collected static output

## License

No license has been selected yet.
