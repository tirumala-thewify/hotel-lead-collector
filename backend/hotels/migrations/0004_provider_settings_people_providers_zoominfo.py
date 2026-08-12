from django.db import migrations, models


def migrate_apollo_selection(apps, schema_editor):
    ProviderSettings = apps.get_model('hotels', 'ProviderSettings')
    for settings in ProviderSettings.objects.all():
        settings.people_providers = ['apollo'] if settings.apollo_enabled else []
        settings.save(update_fields=['people_providers'])


class Migration(migrations.Migration):
    dependencies = [('hotels', '0003_provider_settings_business_providers')]
    operations = [
        migrations.AddField(model_name='providersettings', name='people_providers',
                            field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name='providersettings', name='zoominfo_api_key_encrypted',
                            field=models.TextField(blank=True)),
        migrations.RunPython(migrate_apollo_selection, migrations.RunPython.noop),
    ]
