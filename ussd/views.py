from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.views import exception_handler as drf_exception_handler

from .engine import process_ussd
from .models import OperationLog
from .serializers import OperationLogSerializer, UssdRequestSerializer


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is not None and isinstance(response.data, dict):
        if "detail" in response.data and "text" not in response.data:
            response.data = {
                "text": str(response.data["detail"]),
                "end": True,
            }
    return response


class USSDView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = UssdRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"text": "Неверный запрос", "end": True},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data
        result = process_ussd(
            msisdn=data["msisdn"],
            session_id=data["session_id"],
            user_input=data["input"],
        )
        return Response(result, status=status.HTTP_200_OK)


class LogView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, msisdn):
        logs = OperationLog.objects.filter(msisdn=msisdn)
        serializer = OperationLogSerializer(logs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
