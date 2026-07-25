# Watchroom — MVP Data Model and Architecture

This document describes the approved MVP architecture and the current implemented public foundation for **Watchroom — Series & Movies** inside MVS Tracker.

Watchroom combines:

- MAL-style lightweight progress.
- Game Kiroku-style separation between work metadata and personal history.
- Local-first external metadata.
- Public read-only access.
- Authenticated owner management.
- Movie- and series-specific rules where needed.

The module is now operational through `watchroom.0004`. Its public dashboard, library, and work-detail views are implemented, and the Watchroom regression suite contains **43 passing tests**. Owner write workflows and TMDB integration remain pending.

---

## 1. MVP Scope

Watchroom tracks western and non-anime audiovisual works such as:

- Live-action series.
- Cartoons and western animation.
- Movies.
- Documentary films.
- Documentary series.
- Miniseries.
- Streaming and television productions.

Examples include:

- *Phineas and Ferb*.
- *The Amazing World of Gumball*.
- *Kick Buttowski*.
- *Wizards of Waverly Place*.
- *Saw*.
- *The Purge*.
- *Alice in Borderland* as live action.

Anime and manga remain in MAL Insights.

---

## 2. Core Behaviour Types

Watchroom has only two behaviour types:

```text
movie
series
```

These determine progress behaviour.

### Movie

A movie:

- Has no seasons.
- Uses `ViewingRun` history.
- May optionally store progress in minutes.
- Can be completed, paused, dropped, or rewatched.

### Series

A series:

- Has seasons.
- Uses MAL-style aggregated progress.
- Does not store one database row per watched episode.
- Uses `SeasonProgress` values such as `12 / 38`.
- Can be completed, paused, dropped, or rewatched.

---

## 3. Presentation Classification

Presentation is separate from behaviour type.

```text
animation
live_action
documentary
mixed
other
```

Examples:

```text
Phineas and Ferb
Type: Series
Presentation: Animation

Phineas and Ferb the Movie:
Across the 2nd Dimension
Type: Movie
Presentation: Animation

Saw
Type: Movie
Presentation: Live Action

Documentary film
Type: Movie
Presentation: Documentary

Documentary series
Type: Series
Presentation: Documentary
```

Labels such as TV Movie, Direct-to-Video, or Streaming Original may remain inside imported metadata, but they do not create separate progress systems.

---

## 4. External Metadata Strategy

Primary source:

```text
TMDB
```

Storage strategy:

```text
Local-first
```

Normal page rendering uses local PostgreSQL data only.

External requests occur only through explicit owner actions:

```text
Search TMDB
Review result
Import locally
Link existing work
Refresh metadata
Refresh seasons
```

A normal dashboard, library, or detail request must not contact TMDB.

At the current checkpoint, the local-first read path is implemented. The TMDB client, search, import, linking, and refresh services are still pending.

### Attribution

The required TMDB attribution will be displayed in the Watchroom or global footer.

Cards, dashboards, and work-detail sections will not carry repeated attribution text.

---

## 5. Conceptual Model

```text
MediaWork
├── WatchEntry
│   └── ViewingRun
│       └── SeasonProgress
└── Season
```

### Entity Responsibilities

```text
MediaWork
    Stores local metadata for one movie or series.

WatchEntry
    Stores the user's personal relationship with the work.

ViewingRun
    Stores one first watch or rewatch attempt.

Season
    Stores season-level metadata and canonical episode totals.

SeasonProgress
    Stores lightweight MAL-style progress for one season
    inside one viewing run.
```

All five models in the conceptual graph are implemented.

Watchroom does not require these MVP models:

```text
Episode
EpisodeWatch
EpisodeSegment
```

---

## 6. MediaWork

`MediaWork` represents a movie or series as a work.

Personal progress and status do not belong here.

### Implemented Fields

