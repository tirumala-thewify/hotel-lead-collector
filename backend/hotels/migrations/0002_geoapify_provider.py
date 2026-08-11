from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('hotels', '0001_initial')]

    operations = [
        migrations.AlterField(
            model_name='providersettings',
            name='hotel_provider',
            field=models.CharField(
                choices=[
                    ('openstreetmap', 'OpenStreetMap'),
                    ('geoapify', 'Geoapify'),
                    ('google', 'Google Places'),
                ],
                default='openstreetmap',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='providersettings',
            name='geoapify_api_key_encrypted',
            field=models.TextField(blank=True),
        ),
    ]
