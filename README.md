# MAL Insight Lab

MAL Insight Lab is a Django-based personal anime analytics dashboard built around MyAnimeList data and enriched with AniList metadata.

The project started as a personal MAL list viewer, but evolved into a command-center style tool for auditing anime progress, tracking seasonal anime, detecting franchise gaps, monitoring episode signals, and managing Plan to Watch decisions directly from the app.

## Current Status

This project is in active development.

The current MVP focuses on anime. Manga support exists partially at the model and sync level, but it is not the main active module yet.

Current anime features are functional enough to be used as a personal local dashboard.

## Main Features

### Command Center Dashboard

The dashboard acts as the main anime control panel.

It includes:

- Anime totals by list status.
- Backlog clear ratio.
- Latest sync logs.
- Episode signals for active watching entries.
- Rewatch episode signals shown after regular watching items.
- Broadcast watchlist for Plan to Watch anime that are currently airing.
- Sequel radar based on MAL relations.
- Manual resync flow for MAL, manual tracked entries, and AniList airing data.

### Episode Signals

Episode Signals use AniList airing data to estimate pending episodes.

They help detect:

- New aired episodes for currently watched anime.
- Long-running anime with accumulated pending episodes.
- Finished anime that still have unseen episodes.
- Rewatch entries with pending episodes.

Rewatch entries are included, but sorted after regular watching signals.

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

It currently supports:

- Viewing anime by season and year.
- Filtering by format.
- Filtering by local status.
- Comparing AniList seasonal entries against the local MAL archive.
- Showing whether an anime is local, not local, watching, completed, or Plan to Watch.
- Adding seasonal anime directly to the official MyAnimeList Plan to Watch list.
- Syncing local data after adding an anime to MAL.

This makes Seasonal Board useful as a personal discovery and planning tool.

## Tech Stack

- Python
- Django
- PostgreSQL
- MyAnimeList API v2
- AniList GraphQL API
- HTML
- CSS
- python-dotenv
- requests

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

## Data Sources

MAL Insight Lab uses MyAnimeList as the main source for personal list data.

AniList is used as an external metadata source for:

- Airing information
- Next episode data
- Estimated aired episodes
- Streaming links
- Native titles
- Seasonal anime data
- Search support

AniList is not used as the personal list source.

## Current Limitations

- Manga support is not fully implemented yet.
- Seasonal Board currently works by specific season and year; yearly ALL-season views are planned next.
- Seasonal sorting by countdown/title is planned.
- Some MyAnimeList API edge cases may still require manual rescue.
- Streaming availability depends on what AniList exposes through external links.
- This is a local personal dashboard, not a deployed production app.

## Roadmap

Planned next steps:

- Add Season `ALL` mode for Seasonal Board.
- Add contextual Seasonal Board sync:
  - Single season sync when a specific season is selected.
  - Full year sync when Season is set to `ALL`.
- Add Seasonal sorting by countdown and title.
- Improve Seasonal discovery filters.
- Add a dedicated Episode Signals page.
- Expand manga support.
- Build Anime ↔ Manga bridge views.
- Improve admin styling or add internal navigation.
- Add richer filtering for archives, relations, and seasonal views.

## Security Notes

This project uses API tokens and database credentials through environment variables.

Never commit:

- `.env`
- `tokens.json`
- raw API dumps
- local virtual environments
- private credentials

## License

No license has been selected yet.
