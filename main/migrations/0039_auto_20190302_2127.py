# Generated by Django 2.1.4 on 2019-03-02 17:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0038_auto_20190302_2106'),
    ]

    operations = [
        migrations.AlterField(
            model_name='problemimage',
            name='image',
            field=models.ImageField(upload_to=''),
        ),
    ]