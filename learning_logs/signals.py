from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .embedded_media_cleanup import (
    cleanup_removed_embedded_media,
    extract_embedded_media_paths,
)
from .models import Entry


@receiver(pre_save, sender=Entry)
def remember_previous_embedded_media(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_embedded_media_paths = set()
        return

    previous_text = (
        sender.objects.filter(pk=instance.pk)
        .values_list('text', flat=True)
        .first()
        or ''
    )
    instance._previous_embedded_media_paths = extract_embedded_media_paths(previous_text)


@receiver(post_save, sender=Entry)
def cleanup_unreferenced_embedded_media_after_save(sender, instance, created, **kwargs):
    previous_paths = getattr(instance, '_previous_embedded_media_paths', set())
    current_paths = extract_embedded_media_paths(instance.text)
    removed_paths = previous_paths - current_paths
    if removed_paths:
        cleanup_removed_embedded_media(removed_paths, exclude_entry_id=instance.id)


@receiver(post_delete, sender=Entry)
def cleanup_unreferenced_embedded_media_after_delete(sender, instance, **kwargs):
    current_paths = extract_embedded_media_paths(instance.text)
    if current_paths:
        cleanup_removed_embedded_media(current_paths, exclude_entry_id=instance.id)
