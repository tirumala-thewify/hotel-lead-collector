from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('hotels', '0004_provider_settings_people_providers_zoominfo')]

    operations = [
        migrations.AlterField(
            model_name='providersettings',
            name='hotel_provider',
            field=models.CharField(
                choices=[
                    ('openstreetmap', 'OpenStreetMap'),
                    ('geoapify', 'Geoapify'),
                    ('google', 'Google Places'),
                    ('playwright', 'Browser Search (Playwright)'),
                ],
                default='openstreetmap', max_length=20,
            ),
        ),
    ]
