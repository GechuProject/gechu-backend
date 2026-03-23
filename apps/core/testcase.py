from django.test import TestCase, override_settings


# 테스트에서 User.objects.create_user() 호출 시 MD5 해셔를 사용하여 속도를 최적화합니다.
# 보안이 불필요한 테스트 환경에서는 이 클래스를 TestCase 대신 사용합니다.
@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class FastTestCase(TestCase):
    pass
