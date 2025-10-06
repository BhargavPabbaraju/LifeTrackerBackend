from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.response import Response

from .models import *
from .serializers import *


class DomainViewSet(viewsets.ModelViewSet):
    queryset = Domain.objects.all()
    serializer_class = DomainSerializer


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer


class GoalViewSet(viewsets.ModelViewSet):
    queryset = Goal.objects.all()
    serializer_class = GoalSerializer


class GoalTypeViewSet(viewsets.ViewSet):
    """A read-only endpoint for listing available goal types."""

    def list(self, request):
        serializer = GoalTypeSerializer(GOAL_TYPE_CLASSES.values(), many=True)
        return Response(serializer.data)
