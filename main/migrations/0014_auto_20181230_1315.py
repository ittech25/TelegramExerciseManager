# Generated by Django 2.1.4 on 2018-12-30 09:15

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0013_bot_last_updated'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='participantgroupbinding',
            name='group',
        ),
        migrations.RemoveField(
            model_name='participantgroupbinding',
            name='participant',
        ),
        migrations.AddField(
            model_name='participantgroupbinding',
            name='groupspecificparticipantdata',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to='main.GroupSpecificParticipantData'),
            preserve_default=False,
        ),
    ]