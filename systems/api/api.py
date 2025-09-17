from rest_framework.response import Response
from rest_framework.decorators import api_view
from systems.models import Switch, System


@api_view(["GET"])
def APISwitchView(request, *args, **kwargs):
  model_data = list(Switch.objects.all().values())
  return Response(model_data)

@api_view(["GET"])
def APISystemView(request, *args, **kwargs):
  model_data = list(System.objects.all().values())
  return Response(model_data)