| Field | Type | Nullable / blank | Description |
|---|---|---:|---|
| `tmdb_id` | `PositiveBigIntegerField` | Yes | External TMDB identifier. |
| `media_type` | `CharField` | No | Movie or Series. |
| `title` | `CharField` | No | Primary local title. |
| `original_title` | `CharField` | Yes | Original-language title. |
| `slug` | `SlugField` | No | Stable local identifier. |
| `overview` | `TextField` | Yes | Locally stored synopsis. |
| `presentation` | `CharField` | No | Animation, Live Action, Documentary, Mixed, or Other. |
| `original_language` | `CharField` | Yes | Original language code. |
| `first_release_date` | `DateField` | Yes | Release date or first-air date. |
| `runtime_minutes` | `PositiveIntegerField` | Yes | Movie runtime. |
| `external_status` | `CharField` | Yes | Imported TMDB status. |
| `poster_url` | `URLField` | Yes | Vertical poster. |
| `backdrop_url` | `URLField` | Yes | Horizontal background. |
| `genres` | `JSONField` | Yes | Imported genres. |
| `origin_countries` | `JSONField` | Yes | Imported origin countries. |
| `networks` | `JSONField` | Yes | Imported networks or platforms. |
| `tmdb_payload` | `JSONField` | Yes | Stored relevant TMDB payload. |
| `tmdb_synced_at` | `DateTimeField` | Yes | Last explicit metadata refresh. |
| `created_at` | `DateTimeField` | No | Local creation timestamp. |
| `updated_at` | `DateTimeField` | No | Last modification timestamp. |

### Media Type Choices

```text
movie
series
```

### Presentation Choices

```text
animation
live_action
documentary
mixed
other
```

### Date Meaning

`first_release_date` is shared by both work types.

```text
Movie
→ Release Date

Series
→ First Aired
```

There is no separate `last_release_date` field in the MVP.

Series completion or continuation state is represented by `external_status`.

### Runtime Rules

- Movies may use `runtime_minutes`.
- Series do not use a universal runtime in the MVP.
- A movie runtime must be positive when present.
- A series should keep `runtime_minutes=None`.

### External-ID Rule

TMDB movie and television IDs belong to separate namespaces.

The unique external identity is:

```text
media_type + tmdb_id
```

A manual local work may exist without a TMDB ID.

### Slug Rule

- `slug` is globally unique.
- It is generated when the work is created.
- It remains stable after visible title edits.
- `get_absolute_url()` resolves to the public Watchroom detail route.

---

## 7. WatchEntry

`WatchEntry` represents the user's personal relationship with one `MediaWork`.

Each work can have at most one watch entry.

### Personal Statuses

```text
plan_to_watch
watching
paused
dropped
completed
```

### Implemented Fields

| Field | Type | Nullable / blank | Description |
|---|---|---:|---|
| `media_work` | `OneToOneField` | No | Associated work. |
| `status` | `CharField` | No | General personal status. |
| `notes` | `TextField` | Yes | Personal notes. |
| `created_at` | `DateTimeField` | No | Date added to Watchroom. |
| `updated_at` | `DateTimeField` | No | Last personal change. |

### Status Semantics

The library status represents the historical relationship with the work.

Examples:

```text
Never started
→ Plan to Watch

First watch active
→ Watching

First watch paused
→ Paused

First watch abandoned
→ Dropped

At least one completed run
→ Completed
```

A rewatch does not remove the historical Completed state.

```text
Run 1 completed
Run 2 watching

Library status:
Completed

Current activity:
Rewatching
```

Dropping a rewatch does not convert the full entry to Dropped.

---

## 8. ViewingRun

`ViewingRun` represents one first watch or rewatch.

### Run Statuses

```text
watching
paused
completed
dropped
```

### Implemented Fields

| Field | Type | Nullable / blank | Description |
|---|---|---:|---|
| `watch_entry` | `ForeignKey` | No | Parent personal entry. |
| `number` | `PositiveIntegerField` | No | Sequential watch number. |
| `status` | `CharField` | No | Current run status. |
| `started_on` | `DateField` | Yes | Optional start date. |
| `finished_on` | `DateField` | Yes | Optional finish date. |
| `progress_minutes` | `PositiveIntegerField` | Yes | Optional movie progress. |
| `notes` | `TextField` | Yes | Context or impressions. |
| `created_at` | `DateTimeField` | No | Creation timestamp. |
| `updated_at` | `DateTimeField` | No | Last modification timestamp. |

### Numbering

```text
Run 1
→ First watch

Run 2
→ First rewatch

Run 3
→ Second rewatch
```

`number` is unique within one `WatchEntry`.

### Active-Run Rule

