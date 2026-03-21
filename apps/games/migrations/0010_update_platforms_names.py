# Generated manually

from django.db import migrations

UPDATES = [
    {"igdb_id": 167, "name": "PlayStation 5", "slug": "ps5"},
    {"igdb_id": 169, "name": "Xbox Series X|S", "slug": "series-x-s"},
    {"igdb_id": 34, "name": "Android", "slug": "android"},
]

OLD_VALUES = [
    {"igdb_id": 167, "name": "PlayStation", "slug": "playstation"},
    {"igdb_id": 169, "name": "Xbox", "slug": "xbox"},
    {"igdb_id": 34, "name": "Mobile", "slug": "mobile"},
]


IOS_PLATFORM = {"igdb_id": 39, "name": "iOS", "slug": "ios"}


def update_platforms(apps, schema_editor):
    Platform = apps.get_model("games", "Platform")
    for data in UPDATES:
        Platform.objects.filter(igdb_id=data["igdb_id"]).update(name=data["name"], slug=data["slug"])
    Platform.objects.get_or_create(
        igdb_id=IOS_PLATFORM["igdb_id"],
        defaults={"name": IOS_PLATFORM["name"], "slug": IOS_PLATFORM["slug"]},
    )


def rollback(apps, schema_editor):
    Platform = apps.get_model("games", "Platform")
    for data in OLD_VALUES:
        Platform.objects.filter(igdb_id=data["igdb_id"]).update(name=data["name"], slug=data["slug"])
    Platform.objects.filter(igdb_id=IOS_PLATFORM["igdb_id"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("games", "0009_update_genres_fighting_arcade"),
    ]

    operations = [
        migrations.RunPython(update_platforms, rollback),
    ]
