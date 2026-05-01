# Stream Production Rollout

This note records the minimum production rollout needed for the Learning Log stream feature.

## Current finding

On 2026-05-01, `creator-ops-briefing` successfully published a private artifact note to production Learning Log:

- topic: `AI大师之路`
- entry_id: `181`
- artifact source: `xiaohongshu-post-20260425-110145-4`

The follow-up `artifact_release` stream write failed with:

- `POST /api/v1/stream/` -> `404`
- `GET /api/v1/public/stream/` -> `404`
- `GET /public/stream/` -> `404`

Conclusion: the production service can still publish normal notes, but it has not loaded the stream routes/code yet.

## Files that must be deployed

- `learning_logs/models.py`
- `learning_logs/migrations/0005_streamitem.py`
- `learning_logs/migrations/0006_system_stream_items.py`
- `learning_logs/migrations/0007_alter_streamitem_event_type_and_more.py`
- `learning_logs/api_views.py`
- `learning_logs/api_urls.py`
- `learning_logs/views.py`
- `learning_logs/urls.py`
- `learning_logs/templates/learning_logs/public_stream.html`
- `learning_logs/templates/learning_logs/base.html`
- `learning_logs/tests.py`
- `docs/API.md`
- `docs/stream-minimal-implementation.md`

## Minimum production steps

Run these on the production server after pulling the updated code:

```bash
cd /path/to/learning_log_v2
./ll_env/bin/python manage.py migrate learning_logs
./ll_env/bin/python manage.py test learning_logs.tests
sudo systemctl restart <learning-log-service>
```

The exact service name is not recorded in this repository yet. Confirm it on the server with:

```bash
systemctl list-units --type=service | grep -Ei 'learning|gunicorn|django'
```

## Verification

After restart, these endpoints should no longer return `404`:

```bash
curl -i http://124.223.158.110/api/v1/public/stream/
curl -i http://124.223.158.110/public/stream/
```

Expected behavior:

- `/api/v1/public/stream/` returns JSON.
- `/public/stream/` returns an HTML page.
- `signal_item`, `theme_update`, and `action_result` events show in the default public stream when their visibility is public.
- `briefing_release` and `artifact_release` events are hidden from the default public stream and are only visible through explicit `event_type` queries.
- A public stream event may still point to a private archive note; in that case the public page should show the event summary without exposing private note content.

## Re-run stream write

After production rollout, re-run one private artifact publish:

```bash
python3 "/Users/miao/Documents/New project/scripts/hub_spoke_publish_xhs_artifact_learning_log.py" \
  --task-dir "/Users/miao/Documents/New project/.work/hub-spoke-runtime/archive/xiaohongshu-post-20260425-110145-4" \
  --topic "AI大师之路"
```

Success criteria:

- `returncode` is `0`
- `stream_event_type` is `artifact_release`
- `stream_event_id` is not empty
- `stream_error` is empty
