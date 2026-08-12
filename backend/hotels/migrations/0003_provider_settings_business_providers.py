from django.db import migrations, models


def migrate_selected_provider(apps, schema_editor):
    ProviderSettings = apps.get_model('hotels', 'ProviderSettings')
    for provider_settings in ProviderSettings.objects.all():
        provider_settings.business_providers = [
            provider_settings.hotel_provider or 'openstreetmap'
        ]
        provider_settings.save(update_fields=['business_providers'])


class Migration(migrations.Migration):
    dependencies = [('hotels', '0002_geoapify_provider')]

    operations = [
        migrations.AddField(
            model_name='providersettings',
            name='business_providers',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(migrate_selected_provider, migrations.RunPython.noop),
    ]
