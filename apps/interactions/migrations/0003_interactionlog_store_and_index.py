import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("games", "0003_alter_game_esrb_rating"),
        ("interactions", "0002_remove_interactioncontextrule_created_at_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="interactionlog",
            name="store",
            field=models.ForeignKey(
                blank=True,
                db_column="store_id",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="games.externalstore",
            ),
        ),
        migrations.AddIndex(
            model_name="interactionlog",
            index=models.Index(fields=["store"], name="interaction_store_i_4e10f0_idx"),
        ),
    ]
