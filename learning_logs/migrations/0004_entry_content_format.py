from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('learning_logs', '0003_entry_is_public_topic_is_public'),
    ]

    operations = [
        migrations.AddField(
            model_name='entry',
            name='content_format',
            field=models.CharField(
                choices=[('markdown', 'Markdown 笔记'), ('html', 'HTML 页面')],
                default='markdown',
                max_length=20,
                verbose_name='内容格式',
            ),
        ),
    ]
