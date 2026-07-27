# Watchroom — MVP Data Model and Architecture

This document describes the completed MVP architecture for **Watchroom — Series & Movies** inside MVS Tracker.

Watchroom combines:

- MAL-style lightweight progress.
- Game Kiroku-style separation between work metadata and personal history.
- Local-first TMDB metadata.
- Public read-only access.
- Authenticated owner management.
- Movie- and series-specific rules.
- Local mixed-media franchises.
- Automatic TMDB movie-collection synchronization.

The module is operational through `watchroom.0006`. Its dashboard, library, work-detail views, franchise views, manual owner workflows, TMDB search and import, safe refresh, viewing history, aggregate progress, and collection synchronization are implemented.

Current regression checkpoint:

```text
Watchroom tests: 155 OK
Global tests: 314 OK
```

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
- Independent specials with their own catalogue identity.
- Related works grouped into franchises or movie collections.

Examples include:

- *Phineas and Ferb*.
- *Phineas and Ferb the Movie: Across the 2nd Dimension*.
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
Refresh metadata and seasons
Synchronize a movie collection
```

A normal dashboard, library, work-detail, or franchise request does not contact TMDB.

### Implemented TMDB Capabilities

- Bearer-token client authentication.
- Movie search.
- Television-series search.
- Movie details.
- Series details.
- Collection details.
- Search-result normalization.
- Movie, series, season, and collection normalization.
- Review-before-import workflow.
- Duplicate detection.
- Transactional import.
- Explicit safe refresh.
- Automatic movie-collection synchronization.

### Attribution

TMDB attribution is displayed in the Watchroom footer.

Cards, dashboards, work details, and franchise sections do not repeat the attribution text.

---

## 5. Conceptual Model

```text
Franchise
└── FranchiseMembership
    └── MediaWork
        ├── WatchEntry
        │   └── ViewingRun
        │       └── SeasonProgress
        └── Season
```

A `MediaWork` may belong to more than one franchise through `FranchiseMembership`.

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

Franchise
    Stores one local grouping of related works.

FranchiseMembership
    Connects a work to a franchise with position,
    role, and optional notes.
```

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

Series continuation state is represented by `external_status`.

### Runtime Rules

- Movies may use `runtime_minutes`.
- Series do not use a universal runtime in the MVP.
- A movie runtime must be positive when present.
- A series keeps `runtime_minutes=None`.

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

Starting a new active run pauses another active run when required by the service workflow.

### Date Rules

- `finished_on >= started_on` when both exist.
- Dates remain optional for historical entries.
- A Watching or Paused run does not keep a finish date.
- Owner forms can explicitly clear stored dates back to `NULL`.

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
- Must not exceed the known movie runtime when runtime is available.
- Completing a movie with a known runtime stores full runtime progress.

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
- Excluded from ordinary completion totals.
- Restored by refresh when they are removed locally but remain present in TMDB.
- Available for owner progress when the active run uses them.

No separate `is_special` database field is required.

---

## 10. SeasonProgress

`SeasonProgress` stores aggregated series progress inside one viewing run.

### Implemented Fields

| Field | Type | Nullable / blank | Description |
|---|---|---:|---|
| `viewing_run` | `ForeignKey` | No | Parent first watch or rewatch. |
| `season` | `ForeignKey` | No | Associated season. |
| `episodes_watched` | `PositiveIntegerField` | No | MAL-style watched count. |
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
- A movie run cannot have `SeasonProgress`.
- Start and finish dates belong to `ViewingRun`, not `SeasonProgress`.
- Only the active run is editable through owner season-progress controls.
- Completed historical run progress remains visible but read only.

### Example

```text
Phineas and Ferb
Run 1

Season 1    47 / 47
Season 2    66 / 66
Season 3    62 / 62
Season 4    39 / 48
```

Derived total:

```text
214 / 261 episodes
```

Specials are excluded from the ordinary total.

### Rewatch Example

```text
Run 1
Season 1    47 / 47
Season 2    66 / 66

Run 2
Season 1    12 / 47
```

