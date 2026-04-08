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
  "text": "Python"
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
  "text": "Python Advanced"
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
  "text": "Learned how JWT works."
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
  "clear_image": true
}
```

### Delete Entry

- `DELETE /api/v1/entries/<entry_id>/`

## iOS Notes

- Store the `access` token securely and send it in the `Authorization` header.
- Keep the `refresh` token so the app can request a new access token when needed.
- For a first iOS prototype, the simplest flow is:
  1. Login
  2. Save tokens
  3. Fetch `/api/v1/topics/`
  4. Render the topic list
