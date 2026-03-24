from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("recommendations", "0003_remove_gamesimilarity_unique_game_similarity_pair_and_more"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="userrecommendation",
            name="unique_user_game_recommendation",
        ),
        migrations.AddConstraint(
            model_name="userrecommendation",
            constraint=models.UniqueConstraint(
                fields=["user", "igdb_game_id", "reason"],
                name="unique_user_game_recommendation",
            ),
        ),
    ]
