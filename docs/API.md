# Learning Log API

This document summarizes the API endpoints that are ready for a future iOS app.

## Base URL

- Local development: `http://127.0.0.1:8000`
- API prefix: `/api/v1/`

## Authentication

### Register

- `POST /api/v1/auth/register/`
- Content-Type: `application/json`

Example request:

```json
{
  "username": "alice",
  "password1": "secret12345",
  "password2": "secret12345"
}
```

Example response:

```json
{
  "user": {
    "id": 1,
    "username": "alice"
  },
  "tokens": {
    "access": "...",
    "refresh": "..."
  }
}
```

### Login

- `POST /api/v1/auth/token/`
- Content-Type: `application/json`

Example request:

```json
{
  "username": "alice",
  "password": "secret12345"
}
```

Example response:

```json
{
  "access": "...",
  "refresh": "..."
}
```

### Refresh Token

- `POST /api/v1/auth/token/refresh/`

Example request:

```json
{
  "refresh": "..."
}
```

### Current User

- `GET /api/v1/auth/me/`
- Requires header: `Authorization: Bearer <access_token>`

## Topics

### List Topics

- `GET /api/v1/topics/`

### Create Topic

- `POST /api/v1/topics/`

Example request:

```json
{
  "text": "Python",
  "is_public": false
}
```

### Topic Detail

- `GET /api/v1/topics/<topic_id>/`

### Update Topic

- `PATCH /api/v1/topics/<topic_id>/`
- `PUT /api/v1/topics/<topic_id>/`

Example request:

```json
{
  "text": "Python Advanced",
  "is_public": true
}
```

### Delete Topic

- `DELETE /api/v1/topics/<topic_id>/`

## Entries

### List Entries For A Topic

- `GET /api/v1/topics/<topic_id>/entries/`

### Create Entry

- `POST /api/v1/topics/<topic_id>/entries/`
- Supports JSON for text-only entries
- Supports multipart form data for file uploads

Text-only example:

```json
{
  "text": "Learned how JWT works.",
  "is_public": false
}
```

### Entry Detail

- `GET /api/v1/entries/<entry_id>/`

### Update Entry

- `PATCH /api/v1/entries/<entry_id>/`
- `PUT /api/v1/entries/<entry_id>/`

Example request:

```json
{
  "text": "Updated note",
  "is_public": true,
  "clear_image": true
}
```

### Delete Entry

- `DELETE /api/v1/entries/<entry_id>/`

## Public Feed APIs (No Login Required)

### Public Topics

- `GET /api/v1/public/topics/`
- Returns topics with `is_public=true`.

### Public Entries

- `GET /api/v1/public/entries/`
- Returns entries that match either condition:
  - `entry.is_public=true`
  - `entry.topic.is_public=true`

### Public Stream

- `GET /api/v1/public/stream/`
- Returns the public high-frequency signal feed.
- Default feed only includes:
  - `signal_item`
  - `theme_update`
  - `action_result`
- Release events such as `briefing_release` and `artifact_release` are not shown by default. They can still be queried with `event_type`.
- Query params:
  - `limit`: default `50`, max `100`
  - `before_id`: cursor for the next page
  - `event_type`: optional explicit type filter

## AI-Friendly Alias APIs

These are aliases of existing authenticated write APIs, useful for AI tools:

- `POST /api/v1/ai/topics/` (same as `POST /api/v1/topics/`)
- `POST /api/v1/ai/topics/<topic_id>/entries/` (same as `POST /api/v1/topics/<topic_id>/entries/`)
- `PATCH /api/v1/ai/entries/<entry_id>/` (same as `PATCH /api/v1/entries/<entry_id>/`)

## Stream APIs

### List Stream Events

- `GET /api/v1/stream/`
- Returns authenticated access to system stream events.
- Query params:
  - `limit`: default `50`, max `100`
  - `before_id`: cursor for the next page
  - `event_type`: optional explicit type filter

### Create Or Upsert Stream Event

- `POST /api/v1/stream/`
- Supported `payload.item_type` values:
  - `signal_item`
  - `theme_update`
  - `action_result`
  - `briefing_release`
  - `artifact_release`
- The default public feed is for high-value signals, topic tracking, and minimum viable action results. `briefing_release` and `artifact_release` are retained for diagnostics or explicit release-event queries, not for the broad public feed.
- Events default to `visibility = public`.
- Events default to system ownership. Pass `"owner_mode": "user"` only when a stream event must explicitly belong to the authenticated user.
- Public stream events expose event metadata and public archive links only; private entry content remains protected.

Example request:

```json
{
  "request_id": "req-briefing-1",
  "output_kind": "waterfall_item",
  "source_object_ids": ["briefing:2026-05-01"],
  "generated_at": "2026-05-01T09:00:00+08:00",
  "visibility": "public",
  "delivery_targets": ["learning_log_stream"],
  "payload": {
    "item_id": "evt-briefing-2026-05-01",
    "item_type": "briefing_release",
    "display_title": "AI 晨报已发布",
    "display_summary": "今天的晨报已经生成，并已同步到公开笔记。",
    "occurred_at": "2026-05-01T09:00:00+08:00",
    "related_entry_id": 12,
    "source_links": [
      {
        "label": "晨报详情",
        "url": "https://example.com/briefing"
      }
    ]
  }
}
```

## iOS Notes

- Store the `access` token securely and send it in the `Authorization` header.
- Keep the `refresh` token so the app can request a new access token when needed.
- For a first iOS prototype, the simplest flow is:
  1. Login
  2. Save tokens
  3. Fetch `/api/v1/topics/`
  4. Render the topic list