A work may have at most one active run.

Active statuses:

```text
watching
paused
```

Starting a new active run should not silently coexist with another active run.

### Date Rules

- `finished_on >= started_on` when both exist.
- Completion dates remain optional for historical entries.
- A Watching or Paused run should not keep a finish date.

### Movie Progress

`progress_minutes` is only valid for movies.

Example:

```text
Saw
Run 1
Status: Paused
Progress: 54 minutes
```

Rules:

- Must be positive when present.
- Must be null for series.
- Should not exceed the known movie runtime when runtime is available.
- Completing a movie may clear or normalise partial-minute progress.

### Series Runs

Series progress is stored through `SeasonProgress`, not `progress_minutes`.

---

## 9. Season

`Season` exists only for series.

### Implemented Fields

| Field | Type | Nullable / blank | Description |
|---|---|---:|---|
| `media_work` | `ForeignKey` | No | Parent series. |
| `tmdb_id` | `PositiveBigIntegerField` | Yes | External TMDB season identifier. |
| `season_number` | `PositiveIntegerField` | No | Canonical source number. |
| `name` | `CharField` | Yes | Visible season name. |
| `episode_count` | `PositiveIntegerField` | No | Canonical source total. |
| `air_date` | `DateField` | Yes | Season air date. |
| `poster_url` | `URLField` | Yes | Optional season poster. |
| `tmdb_payload` | `JSONField` | Yes | Stored relevant season payload. |
| `created_at` | `DateTimeField` | No | Creation timestamp. |
| `updated_at` | `DateTimeField` | No | Last modification timestamp. |

### Rules

The following combination is unique:

```text
media_work + season_number
```

Additional rules:

- The parent work must be a series.
- `episode_count >= 0`.
- Imported numbering is preserved.
- Watchroom does not manually split double-segment cartoon episodes.

### Canonical Episode Rule

The progress unit is the episode exactly as represented by the source catalogue.

Example:

```text
Season 1 · Episode 14
Two 11-minute segments
One 22-minute catalogue episode
```

Watchroom records:

```text
14 / 38
```

It does not create:

```text
14A
14B
```

unless the external source itself treats them as independent episodes.

### Specials

```text
season_number == 0
→ Specials
```

Specials are:

- Imported and stored.
- Displayed separately.
- Excluded from ordinary completion totals by default.
- Available for manual progress when the owner chooses to track them.

No separate `is_special` database field is required in the MVP.

---

## 10. SeasonProgress

`SeasonProgress` stores aggregated series progress inside one viewing run.

### Implemented Fields

| Field | Type | Nullable / blank | Description |
|---|---|---:|---|
| `viewing_run` | `ForeignKey` | No | Parent first watch or rewatch. |
| `season` | `ForeignKey` | No | Associated season. |
| `episodes_watched` | `PositiveIntegerField` | No | MAL-style watched count. |
| `started_on` | `DateField` | Yes | Optional season start date. |
| `finished_on` | `DateField` | Yes | Optional season finish date. |
| `created_at` | `DateTimeField` | No | Creation timestamp. |
| `updated_at` | `DateTimeField` | No | Last modification timestamp. |

### Unique Rule

```text
viewing_run + season
→ unique
```

### Validation

- The season and run must belong to the same `MediaWork`.
- The parent work must be a series.
- `0 <= episodes_watched <= season.episode_count`.
- `finished_on >= started_on` when both exist.
- A completed season may keep an unknown finish date.
- A movie run cannot have `SeasonProgress`.

### Example

```text
Phineas and Ferb
Run 1

Season 1    38 / 38
Season 2    14 / 36
Season 3     0 / 35
```

Derived total:

```text
52 / 109 episodes
```

Specials are excluded from this ordinary total.

### Rewatch Example

```text
Run 1
Season 1    38 / 38
Season 2    36 / 36

Run 2
Season 1    12 / 38
```

The second run does not overwrite the first.

---

## 11. Derived Progress States

### Movie

A movie may display:

```text
Plan to Watch
Watching
Paused
Dropped
Completed
Rewatching
Rewatch Paused
```

`Rewatching` and `Rewatch Paused` are derived activity labels, not database status choices on `WatchEntry`.

### Series

A series may display:

