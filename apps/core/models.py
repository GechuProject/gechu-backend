"""
TODO:  TimeStampedModel 만들어 주세요.
모든 모델에 공통으로 사용되는 생성/수정 시간을 기록하는 추상 클래스로,
이 클래스를 상속받는 모든 모델은 created_at, updated_at 필드를 자동으로 갖게됩니다.
abstract = True: 이 클래스 자체는 데이터베이스 테이블을 생성하지 않으며, 오직 다른 모델에 상속(Mixin)되는 용도로만 사용됩니다.
"""
from django.db import models

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True