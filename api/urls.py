# api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DocumentViewSet,
    SimpleRegisterView,
    SimpleLoginView,
    CurrentUserView,
    UserQueryView
)

router = DefaultRouter()
router.register(r'documents', DocumentViewSet, basename='document')

urlpatterns = [
    path('', include(router.urls)),
    path('register/', SimpleRegisterView.as_view(), name='simple-register'),
    path('login/', SimpleLoginView.as_view(), name='simple-login'),
    path('user_query/', UserQueryView.as_view(), name='user-query'),
    path('me/', CurrentUserView.as_view(), name='current-user'),
]
