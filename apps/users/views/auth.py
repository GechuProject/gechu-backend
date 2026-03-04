from rest_framework.views import APIView
from rest_framework.response import Response

class EmailCodeSendAPIView(APIView):
    def post(self, request):
        return Response({"message": "stub", "expires_in": 300})