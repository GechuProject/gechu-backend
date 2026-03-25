from django.test import TestCase, override_settings
from django_redis import get_redis_connection


# 테스트에서 User.objects.create_user() 호출 시 MD5 해셔를 사용하여 속도를 최적화합니다.
# 보안이 불필요한 테스트 환경에서는 이 클래스를 TestCase 대신 사용합니다.
@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class FastTestCase(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # 테스트 시작 전 Redis 캐시 초기화
        try:
            r = get_redis_connection("default")
            r.flushdb()
        except Exception:
            pass  # Redis 연결 실패 시 무시

    def tearDown(self) -> None:
        super().tearDown()
        # 각 테스트 후 Redis 캐시 초기화
        try:
            r = get_redis_connection("default")
            r.flushdb()
        except Exception:
            pass  # Redis 연결 실패 시 무시