```text
12 / 38
52 / 109
Up to Date
1 episode behind
Ready to complete
Rewatching
```

### Up to Date

For an active series run:

```text
watched non-special episodes
==
currently imported non-special episode total
```

This produces `Up to Date`.

When a TMDB refresh changes the total:

```text
12 / 12
→ Up to Date

refresh adds one episode

12 / 13
→ 1 episode behind
```

Watchroom should not silently mark a series Completed after metadata refresh.

Completion remains an explicit owner action.

---

## 12. Import and Refresh Workflow

### Search and Import

```text
Search TMDB
        ↓
Choose Movie or Series result
        ↓
Review title and metadata
        ↓
Choose initial personal status
        ↓
Save MediaWork locally
        ↓
Create WatchEntry
        ↓
When Series:
import Season summaries
```

### Link Existing Local Work

```text
Select TMDB result
        ↓
Select local work without TMDB identity
        ↓
Update metadata
        ↓
Preserve slug, WatchEntry,
ViewingRuns, SeasonProgress, and notes
```

### Refresh Work

An explicit owner refresh may update:

- Title.
- Original title.
- Overview.
- First release date.
- External status.
- Poster.
- Backdrop.
- Genres.
- Origin countries.
- Networks.
- Stored TMDB payload.
- Sync timestamp.

### Refresh Seasons

An explicit owner season refresh may:

- Create missing seasons.
- Update season names.
- Update canonical episode totals.
- Update air dates.
- Update season posters.
- Preserve local `SeasonProgress`.

A refresh must not:

- Delete personal history.
- Lower `episodes_watched` silently.
- Renumber local runs.
- Mark the work Completed automatically.
- Split or merge local progress without an explicit migration rule.

When a refreshed episode total becomes lower than existing progress, the operation must surface a conflict for owner review instead of corrupting progress.

---

## 13. Current Public Read Architecture

The public views share a common optimized read layer under `watchroom/web/common.py`.

It:

- Uses `select_related()` for `MediaWork`.
- Prefetches seasons, viewing runs, and season progress.
- Detects active rewatches with an `Exists` annotation.
- Derives current run, display run, run count, and activity labels.
- Derives movie-minute progress.
- Sums non-special episode totals for series.
- Derives current season progress and overall progress.
- Derives `Up to Date` without writing to the database.

The web layer is modularized as:

```text
watchroom/web/
├── common.py
├── dashboard.py
├── detail.py
└── library.py
```

Normal GET requests remain read only.

---

## 14. Database Constraints

Implemented constraints include:

- Unique `MediaWork.slug`.
- Unique `MediaWork(media_type, tmdb_id)` when `tmdb_id` is present.
- One `WatchEntry` per `MediaWork`.
- Positive movie runtime when present.
- Unique `ViewingRun(watch_entry, number)`.
- Positive viewing-run number.
- Valid viewing-run date range.
- At most one active run per `WatchEntry`.
- Positive movie progress when present.
- Unique `Season(media_work, season_number)`.
- Unique `SeasonProgress(viewing_run, season)`.
- Valid SeasonProgress date range.
- Non-negative `episodes_watched`.

Cross-model limits such as `episodes_watched <= episode_count` remain model/form validation because they depend on another row.

---

## 15. Owner and Public Access

Public visitors may:

- View the Watchroom dashboard.
- Browse the library.
- Open work details.
- View progress and watch history.
- View seasons and aggregate progress.

The authenticated owner will eventually be able to:

- Search TMDB.
- Import or link works.
- Refresh metadata.
- Refresh seasons.
- Edit personal status.
- Create or update viewing runs.
- Update season progress.
- Add notes.
- Delete eligible local records.

The public read paths above are implemented. The owner forms and mutating endpoints listed below are still pending.

When implemented, mutating endpoints require:

```text
login
POST
CSRF
```

Normal GET requests remain read-only.

---

## 16. Routes

### Implemented Public Routes

```text
/watchroom/                         Dashboard
/watchroom/library/                 Library
/watchroom/library/<slug>/          Work detail
```

These routes are publicly accessible and read only.

### Planned Owner Routes

Owner actions will use nested work-detail routes where practical.

Examples:

