# Generated by Django 2.1.7 on 2019-02-17 10:48

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0035_bot_for_testing'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subjectgroupbinding',
            name='last_problem',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='main.Problem'),
        ),
    ]