The second run does not overwrite the first.

---

## 11. Franchise

`Franchise` represents a local grouping of related movies and series.

It supports both:

```text
Mixed local franchise
→ Phineas and Ferb series + movie + independent extras

TMDB movie collection
→ Saw + Saw II + Saw III + ...
```

### Implemented Fields

| Field | Type | Nullable / blank | Description |
|---|---|---:|---|
| `name` | `CharField` | No | Visible franchise name. |
| `slug` | `SlugField` | No | Stable unique local identifier. |
| `overview` | `TextField` | Yes | Franchise description. |
| `poster_url` | `URLField` | Yes | Vertical TMDB artwork or fallback metadata. |
| `backdrop_url` | `URLField` | Yes | Primary horizontal franchise image. |
| `tmdb_collection_id` | `PositiveBigIntegerField` | Yes | Unique TMDB movie-collection identity. |
| `tmdb_payload` | `JSONField` | Yes | Stored TMDB collection payload. |
| `tmdb_synced_at` | `DateTimeField` | Yes | Last collection synchronization. |
| `works` | `ManyToManyField` | Yes | Works connected through `FranchiseMembership`. |
| `created_at` | `DateTimeField` | No | Local creation timestamp. |
| `updated_at` | `DateTimeField` | No | Last modification timestamp. |

### Image Rule

```text
backdrop_url
→ Primary franchise artwork
→ Franchise index card
→ Franchise detail hero
→ Editable by the owner

poster_url
→ Auxiliary TMDB metadata
→ Fallback when no backdrop exists
```

The owner form exposes one manual image field:

```text
Background Image URL
→ backdrop_url
```

### Deletion Rule

A franchise can be deleted through the owner interface only when it has no memberships.

Deleting an empty franchise does not delete any `MediaWork`.

---

## 12. FranchiseMembership

`FranchiseMembership` connects one `MediaWork` to one `Franchise`.

### Implemented Fields

| Field | Type | Nullable / blank | Description |
|---|---|---:|---|
| `franchise` | `ForeignKey` | No | Parent franchise. |
| `media_work` | `ForeignKey` | No | Connected movie or series. |
| `position` | `PositiveIntegerField` | No | Manual or TMDB-derived order. |
| `role` | `CharField` | No | Relationship role. |
| `notes` | `TextField` | Yes | Optional membership context. |
| `created_at` | `DateTimeField` | No | Creation timestamp. |
| `updated_at` | `DateTimeField` | No | Last modification timestamp. |

### Role Choices

```text
main
spin_off
special
extra
other
```

### Rules

- One work appears at most once inside the same franchise.
- `position > 0`.
- A work may belong to multiple franchises.
- Removing a membership preserves both the franchise and the work.
- Deleting a work removes its memberships.
- Existing manual positions and roles are not overwritten by later TMDB collection synchronization.

---

## 13. Derived Progress States

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
214 / 261
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

A metadata refresh never marks a series Completed automatically.

An explicit owner season-progress update completes the active run when every known regular season reaches its canonical episode total. Season 0 / Specials do not participate in this completion rule.

---

## 14. Search and Import Workflow

### Search

```text
Owner opens Search TMDB
        ↓
Selects Movie or Series
        ↓
TMDB search runs explicitly
        ↓
Results are normalized
        ↓
Already imported works are marked locally
```

Searching does not write to the database.

### Review and Import

```text
Select Review & Import
        ↓
Fetch complete TMDB details
        ↓
When Movie:
fetch and normalize collection details when present
        ↓
Review metadata and seasons
        ↓
Choose presentation and initial personal status
        ↓
Transactional local import
```

Supported import statuses:

```text
plan_to_watch
completed
dropped
```

Watching and Paused are assigned through a `ViewingRun`.

### Imported Records

Every successful import creates:

```text
MediaWork
WatchEntry
```

A series also imports its season summaries.

A Completed movie creates a completed first run and uses the known runtime as full progress.

