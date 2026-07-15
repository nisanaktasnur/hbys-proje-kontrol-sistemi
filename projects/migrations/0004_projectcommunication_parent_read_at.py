from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0003_multi_hospital_context"),
    ]

    operations = [
        migrations.AddField(
            model_name="projectcommunication",
            name="read_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Okunma Zamanı"),
        ),
        migrations.AddField(
            model_name="projectcommunication",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="replies",
                to="projects.projectcommunication",
                verbose_name="Üst İletişim",
            ),
        ),
    ]
