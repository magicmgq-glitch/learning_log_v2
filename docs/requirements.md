# Learning Log System Archive Entry Requirements

## 1. Background

Learning Log currently supports a first-generation stream system through `StreamItem`.
The team considered a full Route 2 split with an independent `SystemContent` model, but the current implementation cost is too high for this phase.

The chosen near-term solution is:

1. keep using `Entry` as the detail-content container
2. treat `miaoAI` as a dedicated system account
3. store system stream detail pages inside system-only Topics
4. mark those entries explicitly as system-originated
5. make iOS stream cards route internally by `related_entry_id`

## 2. Problem Statement

The current stream design still needs a correction:

- `StreamItem`: event / timeline layer
- `Entry`: content storage layer reused by both user notes and system archive notes

The practical problems to solve now are:

- stream cards open Safari even when they point to internal Learning Log content
- system-generated detail pages are not clearly marked as system-originated entries
- there is no public single-entry JSON detail API for the iOS client

## 3. Target Outcome

Introduce a **system archive entry** approach:

- keep `Topic / Entry` intact
- reserve `miaoAI` as the system publisher account
- store stream-linked system detail pages as public entries inside system-only topics
- add an explicit `source_type` marker to entries
- let iOS treat `related_entry_id` as the primary internal target

## 4. In Scope

This round includes:

1. Add an origin marker to `Entry`.
2. Add a public single-entry detail API for stream-linked public entries.
3. Update iOS stream card routing to prefer internal entry detail.
4. Keep `related_entry` as the stream bridge.
5. Preserve browser fallback through `archive_url`.

## 5. Out of Scope

This round does **not** include:

1. Creating a new `SystemContent` model in this round.
2. Removing `related_entry`.
3. Reworking all markdown/html body links into app-internal routing.
4. Full admin redesign for system content management.
5. Android implementation.

## 6. Core Business Rules

### 6.1 Content ownership rules

- User notes belong to a normal user and remain inside `Topic / Entry`.
- System stream events belong to the system timeline.
- System stream detail pages belong to `miaoAI` and must be written into system-only topics.
- System archive entries must be marked with `source_type = system`.

### 6.2 Routing rules

- `related_entry_id` first.
- Browser fallback second.
- No silent jump to browser when an internal target exists.

### 6.3 Public visibility rules

- Public stream events may point to public system archive entries.
- Public system archive entries must be readable without login through a dedicated public single-entry API.
- User private entries must not be exposed through stream fallbacks.

## 7. Functional Requirements

### FR-1: Entry origin marker

The system shall support an explicit `source_type` marker on `Entry`, at minimum:

- `user`
- `system`

### FR-2: Stream-to-entry target

The system shall continue to allow a stream item to reference an entry through `related_entry`.

### FR-3: Public single-entry detail API

The system shall expose an unauthenticated API for reading one public entry by id.

### FR-4: iOS internal navigation

The iOS app shall navigate to public entry detail inside the app when a stream item points to a related public entry.

### FR-5: Browser fallback

The iOS app shall open Safari only when the stream item has no valid internal target and a valid fallback URL exists.

### FR-6: Existing note behavior safety

The existing Topic list, Entry list, Entry detail, Markdown rendering, and HTML rendering behavior shall not regress.

## 8. Non-Functional Requirements

### NFR-1: Contract safety

- Existing response fields such as `archive_url` remain valid.
- New fields must be additive.

### NFR-2: Operational safety

- No silent failure.
- Missing target content must degrade gracefully.
- Old stream items must remain readable as event summaries.

### NFR-3: Performance

- Public stream remains paginated.
- Public entry detail must load a single object efficiently.
- Queries must be index-aware for high-volume stream writes.

### NFR-4: Migration safety

- Database migration must be staged.
- Existing `related_entry` historical data must remain valid.

## 9. User Stories

### Story A: Public stream reader

As a public app user,  
when I tap a stream card that represents a public system briefing,  
I want to open the linked public entry inside the app,  
so that I stay in the Learning Log experience instead of being pushed into Safari.

### Story B: Browser fallback

As a public app user,  
when a stream card has no internal content target but has a fallback page,  
I want the app to open Safari,  
so that I can still view the content externally.

### Story C: Product maintenance

As the product owner,  
I want system-published entries to be explicitly marked as system-originated,  
so that daily high-volume stream publishing does not become indistinguishable from user-authored notes.

## 10. Acceptance Criteria

1. System-generated detailed pages can continue to be stored in `Entry`, but must be marked with `source_type = system`.
2. New stream events continue to reference `related_entry`.
3. Public app clients can fetch one public entry by ID.
4. Stream cards with `related_entry_id` open app-internal detail pages.
5. Stream cards without internal targets still support browser fallback.
6. Existing user note APIs and user note pages continue to work unchanged.
7. Existing historical stream items remain readable.

## 11. Delivery Strategy

Recommended rollout order:

1. Add `Entry.source_type`.
2. Add public entry detail API.
3. Update iOS stream routing.
4. Ensure new system stream detail pages are published through `miaoAI` + system-only topics.

## 12. Risks

1. System archive entries and user entries still share one table.
2. Historical stream items may point to deleted entries.
3. Statistics may become noisy if `source_type` is not used consistently.
4. Over-expanding scope into full global internal-link routing too early.
