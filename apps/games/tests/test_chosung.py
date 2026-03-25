from django.test import SimpleTestCase

from apps.games.chosung import get_chosung, get_chosung_normalized


class GetChosungTest(SimpleTestCase):
    def test_korean_basic(self) -> None:
        self.assertEqual(get_chosung("디아블로"), "ㄷㅇㅂㄹ")

    def test_korean_with_spaces(self) -> None:
        self.assertEqual(get_chosung("디 키"), "ㄷ ㅋ")

    def test_english_passthrough(self) -> None:
        self.assertEqual(get_chosung("Diablo"), "Diablo")

    def test_mixed(self) -> None:
        self.assertEqual(get_chosung("FIFA 23"), "FIFA 23")

    def test_numbers(self) -> None:
        self.assertEqual(get_chosung("123"), "123")

    def test_empty(self) -> None:
        self.assertEqual(get_chosung(""), "")


class GetChosungNormalizedTest(SimpleTestCase):
    def test_removes_spaces(self) -> None:
        self.assertEqual(get_chosung_normalized("디 키"), "ㄷㅋ")

    def test_empty_string(self) -> None:
        self.assertEqual(get_chosung_normalized(""), "")

    def test_none_like_falsy(self) -> None:
        # falsy 값 방어
        self.assertEqual(get_chosung_normalized(""), "")

    def test_korean_no_spaces(self) -> None:
        self.assertEqual(get_chosung_normalized("디아블로"), "ㄷㅇㅂㄹ")

    def test_english_no_change(self) -> None:
        self.assertEqual(get_chosung_normalized("Diablo"), "Diablo")
