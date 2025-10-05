from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()
router.register(r'domains',DomainViewSet)
router.register(r'tags',TagViewSet)
router.register(r'goals',GoalViewSet)

urlpatterns = [
    path('api/',include(router.urls)),
]