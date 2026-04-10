from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0002_invitecode_valid_for_days'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserAPIToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(max_length=80, unique=True, verbose_name='长期 API Token')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('last_used_at', models.DateTimeField(blank=True, null=True, verbose_name='最近使用时间')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                (
                    'user',
                    models.OneToOneField(
                        on_delete=models.deletion.CASCADE,
                        related_name='api_token',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': '用户 API Token',
                'verbose_name_plural': '用户 API Token',
            },
        ),
    ]
