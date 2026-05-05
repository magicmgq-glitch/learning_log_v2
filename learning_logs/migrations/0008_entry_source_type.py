from django.db import migrations, models


def backfill_system_entry_source_type(apps, schema_editor):
    Entry = apps.get_model('learning_logs', 'Entry')

    Entry.objects.filter(topic__owner__username='miaoAI').update(source_type='system')


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('learning_logs', '0007_alter_streamitem_event_type_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='entry',
            name='source_type',
            field=models.CharField(
                choices=[('user', '用户笔记'), ('system', '系统归档')],
                db_index=True,
                default='user',
                max_length=20,
                verbose_name='内容来源',
            ),
        ),
        migrations.RunPython(backfill_system_entry_source_type, noop_reverse),
    ]
