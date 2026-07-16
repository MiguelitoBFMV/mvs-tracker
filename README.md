# MAL Insight Lab

MAL Insight Lab is a Django-based personal anime analytics dashboard built around MyAnimeList data, enriched with AniList metadata for airing schedules, episode signals, streaming links, and franchise discovery.

The project started as a personal MAL list viewer, but evolved into a command-center style tool for auditing anime progress, detecting missing franchise entries, tracking currently airing shows, and rescuing entries that may not appear correctly through the MyAnimeList list API.

## Current Status

This project is in active development.

The current version focuses on anime data. Manga support exists partially at the model level, but it is not the main focus yet.

## Main Features

- Sync anime lists from MyAnimeList by status:
  - Watching
  - Completed
  - On hold
  - Dropped
  - Plan to watch

- Command Center dashboard:
  - Anime totals by status
  - Backlog clear ratio
  - Latest sync events
  - Episode signals for currently watched anime
  - Broadcast watchlist for Plan to Watch anime that are currently airing
  - Sequel radar based on MAL relations
  - Manual resync flow

- AniList integration:
  - Airing status
  - Estimated aired episodes
  - Next airing episode
  - Time until next episode
  - Streaming links when available

- Relation Scan:
  - Direct anime and manga relations from MAL
  - Local status detection for related anime
  - Prioritized relation sorting
  - Useful for finding missing movies, OVAs, sequels, specials, and franchise gaps

- Search Anime / Rescue:
  - Search anime through AniList
  - Compare results against the local MAL archive
  - Rescue manually tracked anime entries
  - Useful when MAL web shows an anime in the list but the MAL API does not return it correctly

- Manual tracked anime:
  - Keeps rescued anime entries synchronized locally
  - Prevents edge cases from disappearing during normal MAL sync

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
├── config/                  # Django project settings
├── mal_data/                # Main Django app
│   ├── management/commands/ # Sync and inspection commands
│   ├── migrations/          # Database migrations
│   ├── services/            # MAL, AniList and sync services
│   ├── static/              # CSS
│   ├── admin.py
│   ├── models.py
│   ├── urls.py
│   └── views.py
├── templates/
│   ├── base.html
│   └── mal_data/            # Dashboard, archive, relation and search templates
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

Do not commit `.env`, access tokens, raw API responses, or local virtual environments.

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

Sync one MAL anime status:

```bash
python manage.py fetch_anime_status watching
python manage.py fetch_anime_status completed
python manage.py fetch_anime_status on_hold
python manage.py fetch_anime_status dropped
python manage.py fetch_anime_status plan_to_watch
```

Sync AniList airing data for dashboard targets:

```bash
python manage.py sync_airing_data --dashboard
```

Inspect AniList airing data for a specific MAL ID:

```bash
python manage.py inspect_airing_data 63832
```

Fetch or update relations for a specific anime:

```bash
python manage.py fetch_anime_relations 32182
```

Rescue an anime entry manually when MAL API does not return it correctly from the list endpoint:

```bash
python manage.py rescue_anime_entry 46488 --status watching --episodes-watched 1 --sync-airing
```

## Data Sources

MAL Insight Lab uses MyAnimeList as the main source for personal list data.

AniList is used as an external metadata source for airing information, next episode data, streaming links, native titles, and search support.

The project does not use AniList as the personal list source.

## Current Limitations

- Manga support is not fully implemented yet.
- External relation nodes that are not in the local MAL list do not have a dedicated metadata table yet.
- Some MyAnimeList API edge cases may require manual rescue.
- Streaming availability depends on what AniList exposes through external links.
- This is a local personal dashboard, not a deployed production app.

## Roadmap

Planned next steps:

- Add `AnimeMetadata` for public anime nodes outside the personal MAL list.
- Improve Relation Scan for non-local nodes.
- Add a personal seasonal / LiveChart-style view.
- Expand manga support.
- Build a franchise graph view.
- Improve search and rescue workflows.
- Add richer filtering for archives and relations.

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