A Completed series creates a completed first run and full `SeasonProgress` for every known regular season. Specials remain excluded.

### Duplicate Protection

The importer rejects another work with the same:

```text
media_type + tmdb_id
```

The review route redirects to the existing local detail when the work is already imported.

---

## 15. Safe Refresh Workflow

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
- Movie runtime.
- Season names.
- Season episode totals.
- Season air dates.
- Season posters.
- Missing seasons.
- Movie-collection metadata and membership.

A refresh does not modify:

- Presentation selected by the owner.
- `WatchEntry.status`.
- Personal notes.
- `ViewingRun` history.
- Run dates.
- Movie progress.
- `SeasonProgress`.
- Local slugs.
- Existing manual franchise roles or positions.

### Runtime Protection

When TMDB returns a movie runtime lower than stored progress:

```text
Incoming runtime < maximum recorded movie progress
→ preserve local runtime
```

### Episode-Total Protection

When TMDB returns an episode total lower than stored progress:

```text
Incoming total < maximum stored SeasonProgress
→ preserve local episode total
```

### Missing-Season Rule

A refresh does not delete local seasons absent from the current TMDB response.

When TMDB returns a season that is missing locally, the season is created again. This includes Season 0 / Specials.

### Automatic Completion Rule

Refresh never completes a series automatically, even when refreshed totals match current progress.

Completion remains an explicit owner progress action.

---

## 16. Franchise and TMDB Collection Synchronization

TMDB movie collections and local franchises are related but not identical concepts.

### Automatic Movie Collection

When a movie belongs to a TMDB collection:

```text
Import or refresh movie
        ↓
Fetch collection details
        ↓
Create or reuse Franchise by tmdb_collection_id
        ↓
Update collection metadata
        ↓
Add movie as Main membership
        ↓
Use collection release order as position
```

Example:

```text
Saw Collection
1 · Saw
2 · Saw II
3 · Saw III
```

A second movie from the same collection reuses the existing `Franchise`.

### Mixed Local Franchise

TMDB movie collections do not connect television series and movies into one cross-media franchise.

That relationship is managed locally.

Example:

```text
Phineas and Ferb
1 · Phineas and Ferb · Main · Series
2 · Across the 2nd Dimension · Special · Movie
```

The owner can add, reorder, relabel, annotate, or remove memberships without changing the underlying library works.

---

## 17. Public Read Architecture

