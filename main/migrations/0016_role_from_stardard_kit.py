# Generated by Django 2.1.4 on 2018-12-30 10:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0015_scorethreshold'),
    ]

    operations = [
        migrations.AddField(
            model_name='role',
            name='from_stardard_kit',
            field=models.BooleanField(default=False),
        ),
    ]