```text
/watchroom/search/
/watchroom/import/<media_type>/<tmdb_id>/
/watchroom/library/<slug>/entry/update/
/watchroom/library/<slug>/runs/create/
/watchroom/library/<slug>/runs/<id>/update/
/watchroom/library/<slug>/seasons/refresh/
/watchroom/library/<slug>/progress/<season_id>/update/
```

Final owner route names may be adjusted during implementation.

---

## 17. Implemented Public Dashboard

The dashboard is available at `/watchroom/`.

Current metrics:

- Total works.
- Watching.
- Completed.
- Plan to Watch.
- Movies.
- Series.

Current sections:

- Now Watching.
- Recently Updated.
- Empty states for a new library.
- Owner or read-only access state.
- TMDB attribution footer.

The dashboard uses local PostgreSQL data and shared prefetched query helpers. It does not require episode-level rows or external API requests.

Example card state:

```text
Phineas and Ferb
Watching
Season 1 · 12 / 38
```

---

## 18. Implemented Public Library and Detail Views

The library is available at `/watchroom/library/`.

Implemented search and filters:

```text
Title or original title
Movie or Series
Personal status
Presentation
Active rewatch
```

Implemented ordering:

```text
Title
Recently Updated
Newest Release
Oldest Release
```

Each library card shows:

- Poster or local fallback initials.
- Type.
- Presentation.
- Title and optional original title.
- Synopsis preview.
- Derived activity state.
- Current progress.
- Viewing-run count.

The work-detail page shows:

- Poster and optional backdrop.
- Type, presentation, and imported external status.
- Release Date for movies or First Aired for series.
- Runtime for movies.
- Aggregate progress for series.
- Seasons and Season 0 / Specials.
- Current run progress.
- First-watch and rewatch history.
- Up to Date when the active run matches all imported non-special episodes.
- Public 404 behaviour for unknown slugs.

---

## 19. Decisions Outside the MVP

The initial MVP excludes:

- Per-episode database rows.
- Per-episode watch history.
- Episode-segment tracking.
- Automatic scrobbling.
- Streaming-provider synchronisation.
- Permanent background TMDB synchronisation.
- Multiple users.
- Ratings and reviews beyond personal notes.
- Cast and crew databases.
- Awards tracking.
- Subtitle or audio-language tracking.
- Exact playback-position synchronisation.
- Automatic Completed transitions after refresh.
- Separate progress engines for cartoons, documentaries, or miniseries.
- Separate TV Movie behaviour.
- Automatic franchise or collection modelling.

These may be added later only when they provide clear value.

---

## 20. Future Extensions

Possible post-MVP additions:

- Collections and franchises.
- Streaming availability for Chile.
- TMDB / JustWatch provider attribution.
- Favourite works.
- Personal ratings.
- Release-calendar views.
- Upcoming-season alerts.
- Cross-module Hibi Log activity.
- Watch-time analytics.
- MAL Insights and Watchroom combined viewing statistics.

---

## 21. Implementation Progress

```text
[x] Create Watchroom Django app
[x] Add public module routes and navigation
[x] Implement MediaWork and WatchEntry
[x] Implement Season
[x] Implement ViewingRun and SeasonProgress
[x] Add the public dashboard
[x] Add the public library and detail views
[x] Add dashboard, library, detail, and model tests
[x] Add the initial technical document
[ ] Add owner forms and write endpoints
[ ] Add local manual creation workflows
[ ] Add run transitions and progress editing
[ ] Add TMDB client and search
[ ] Add local TMDB import and linking
[ ] Add metadata and season refresh
[ ] Validate the interface with real imported data
[ ] Complete final hardening and documentation
```

---

## 22. Current Implementation Checkpoint

```text
Document: watchroom-data-model.md
Module: Watchroom
Stage: Public foundation
Status: Implemented on feat/watchroom-foundation
Current migration: watchroom.0004
Watchroom tests: 43 OK
Active routes: Dashboard, Library, Work Detail
Primary source: TMDB selected; integration pending
Storage strategy: Local-first
Progress style: MAL-like aggregate progress
History style: Game Kiroku-like ViewingRun history
Primary types: Movie and Series
Episode rows: Excluded
TMDB attribution: Footer
Next block: Owner forms and write workflows
```

This branch should remain separate from `main` until owner write workflows, real-data validation, and the next hardening checkpoint are complete.
