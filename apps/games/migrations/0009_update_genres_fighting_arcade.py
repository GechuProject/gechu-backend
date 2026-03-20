# Generated manually

from django.db import migrations

GENRES = [
    {"igdb_id": 12, "igdb_type": "genre", "name": "RPG", "slug": "rpg"},
    {"igdb_id": 31, "igdb_type": "genre", "name": "어드벤처", "slug": "adventure"},
    {"igdb_id": 5, "igdb_type": "genre", "name": "FPS", "slug": "shooter"},
    {"igdb_id": 15, "igdb_type": "genre", "name": "전략", "slug": "strategy"},
    {"igdb_id": 13, "igdb_type": "genre", "name": "시뮬레이션", "slug": "simulator"},
    {"igdb_id": 14, "igdb_type": "genre", "name": "스포츠", "slug": "sport"},
    {"igdb_id": 10, "igdb_type": "genre", "name": "레이싱", "slug": "racing"},
    {"igdb_id": 9, "igdb_type": "genre", "name": "퍼즐", "slug": "puzzle"},
    {"igdb_id": 4, "igdb_type": "genre", "name": "격투", "slug": "fighting"},
    {"igdb_id": 33, "igdb_type": "genre", "name": "아케이드", "slug": "arcade"},
]


def reset_genres(apps, schema_editor):
    Genre = apps.get_model("games", "Genre")
    UserPreferenceGenre = apps.get_model("preferences", "UserPreferenceGenre")

    # 유저 선호 장르 전체 삭제
    UserPreferenceGenre.objects.all().delete()

    # 장르 전체 삭제
    Genre.objects.all().delete()

    # PK 시퀀스 리셋
    schema_editor.execute("ALTER SEQUENCE genres_id_seq RESTART WITH 1;")

    # 새로 생성 (PK 1부터 순차)
    for genre in GENRES:
        Genre.objects.create(**genre)


def rollback(apps, schema_editor):
    Genre = apps.get_model("games", "Genre")
    UserPreferenceGenre = apps.get_model("preferences", "UserPreferenceGenre")

    UserPreferenceGenre.objects.all().delete()
    Genre.objects.all().delete()

    schema_editor.execute("ALTER SEQUENCE genres_id_seq RESTART WITH 1;")

    OLD_GENRES = [
        {"igdb_id": 12, "igdb_type": "genre", "name": "RPG", "slug": "rpg"},
        {"igdb_id": 1, "igdb_type": "theme", "name": "액션", "slug": "action"},
        {"igdb_id": 31, "igdb_type": "genre", "name": "어드벤처", "slug": "adventure"},
        {"igdb_id": 5, "igdb_type": "genre", "name": "FPS", "slug": "shooter"},
        {"igdb_id": 15, "igdb_type": "genre", "name": "전략", "slug": "strategy"},
        {"igdb_id": 13, "igdb_type": "genre", "name": "시뮬레이션", "slug": "simulator"},
        {"igdb_id": 14, "igdb_type": "genre", "name": "스포츠", "slug": "sport"},
        {"igdb_id": 10, "igdb_type": "genre", "name": "레이싱", "slug": "racing"},
        {"igdb_id": 9, "igdb_type": "genre", "name": "퍼즐", "slug": "puzzle"},
        {"igdb_id": 5, "igdb_type": "game_mode", "name": "MMORPG", "slug": "mmorpg"},
    ]
    for genre in OLD_GENRES:
        Genre.objects.create(**genre)


class Migration(migrations.Migration):
    dependencies = [
        ("games", "0008_alter_genre_igdb_id_alter_tag_igdb_id_and_more"),
        ("preferences", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(reset_genres, rollback),
    ]
