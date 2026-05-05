# Learning Log System Archive Entry Technical Specification

## 1. Purpose

This document defines the technical design for the chosen near-term approach:

- keep using `Entry` as the detail storage object
- reserve `miaoAI` as the system publisher account
- mark system archive entries explicitly
- route iOS stream cards internally by `related_entry_id`

The goal is to fix system-stream navigation and content attribution without immediately introducing a brand-new content model.

## 2. Current State

### 2.1 Existing user content model

- `Topic`
- `Entry`

These are user-centric and already support:

- markdown / html content
- public/private visibility
- iOS entry detail rendering

### 2.2 Existing stream model

`StreamItem` currently stores:

- event metadata
- visibility
- optional `owner`
- optional `related_entry`
- payload metadata

### 2.3 Existing client behavior

The iOS stream card currently:

- receives `display_title`
- receives `display_summary`
- receives `related_entry_id`
- receives `archive_url`
- still opens `archive_url` through browser behavior

## 3. Target Architecture

```text
System publisher / workflow
    -> miaoAI system account
    -> system-only Topic
    -> Entry(source_type=system)
    -> StreamItem.related_entry
    -> Public Stream API
    -> iOS internal detail route or browser fallback
```

## 4. Data Model Adjustment

### 4.1 Entry source marker

Add to `Entry`:

- `source_type: CharField(choices=[user, system], default=user, db_index=True)`

Purpose:

- distinguish system archive entries from user-authored notes
- support later statistics / admin filtering / presentation branching
- avoid relying on `owner.username == "miaoAI"` as the only discriminator

### 4.2 StreamItem

Keep:

- `related_entry`

Do not add a new target model in this round.

## 5. API Contract Changes

### 5.1 Public single-entry detail

New endpoint:

- `GET /api/v1/public/entries/<id>/`

Response:

```json
{
  "topic": { "...": "..." },
  "entry": { "...": "..." }
}
```

Rules:

- only return entries where:
  - `entry.is_public == true`
  - or `entry.topic.is_public == true`
- include owner fields needed by the iOS public detail page

### 5.2 Stream API contract

Keep:

```json
{
  "related_entry_id": 214,
  "archive_url": "http://..."
}
```

Semantics:

- `related_entry_id` is the primary internal target
- `archive_url` is the browser fallback

### 5.3 Stream write contract

Writers continue to send:

- `related_entry_id`

But the linked entry must satisfy:

- owned by `miaoAI`
- stored in a system-only topic
- marked with `source_type = system`

## 6. Server Logic

### 6.1 Publish flow

1. create or update system archive entry through the existing note publishing flow
2. mark that entry as `source_type = system`
3. create or update `StreamItem`
4. link `StreamItem.related_entry`

### 6.2 Public stream read flow

1. query visible `StreamItem`
2. `select_related('related_entry', 'related_entry__topic', 'related_entry__topic__owner')`
3. serialize display metadata
4. expose `related_entry_id`
5. expose `archive_url` as fallback

### 6.3 Archive URL behavior

`archive_url` becomes a fallback-only field:

- web sharing
- diagnostics
- public browser fallback

It must not be treated as the primary app navigation source.

## 7. iOS Client Design

### 7.1 Stream model changes

No new target object is required in this round.
Reuse:

- `relatedEntryID`
- `archiveURL`

### 7.2 Routing precedence

When a stream card is tapped:

1. if `target.kind == "system_content"` and `target.id != nil`
1. if `related_entry_id` exists
   - fetch `public/entries/<id>/`
   - push an in-app public entry detail screen
2. else if `archive_url` exists
   - open external browser
3. else
   - no navigation

### 7.3 Detail view strategy

Prefer reusing the existing public entry detail rendering path.
No independent system-content detail page is required in this round.

### 7.4 Existing note safety

Do not change:

- Topic list behavior
- Topic detail behavior
- Entry detail rendering behavior
- existing markdown/html note link behavior in this round

## 8. Web Design

### Minimum required

No new web page is required in this round.
The existing public entry detail page continues to serve as the browser fallback target.

## 9. Migration Strategy

### Phase 1: additive introduction

1. add `Entry.source_type`
2. add public single-entry API
3. keep old `related_entry`
4. keep old `archive_url`

### Phase 2: new writes follow system-topic conventions

System-generated briefings, artifacts, and progress pages continue to publish into `Entry`, but only through:

- `miaoAI`
- system-only topics
- `source_type = system`

### Phase 3: optional later evolution

If system volume or semantics outgrow this model later:

- introduce a dedicated `SystemContent` model
- migrate new publishers first
- keep historical system entries as compatibility data

## 10. Error Handling

### Case A: stream item has `related_entry_id` but target not found

- API returns `archive_url = null` and `related_entry_id = null` when target cannot be exposed
- keep display metadata
- preserve `archive_url` if available

### Case B: linked entry exists but is not public

- public detail API returns 404
- client must not expose content

### Case C: iOS fetch fails

- show load error
- if `archive_url` exists, offer explicit browser fallback
- do not silently open the browser

## 11. Testing Requirements

### Backend

Add tests for:

1. `Entry.source_type` default and explicit system value
2. public single-entry detail API access control
3. stream compatibility with `related_entry`
4. stream-linked public entry detail serialization

### iOS

Verify:

1. stream card with `related_entry_id` opens in-app detail
2. stream card with only archive URL opens browser
3. stream card with neither target nor archive URL does not navigate
4. markdown/html note pages continue to behave as before

## 12. Rollout Notes

This route should be implemented in small reversible steps:

1. docs and blueprint
2. `Entry.source_type` migration
3. public single-entry API
4. iOS stream routing
5. optional doc/API updates

No destructive removal of legacy fields should happen in the first implementation round.
