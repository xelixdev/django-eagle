from django.urls import path

from test_project.views import EagleView

urlpatterns = [
    path("eagles/<int:pk>/", EagleView.as_view(), name="eagle-detail"),
]
