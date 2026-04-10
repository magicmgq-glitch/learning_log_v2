from django.db import migrations, models


def disable_existing_tokens(apps, schema_editor):
    UserAPIToken = apps.get_model('users', 'UserAPIToken')
    UserAPIToken.objects.all().update(is_active=False)


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0003_userapitoken'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userapitoken',
            name='is_active',
            field=models.BooleanField(default=False, verbose_name='是否启用'),
        ),
        migrations.RunPython(disable_existing_tokens, migrations.RunPython.noop),
    ]
