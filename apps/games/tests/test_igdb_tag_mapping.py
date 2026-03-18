from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.games.services.igdb_mapping import map_igdb_tags


class IGDBTagMappingTests(TestCase):
    @patch("apps.games.services.tag_list.TagService.get_igdb_mapping")
    def test_map_igdb_tags(self, mock_get_mapping: MagicMock) -> None:
        """IGDB ID → DB ID 매핑"""
        # 테스트용 매핑
        mock_get_mapping.return_value = {1: 1, 2: 2, 3: 3}

        igdb_ids = [1, 2, 3]
        tag_ids = map_igdb_tags(igdb_ids)
        self.assertEqual(set(tag_ids), {1, 2, 3})

    @patch("apps.games.services.tag_list.TagService.get_igdb_mapping")
    def test_map_igdb_tags_with_unknown_ids(self, mock_get_mapping: MagicMock) -> None:
        """존재하지 않는 IGDB ID는 무시"""
        mock_get_mapping.return_value = {2: 2}

        igdb_ids = [2, 99]  # 99는 매핑 없음
        tag_ids = map_igdb_tags(igdb_ids)
        self.assertEqual(tag_ids, [2])
