from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    SubjectViewSet, TeacherViewSet, ParentViewSet, SchoolClassViewSet,
    StudentViewSet, ScheduleViewSet, GradeViewSet, HomeworkViewSet,
    AttendanceViewSet, AnnouncementViewSet, SummaryAPIView, MeAPIView,
    LessonDayAPIView, LessonWorkspaceAPIView,
    RegisterAPIView, RegisterMetaAPIView, RegistrationRequestViewSet,
)

router = DefaultRouter()
router.register("subjects", SubjectViewSet, basename="subject")
router.register("teachers", TeacherViewSet, basename="teacher")
router.register("parents", ParentViewSet, basename="parent")
router.register("classes", SchoolClassViewSet, basename="class")
router.register("students", StudentViewSet, basename="student")
router.register("schedule", ScheduleViewSet, basename="schedule")
router.register("grades", GradeViewSet, basename="grade")
router.register("homework", HomeworkViewSet, basename="homework")
router.register("attendance", AttendanceViewSet, basename="attendance")
router.register("announcements", AnnouncementViewSet, basename="announcement")
router.register("registrations", RegistrationRequestViewSet, basename="registration")

urlpatterns = [
    path("", include(router.urls)),
    path("me/", MeAPIView.as_view(), name="me"),
    path("summary/", SummaryAPIView.as_view(), name="summary"),
    path("lessons/", LessonDayAPIView.as_view(), name="lesson-day"),
    path("lessons/workspace/", LessonWorkspaceAPIView.as_view(), name="lesson-workspace"),
    path("register/", RegisterAPIView.as_view(), name="register"),
    path("register/meta/", RegisterMetaAPIView.as_view(), name="register-meta"),
]
