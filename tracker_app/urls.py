from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()
router.register(r'domains',DomainViewSet)
router.register(r'tags',TagViewSet)
router.register(r'goals',GoalViewSet)
router.register(r'goal-types', GoalTypeViewSet, basename='goal-type')

urlpatterns = [
    path('api/', include(router.urls)),
]