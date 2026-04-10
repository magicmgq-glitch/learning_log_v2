from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0001_invitecode'),
    ]

    operations = [
        migrations.AddField(
            model_name='invitecode',
            name='valid_for_days',
            field=models.PositiveSmallIntegerField(
                choices=[(1, '24小时'), (7, '7天'), (30, '30天')],
                default=1,
                verbose_name='有效期',
            ),
        ),
    ]