The public views share an optimized read layer under `watchroom/web/common.py`.

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
├── franchises.py
├── library.py
├── owner.py
└── tmdb.py
```

Service responsibilities are separated as:

```text
watchroom/services/
├── tmdb_client.py
├── tmdb_collections.py
├── tmdb_importer.py
├── tmdb_normalizer.py
├── tmdb_refresh.py
└── viewing.py
```

Normal GET requests remain read only. Owner mutations use authenticated POST endpoints and CSRF validation.

---

## 18. Database Constraints

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
- Non-negative `episodes_watched`.
- Unique `Franchise.slug`.
- Unique positive `Franchise.tmdb_collection_id` when present.
- Unique `FranchiseMembership(franchise, media_work)`.
- Positive franchise membership position.

Cross-model limits such as `episodes_watched <= episode_count` remain model/form validation because they depend on another row.

---

## 19. Owner and Public Access

Public visitors may:

- View the Watchroom dashboard.
- Browse and filter the library.
- Open work details.
- View seasons and aggregate progress.
- View first-watch and rewatch history.
- View completed historical progress.
- Browse the franchise index.
- Open franchise details and connected works.

The authenticated owner may:

- Create a local movie or series.
- Permanently delete a work and its local history.
- Edit personal status and notes before run history controls the entry.
- Add, edit, and safely delete eligible seasons.
- Start a first watch or rewatch.
- Pause, resume, complete, or drop an active run.
- Edit or clear run dates.
- Edit run notes and movie-minute progress.
- Update season progress for the active series run.
- Search TMDB.
- Review and import a TMDB work.
- Refresh imported metadata and seasons.
- Create and edit franchises.
- Add, edit, reorder, relabel, annotate, and remove franchise memberships.
- Delete an empty franchise.

Implemented mutating endpoints require:

```text
login
POST
CSRF
```

Normal GET requests remain read only.

---

## 20. Routes

### Public Routes

```text
/watchroom/                                         Dashboard
/watchroom/library/                                 Library
/watchroom/library/<slug>/                          Work detail
/watchroom/franchises/                              Franchise index
/watchroom/franchises/<slug>/                       Franchise detail
```

### Owner Work Routes

```text
/watchroom/library/create/
/watchroom/library/<slug>/delete/
/watchroom/library/<slug>/entry/update/
/watchroom/library/<slug>/seasons/create/
/watchroom/library/<slug>/seasons/<id>/update/
/watchroom/library/<slug>/seasons/<id>/delete/
/watchroom/library/<slug>/runs/create/
/watchroom/library/<slug>/runs/<id>/update/
/watchroom/library/<slug>/runs/<id>/<action>/
/watchroom/library/<slug>/runs/<id>/progress/<season_id>/update/
```

The run transition action supports:

```text
pause
resume
complete
drop
```

### Owner TMDB Routes

```text
/watchroom/search/
/watchroom/import/<media_type>/<tmdb_id>/
/watchroom/library/<slug>/tmdb/refresh/
```

### Owner Franchise Routes

```text
/watchroom/franchises/create/
/watchroom/franchises/<slug>/update/
/watchroom/franchises/<slug>/delete/
/watchroom/franchises/<slug>/members/add/
/watchroom/franchises/<slug>/members/<membership_id>/update/
/watchroom/franchises/<slug>/members/<membership_id>/remove/
```

---

## 21. Public Interface

### Dashboard

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

### Library

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

### Work Detail

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
- Connected franchises with role and position.
- Public 404 behaviour for unknown slugs.

### Franchise Index and Detail

The franchise index shows:

- Primary horizontal artwork from `backdrop_url`.
- Franchise name and overview.
- Movie, Series, Completed, and total-work counts.

The franchise detail shows:

- Background-image hero.
- Franchise summary metrics.
- Connected works in manual or TMDB-derived order.
- Work type, role, status, and membership notes.
- Owner controls only when authenticated.

---

## 22. Owner Workflows

### Manual Work Creation

The owner can create a local Movie or Series with:

- Title and optional original title.
- Presentation.
- Overview.
- Original language.
- Release Date / First Aired.
- Movie runtime.
- External status.
- Poster and backdrop URLs.
- Initial personal status and notes.

Watching and Paused cannot be selected before a viewing run exists.

Creating a historical Completed or Dropped work creates the corresponding first historical run.

### Work Deletion

The owner can permanently delete a work.

The deletion removes:

- `WatchEntry`.
- Seasons.
- Viewing runs.
- Season progress.
- Franchise memberships.

The franchise records themselves remain.

### Season Management

Series seasons can be:

- Created.
- Edited.
- Deleted when no progress references them.
- Protected when viewing history exists.

An episode total cannot be reduced below the highest stored progress for that season.

### Viewing Runs

A work can have at most one active run:

```text
watching
paused
```

The service layer:

- Assigns the next sequential run number.
- Synchronizes `WatchEntry.status`.
- Preserves Completed history during rewatches.
- Validates pause, resume, complete, and drop transitions.
- Completes movies with their known runtime.
- Requires full known regular-season progress before a series run can be completed.

### Season Progress

`SeasonProgress` contains only:

```text
viewing_run
season
episodes_watched
```

Run dates and notes remain on `ViewingRun`.

Saving full progress for every known regular season through an explicit owner action completes the active run. Specials remain independent.

Completed historical progress is displayed but cannot be edited until a new rewatch run begins.

### Franchise Management

The owner can:

- Create a local franchise.
- Edit its name, overview, and primary background image.
- Add any local movie or series.
- Set position.
- Set role.
- Add membership notes.
- Update existing memberships.
- Remove a work without deleting it.
- Delete the franchise after every membership is removed.

---

## 23. Decisions Outside the MVP

The completed MVP excludes:

- Per-episode database rows.
- Per-episode watch history.
- Episode-segment tracking.
- Automatic scrobbling.
- Streaming-provider synchronization.
- Permanent background TMDB synchronization.
- Multiple users.
- Ratings and reviews beyond personal notes.
- Cast and crew databases.
- Awards tracking.
- Subtitle or audio-language tracking.
- Exact playback-position synchronization.
- Automatic Completed transitions after metadata refresh.
- Separate progress engines for cartoons, documentaries, or miniseries.
- Separate TV Movie behaviour.
- Automatic cross-media franchise discovery.
- Automatic import of every missing movie in a collection.

These may be added later only when they provide clear value.

---

## 24. Future Extensions

Possible post-MVP additions:

- Link an existing manual work to TMDB.
- Discover missing local works from a TMDB movie collection.
- Streaming availability for Chile.
- TMDB / JustWatch provider attribution.
- Favourite works.
- Personal ratings.
- Release-calendar views.
- Upcoming-season alerts.
- Cross-module Hibi Log activity.
- Watch-time analytics.
- MAL Insights and Watchroom combined viewing statistics.
- Multiple users.

---

## 25. Implementation Progress

```text
[x] Create Watchroom Django app
[x] Add public module routes and navigation
[x] Implement MediaWork and WatchEntry
[x] Implement Season
[x] Implement ViewingRun and SeasonProgress
[x] Add the public dashboard
[x] Add the public library and detail views
[x] Add authenticated owner forms
[x] Add manual local work creation
[x] Add entry and season management
[x] Add viewing-run creation and transitions
[x] Add movie-minute progress
[x] Add active-run season progress
[x] Remove duplicate season-progress dates
[x] Add explicit full-progress series completion
[x] Protect completed historical progress from editing
[x] Add permanent work deletion
[x] Add public and owner permission hardening
[x] Implement TMDB client and normalizers
[x] Add TMDB movie and series search
[x] Add review-before-import workflow
[x] Add local transactional import
[x] Add duplicate protection
[x] Add safe metadata and season refresh
[x] Add runtime and episode-total preservation
[x] Restore missing seasons and Specials during refresh
[x] Implement Franchise and FranchiseMembership
[x] Add public franchise index and detail views
[x] Add owner franchise and membership management
[x] Support mixed Movie / Series franchises
[x] Add automatic TMDB movie-collection synchronization
[x] Add background-image franchise cards and heroes
[x] Reach 155 Watchroom tests
[x] Reach 314 global tests
[x] Validate Saw Collection automatically
[x] Validate Phineas and Ferb as a mixed local franchise
[x] Complete the Watchroom MVP
```

---

## 26. Current Implementation Checkpoint

```text
Document: watchroom-data-model.md
Module: Watchroom
Stage: MVP complete
Status: Ready to merge from feat/watchroom-tmdb-integration
Current migration: watchroom.0006
Watchroom tests: 155 OK
Global tests: 314 OK
Active public routes: Dashboard, Library, Work Detail, Franchise Index, Franchise Detail
Active owner workflows: Manual creation, deletion, entry, seasons, runs, transitions, progress, TMDB search/import/refresh, franchise management
Primary source: TMDB
TMDB client: Complete
TMDB search: Complete
TMDB import: Complete
TMDB refresh: Complete
Local franchises: Complete
Mixed Movie/Series franchises: Complete
TMDB movie collections: Complete
Primary franchise image: backdrop_url
Storage strategy: Local-first
Progress style: MAL-like aggregate progress
History style: Game Kiroku-like ViewingRun history
Primary types: Movie and Series
SeasonProgress dates: Excluded
Episode rows: Excluded
TMDB attribution: Footer
```

Watchroom is ready to merge into `main`. Post-MVP work should continue in separate feature branches so optional integrations remain isolated from the completed tracking system.
