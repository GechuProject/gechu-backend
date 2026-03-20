import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0004_add_social_user_unique_user_provider"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserProfileImage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("image_data", models.BinaryField()),
                ("content_type", models.CharField(default="image/webp", max_length=50)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=models.deletion.CASCADE,
                        related_name="profile_image",
                        to="users.user",
                    ),
                ),
            ],
            options={
                "db_table": "user_profile_images",
            },
        ),
    ]
