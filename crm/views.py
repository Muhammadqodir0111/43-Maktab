import math
from datetime import date, timedelta

from django.contrib.auth import logout
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.db.models import Count, Q, Avg
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Subject, Teacher, Parent, SchoolClass, Student,
    Schedule, Grade, Homework, HomeworkSubmission, Attendance, Announcement,
    RegistrationRequest,
)
from .serializers import (
    SubjectSerializer, TeacherSerializer, ParentSerializer, SchoolClassSerializer,
    StudentSerializer, ScheduleSerializer, GradeSerializer, HomeworkSerializer,
    HomeworkSubmissionSerializer, AttendanceSerializer, AnnouncementSerializer,
    RegisterSerializer, RegistrationRequestSerializer,
)

WRITE_ACTIONS = ("create", "update", "partial_update", "destroy")


def role_of(user):
    if not user or not user.is_authenticated:
        return "guest"
    if user.is_staff:
        return "admin"
    if hasattr(user, "teacher_profile"):
        return "teacher"
    if hasattr(user, "student_profile"):
        return "student"
    if hasattr(user, "parent_profile"):
        return "parent"
    return "user"


def teacher_of(user):
    return getattr(user, "teacher_profile", None) if user and user.is_authenticated else None


# --- Chorak (quarter) hisob-kitobi -----------------------------------------

QUARTER_LABELS = {1: "I chorak", 2: "II chorak", 3: "III chorak", 4: "IV chorak"}


def academic_year_start(ref):
    return ref.year if ref.month >= 9 else ref.year - 1


def quarter_range(q, ref=None):
    ref = ref or date.today()
    ys = academic_year_start(ref)
    if q == 1:
        return date(ys, 9, 1), date(ys, 10, 31)
    if q == 2:
        return date(ys, 11, 1), date(ys, 12, 31)
    if q == 3:
        return date(ys + 1, 1, 1), date(ys + 1, 3, 31)
    return date(ys + 1, 4, 1), date(ys + 1, 5, 31)


def quarter_of(ref):
    m = ref.month
    if m in (9, 10):
        return 1
    if m in (11, 12):
        return 2
    if m in (1, 2, 3):
        return 3
    if m in (4, 5):
        return 4
    return 1


def round_half_up(x):
    return int(math.floor(x + 0.5))


def quarter_summary(class_id, subject_id, q, ref=None):
    """Sinf+fan+chorak bo'yicha o'quvchilar bahosi va chorak bahosi."""
    start, end = quarter_range(q, ref)
    base = (
        Grade.objects
        .filter(school_class_id=class_id, subject_id=subject_id,
                date__gte=start, date__lte=end)
        .exclude(type=Grade.CHORAK)
    )
    saved = {
        g.student_id: g for g in
        Grade.objects.filter(school_class_id=class_id, subject_id=subject_id,
                             type=Grade.CHORAK, date__gte=start, date__lte=end)
    }
    avg_map = {
        r["student"]: (r["avg"], r["count"])
        for r in base.values("student").annotate(avg=Avg("value"), count=Count("id"))
    }
    rows = []
    for s in Student.objects.filter(school_class_id=class_id, is_active=True).order_by("name"):
        avg, cnt = avg_map.get(s.id, (None, 0))
        sv = saved.get(s.id)
        rows.append({
            "student_id": s.id,
            "student_name": s.name,
            "average": round(avg, 2) if avg else None,
            "count": cnt,
            "computed": round_half_up(avg) if avg else None,
            "saved": sv.value if sv else None,
            "grade_id": sv.id if sv else None,
        })
    return start, end, rows


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class IsAdminOrTeacher(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.is_staff or hasattr(u, "teacher_profile")))


class RoleWriteMixin:
    """Yozish amallari uchun ruxsat; o'qish — har qanday kirgan foydalanuvchi."""

    write_permission_class = IsAdmin
    extra_write_actions = ()

    def get_permissions(self):
        if self.action in WRITE_ACTIONS or self.action in self.extra_write_actions:
            return [self.write_permission_class()]
        return [IsAuthenticated()]


# --------------------------------------------------------------------------
# Kirish / rol
# --------------------------------------------------------------------------

class MeAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        u = request.user
        role = role_of(u)
        data = {
            "username": u.username if u.is_authenticated else "",
            "role": role,
            "is_admin": role == "admin",
            "is_authenticated": u.is_authenticated,
            "student_id": None,
            "teacher_id": None,
            "parent_id": None,
            "display_name": "",
            "children": [],
        }
        if role == "student":
            s = u.student_profile
            data["student_id"] = s.pk
            data["display_name"] = s.name
            data["class_id"] = s.school_class_id
            data["class_name"] = s.class_name
        elif role == "teacher":
            t = u.teacher_profile
            data["teacher_id"] = t.pk
            data["display_name"] = t.full_name
        elif role == "parent":
            p = u.parent_profile
            data["parent_id"] = p.pk
            data["display_name"] = p.full_name
            data["children"] = [
                {"id": c.pk, "name": c.name, "class_id": c.school_class_id,
                 "class_name": c.class_name}
                for c in p.children.filter(is_active=True)
            ]
        elif role == "admin":
            data["display_name"] = u.get_full_name() or u.username
        return Response(data)


def logout_view(request):
    logout(request)
    return redirect("/login/?logged_out=1")


ROLE_LABELS_UI = {
    "admin": "Administrator",
    "teacher": "O'qituvchi",
    "student": "O'quvchi",
    "parent": "Ota-ona",
}


class RoleLoginView(LoginView):
    """Login sahifasida tanlangan rol foydalanuvchining haqiqiy roliga mos kelishini tekshiradi."""
    template_name = "login.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["roles"] = ROLE_LABELS_UI
        ctx["selected_role"] = self.request.POST.get("role") or "teacher"
        form = ctx.get("form")
        if form is not None:
            try:
                ctx["pending_error"] = any(
                    getattr(e, "code", "") == "inactive"
                    for e in form.non_field_errors().as_data()
                )
            except Exception:
                ctx["pending_error"] = False
        return ctx

    def form_valid(self, form):
        selected = (self.request.POST.get("role") or "").strip()
        user = form.get_user()
        actual = role_of(user)
        if selected and selected != actual:
            ctx = self.get_context_data(form=form)
            ctx["selected_role"] = selected
            ctx["role_error"] = (
                f"«{ROLE_LABELS_UI.get(selected, selected)}» roli tanlandi, lekin bu foydalanuvchi "
                f"«{ROLE_LABELS_UI.get(actual, actual)}». Iltimos, to'g'ri rolni tanlang."
            )
            return self.render_to_response(ctx, status=200)
        return super().form_valid(form)


# --------------------------------------------------------------------------
# Fanlar / O'qituvchilar / Ota-onalar / Sinflar
# --------------------------------------------------------------------------

class SubjectViewSet(RoleWriteMixin, viewsets.ModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer


class TeacherViewSet(RoleWriteMixin, viewsets.ModelViewSet):
    queryset = Teacher.objects.prefetch_related("subjects").all()
    serializer_class = TeacherSerializer


class ParentViewSet(RoleWriteMixin, viewsets.ModelViewSet):
    queryset = Parent.objects.prefetch_related("children").all()
    serializer_class = ParentSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        u = self.request.user
        if not u.is_staff and not hasattr(u, "teacher_profile"):
            own = getattr(u, "parent_profile", None)
            return qs.filter(pk=own.pk) if own else qs.none()
        return qs


class SchoolClassViewSet(RoleWriteMixin, viewsets.ModelViewSet):
    queryset = SchoolClass.objects.select_related("curator").all()
    serializer_class = SchoolClassSerializer


# --------------------------------------------------------------------------
# O'quvchilar
# --------------------------------------------------------------------------

class StudentViewSet(RoleWriteMixin, viewsets.ModelViewSet):
    queryset = Student.objects.select_related("school_class").prefetch_related("parents").all()
    serializer_class = StudentSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        u = self.request.user
        role = role_of(u)
        if role == "student":
            own = getattr(u, "student_profile", None)
            return qs.filter(pk=own.pk) if own else qs.none()
        if role == "parent":
            own = getattr(u, "parent_profile", None)
            return qs.filter(parents=own) if own else qs.none()
        if role in ("teacher", "admin"):
            params = self.request.query_params
            if params.get("class"):
                qs = qs.filter(school_class_id=params["class"])
            if params.get("active") == "1":
                qs = qs.filter(is_active=True)
            return qs
        return qs.none()

    @action(detail=True, methods=["get"])
    def dashboard(self, request, pk=None):
        student = self.get_object()
        grades = Grade.objects.filter(student=student).exclude(type=Grade.CHORAK)
        att = Attendance.objects.filter(student=student)
        subs = HomeworkSubmission.objects.filter(student=student)

        quarter_map = {}
        for g in (Grade.objects.filter(student=student, type=Grade.CHORAK)
                  .select_related("subject").order_by("subject__name", "-date")):
            quarter_map.setdefault(g.subject_id, g)
        quarter_grades = [
            {"subject_id": g.subject_id, "subject_name": g.subject.name,
             "value": g.value, "date": g.date.isoformat()}
            for g in quarter_map.values()
        ]

        total_att = att.count()
        present = att.filter(status__in=[Attendance.PRESENT, Attendance.LATE]).count()
        att_percent = round(present / total_att * 100, 1) if total_att else 0
        avg_grade = grades.aggregate(a=Avg("value"))["a"]
        avg_grade = round(avg_grade, 2) if avg_grade else 0

        by_subject = (
            grades.values("subject", "subject__name")
            .annotate(avg=Avg("value"), count=Count("id"))
            .order_by("subject__name")
        )
        subject_stats = [
            {"subject_id": r["subject"], "subject_name": r["subject__name"],
             "avg": round(r["avg"], 2), "count": r["count"]}
            for r in by_subject
        ]

        today = date.today()
        schedule = (
            Schedule.objects.filter(school_class=student.school_class,
                                    weekday=today.isoweekday(), is_active=True)
            .select_related("subject", "teacher").order_by("period")
        ) if student.school_class else Schedule.objects.none()

        return Response({
            "student": StudentSerializer(student).data,
            "stats": {
                "grades_count": grades.count(),
                "avg_grade": avg_grade,
                "attendance_percent": att_percent,
                "present": present,
                "absent": total_att - present,
                "homework_total": subs.count(),
                "homework_done": subs.filter(is_done=True).count(),
            },
            "subjects": subject_stats,
            "quarter_grades": quarter_grades,
            "recent_grades": GradeSerializer(
                grades.select_related("subject", "teacher").order_by("-date")[:15], many=True
            ).data,
            "today_schedule": ScheduleSerializer(schedule, many=True).data,
        })

    @action(detail=True, methods=["get"])
    def attendance(self, request, pk=None):
        student = self.get_object()
        records = Attendance.objects.filter(student=student).select_related("schedule__subject")
        total = records.count()
        present = records.filter(status__in=[Attendance.PRESENT, Attendance.LATE]).count()
        return Response({
            "student": StudentSerializer(student).data,
            "stats": {
                "total": total,
                "present": present,
                "absent": total - present,
                "percent": round(present / total * 100, 1) if total else 0,
            },
            "records": AttendanceSerializer(
                records.order_by("-date")[:90], many=True
            ).data,
        })


# --------------------------------------------------------------------------
# Dars jadvali
# --------------------------------------------------------------------------

class ScheduleViewSet(RoleWriteMixin, viewsets.ModelViewSet):
    queryset = Schedule.objects.select_related("school_class", "subject", "teacher").all()
    serializer_class = ScheduleSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get("class"):
            qs = qs.filter(school_class_id=p["class"])
        if p.get("teacher"):
            qs = qs.filter(teacher_id=p["teacher"])
        if p.get("weekday"):
            qs = qs.filter(weekday=p["weekday"])
        return qs


# --------------------------------------------------------------------------
# Baholar
# --------------------------------------------------------------------------

class GradeViewSet(RoleWriteMixin, viewsets.ModelViewSet):
    write_permission_class = IsAdminOrTeacher
    queryset = Grade.objects.select_related("student", "subject", "teacher").all()
    serializer_class = GradeSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        u = self.request.user
        role = role_of(u)
        if role == "teacher":
            t = getattr(u, "teacher_profile", None)
            qs = qs.filter(teacher=t) if t else qs.none()
        elif role == "student":
            own = getattr(u, "student_profile", None)
            qs = qs.filter(student=own) if own else qs.none()
        elif role == "parent":
            own = getattr(u, "parent_profile", None)
            qs = qs.filter(student__parents=own) if own else qs.none()
        elif role != "admin":
            qs = qs.none()

        p = self.request.query_params
        for key, field in (("class", "school_class_id"), ("subject", "subject_id"),
                           ("student", "student_id"), ("type", "type")):
            if p.get(key):
                qs = qs.filter(**{field: p[key]})
        if p.get("start"):
            qs = qs.filter(date__gte=p["start"])
        if p.get("end"):
            qs = qs.filter(date__lte=p["end"])
        return qs

    @action(detail=False, methods=["get"])
    def journal(self, request):
        """Sinf + fan bo'yicha baholar jurnali (kunlar bo'ylab)."""
        class_id = request.query_params.get("class")
        subject_id = request.query_params.get("subject")
        if not class_id or not subject_id:
            return Response({"detail": "class va subject talab qilinadi"},
                            status=status.HTTP_400_BAD_REQUEST)

        students = Student.objects.filter(
            school_class_id=class_id, is_active=True
        ).order_by("name")
        qs = Grade.objects.filter(
            school_class_id=class_id, subject_id=subject_id
        )
        if request.query_params.get("start"):
            qs = qs.filter(date__gte=request.query_params["start"])
        if request.query_params.get("end"):
            qs = qs.filter(date__lte=request.query_params["end"])

        dates = list(qs.values_list("date", flat=True).distinct().order_by("date"))
        cells = {}
        meta = {}
        for g in qs:
            key = f"{g.student_id}:{g.date.isoformat()}"
            cells[key] = {"id": g.pk, "value": g.value, "type": g.type,
                          "comment": g.comment}
            meta.setdefault(g.student_id, []).append(g.value)

        ref = None
        if request.query_params.get("start"):
            try:
                ref = date.fromisoformat(request.query_params["start"])
            except ValueError:
                ref = None
        ref = ref or date.today()
        q = quarter_of(ref)
        _, _, qrows = quarter_summary(class_id, subject_id, q, ref)
        qmap = {r["student_id"]: r for r in qrows}

        rows = []
        for s in students:
            vals = meta.get(s.id, [])
            qr = qmap.get(s.id, {})
            rows.append({
                "student_id": s.id,
                "student_name": s.name,
                "average": round(sum(vals) / len(vals), 2) if vals else None,
                "quarter_computed": qr.get("computed"),
                "quarter_saved": qr.get("saved"),
            })

        return Response({
            "students": rows,
            "dates": [d.isoformat() for d in dates],
            "cells": cells,
            "quarter": q,
            "quarter_label": QUARTER_LABELS[q],
        })

    @action(detail=False, methods=["get", "post"])
    def quarter(self, request):
        """Chorak bahosini ko'rish (GET) va saqlash (POST)."""
        if request.method == "GET":
            class_id = request.query_params.get("class")
            subject_id = request.query_params.get("subject")
            if not class_id or not subject_id:
                return Response({"detail": "class va subject talab qilinadi"},
                                status=status.HTTP_400_BAD_REQUEST)
            try:
                q = int(request.query_params.get("quarter") or quarter_of(date.today()))
            except ValueError:
                q = quarter_of(date.today())
            start, end, rows = quarter_summary(class_id, subject_id, q)
            return Response({
                "quarter": q, "label": QUARTER_LABELS[q],
                "start": start.isoformat(), "end": end.isoformat(),
                "rows": rows,
            })

        payload = request.data or {}
        class_id = payload.get("class")
        subject_id = payload.get("subject")
        if not class_id or not subject_id:
            return Response({"detail": "class va subject talab qilinadi"},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            q = int(payload.get("quarter") or quarter_of(date.today()))
        except (TypeError, ValueError):
            q = quarter_of(date.today())
        start, end = quarter_range(q)
        teacher = teacher_of(request.user)
        saved = 0
        for row in payload.get("grades") or []:
            value = row.get("value")
            student_id = row.get("student")
            if value in (None, "") or not student_id:
                continue
            g = Grade.objects.filter(
                student_id=student_id, subject_id=subject_id,
                type=Grade.CHORAK, date__gte=start, date__lte=end,
            ).first()
            if g:
                g.value = value
                g.school_class_id = class_id
                if teacher:
                    g.teacher = teacher
                g.save()
            else:
                Grade.objects.create(
                    student_id=student_id, subject_id=subject_id,
                    school_class_id=class_id, date=end, value=value,
                    type=Grade.CHORAK, teacher=teacher,
                )
            saved += 1
        return Response({"saved": saved, "quarter": q})


# --------------------------------------------------------------------------
# Uyga vazifa
# --------------------------------------------------------------------------

class HomeworkViewSet(RoleWriteMixin, viewsets.ModelViewSet):
    write_permission_class = IsAdminOrTeacher
    queryset = Homework.objects.select_related("school_class", "subject", "teacher").all()
    serializer_class = HomeworkSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        u = self.request.user
        role = role_of(u)
        if role == "teacher":
            t = getattr(u, "teacher_profile", None)
            qs = qs.filter(teacher=t) if t else qs.none()
        elif role == "student":
            own = getattr(u, "student_profile", None)
            qs = qs.filter(school_class=own.school_class) if own and own.school_class else qs.none()
        elif role == "parent":
            own = getattr(u, "parent_profile", None)
            if own:
                class_ids = own.children.values_list("school_class_id", flat=True)
                qs = qs.filter(school_class_id__in=[c for c in class_ids if c])
            else:
                qs = qs.none()
        elif role != "admin":
            qs = qs.none()

        p = self.request.query_params
        if p.get("class"):
            qs = qs.filter(school_class_id=p["class"])
        if p.get("subject"):
            qs = qs.filter(subject_id=p["subject"])
        if p.get("date"):
            qs = qs.filter(date=p["date"])
        return qs

    @action(detail=True, methods=["get"])
    def submissions(self, request, pk=None):
        hw = self.get_object()
        existing = {s.student_id: s for s in hw.submissions.all()}
        students = Student.objects.filter(school_class=hw.school_class, is_active=True).order_by("name")
        data = []
        for s in students:
            sub = existing.get(s.id)
            data.append({
                "student_id": s.id,
                "student_name": s.name,
                "submission_id": sub.pk if sub else None,
                "is_done": sub.is_done if sub else False,
                "grade": sub.grade if sub else None,
                "comment": sub.comment if sub else "",
            })
        return Response({"homework": HomeworkSerializer(hw).data, "rows": data})

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        """O'qituvchi/admin bitta o'quvchi holatini belgilaydi."""
        hw = self.get_object()
        student_id = request.data.get("student")
        if not student_id:
            return Response({"detail": "student talab qilinadi"},
                            status=status.HTTP_400_BAD_REQUEST)
        sub, _ = HomeworkSubmission.objects.update_or_create(
            homework=hw, student_id=student_id,
            defaults={
                "is_done": bool(request.data.get("is_done", False)),
                "grade": request.data.get("grade") or None,
                "comment": request.data.get("comment", ""),
            },
        )
        return Response(HomeworkSubmissionSerializer(sub).data)


# --------------------------------------------------------------------------
# Davomat
# --------------------------------------------------------------------------

class AttendanceViewSet(RoleWriteMixin, viewsets.ModelViewSet):
    write_permission_class = IsAdminOrTeacher
    extra_write_actions = ("mark", "generate")
    queryset = Attendance.objects.select_related("student", "schedule__subject").all()
    serializer_class = AttendanceSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        u = self.request.user
        role = role_of(u)
        if role == "student":
            own = getattr(u, "student_profile", None)
            qs = qs.filter(student=own) if own else qs.none()
        elif role == "parent":
            own = getattr(u, "parent_profile", None)
            qs = qs.filter(student__parents=own) if own else qs.none()
        elif role not in ("admin", "teacher"):
            qs = qs.none()

        p = self.request.query_params
        if p.get("date"):
            qs = qs.filter(date=p["date"])
        if p.get("class"):
            qs = qs.filter(student__school_class_id=p["class"])
        if p.get("student"):
            qs = qs.filter(student_id=p["student"])
        return qs

    @action(detail=False, methods=["post"])
    def mark(self, request):
        student_id = request.data.get("student")
        schedule_id = request.data.get("schedule") or None
        day = request.data.get("date", date.today().isoformat())
        status_val = request.data.get("status", Attendance.PRESENT)
        reason = request.data.get("reason", "")
        if not student_id:
            return Response({"detail": "student talab qilinadi"},
                            status=status.HTTP_400_BAD_REQUEST)
        att, created = Attendance.objects.update_or_create(
            student_id=student_id, schedule_id=schedule_id, date=day,
            defaults={"status": status_val, "reason": reason},
        )
        return Response(
            self.serializer_class(att).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"])
    def generate(self, request):
        """Sinf o'quvchilariga sana uchun davomat yozuvlarini yaratadi."""
        class_id = request.data.get("class")
        day = request.data.get("date", date.today().isoformat())
        schedule_id = request.data.get("schedule") or None
        students = Student.objects.filter(is_active=True)
        if class_id:
            students = students.filter(school_class_id=class_id)
        created = 0
        for s in students:
            _, was_created = Attendance.objects.get_or_create(
                student=s, schedule_id=schedule_id, date=day,
            )
            created += 1 if was_created else 0
        return Response({"created": created, "date": day})


# --------------------------------------------------------------------------
# E'lonlar
# --------------------------------------------------------------------------

class AnnouncementViewSet(RoleWriteMixin, viewsets.ModelViewSet):
    write_permission_class = IsAdminOrTeacher
    queryset = Announcement.objects.select_related("school_class", "author").all()
    serializer_class = AnnouncementSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        u = self.request.user
        role = role_of(u)
        if role == "admin":
            return qs
        if role == "teacher":
            return qs.filter(audience__in=["all", "teachers"])
        if role == "student":
            own = getattr(u, "student_profile", None)
            cond = Q(audience__in=["all", "students"])
            if own and own.school_class_id:
                cond |= Q(audience="class", school_class_id=own.school_class_id)
            return qs.filter(cond)
        if role == "parent":
            own = getattr(u, "parent_profile", None)
            class_ids = list(own.children.values_list("school_class_id", flat=True)) if own else []
            cond = Q(audience__in=["all", "parents"])
            cond |= Q(audience="class", school_class_id__in=[c for c in class_ids if c])
            return qs.filter(cond)
        return qs.none()


# --------------------------------------------------------------------------
# Ro'yxatdan o'tish va admin tasdiqlash
# --------------------------------------------------------------------------

class RegisterAPIView(APIView):
    """Ochiq: har kim so'rov yuboradi, hisob admin tasdiqlagach faollashadi."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        req = serializer.save()
        return Response({
            "id": req.id,
            "status": req.status,
            "detail": "So'rovingiz yuborildi. Admin tasdiqlagach tizimga kira olasiz.",
        }, status=status.HTTP_201_CREATED)


class RegisterMetaAPIView(APIView):
    """Ochiq: ro'yxatdan o'tish sahifasi uchun sinflar va rollar."""
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            "classes": list(
                SchoolClass.objects.filter(is_active=True).values("id", "name")
            ),
            "roles": [
                {"value": v, "label": l} for v, l in RegistrationRequest.ROLE_CHOICES
            ],
        })


class RegistrationRequestViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdmin]
    queryset = RegistrationRequest.objects.select_related("school_class").all()
    serializer_class = RegistrationRequestSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        st = self.request.query_params.get("status")
        if st:
            qs = qs.filter(status=st)
        return qs

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        req = self.get_object()
        if req.status == RegistrationRequest.APPROVED:
            return Response({"detail": "Allaqachon tasdiqlangan."},
                            status=status.HTTP_400_BAD_REQUEST)
        if not req.user:
            return Response({"detail": "Tegishli login topilmadi."},
                            status=status.HTTP_400_BAD_REQUEST)
        req.approve(reviewer=request.user)
        return Response({"detail": "Tasdiqlandi.", "status": req.status})

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        req = self.get_object()
        req.reject(reviewer=request.user)
        return Response({"detail": "Rad etildi.", "status": req.status})


# --------------------------------------------------------------------------
# Dars o'tkazish (davomat + baho + uyga vazifa bitta oynada)
# --------------------------------------------------------------------------

class LessonDayAPIView(APIView):
    """Berilgan sinf va kun uchun darslar ro'yxati (jadval asosida)."""
    permission_classes = [IsAdminOrTeacher]

    def get(self, request):
        class_id = request.query_params.get("class")
        if not class_id:
            return Response({"detail": "class talab qilinadi"},
                            status=status.HTTP_400_BAD_REQUEST)
        day = request.query_params.get("date") or date.today().isoformat()
        try:
            d = date.fromisoformat(day)
        except ValueError:
            return Response({"detail": "date noto'g'ri"},
                            status=status.HTTP_400_BAD_REQUEST)

        schedules = (
            Schedule.objects
            .filter(school_class_id=class_id, weekday=d.isoweekday(), is_active=True)
            .select_related("subject", "teacher")
            .order_by("period")
        )
        students_count = Student.objects.filter(
            school_class_id=class_id, is_active=True
        ).count()

        lessons = []
        for s in schedules:
            att = Attendance.objects.filter(schedule=s, date=day)
            grades = Grade.objects.filter(
                school_class_id=class_id, subject=s.subject, date=day
            ).exclude(type=Grade.CHORAK)
            hw = Homework.objects.filter(
                school_class_id=class_id, subject=s.subject, date=day
            ).first()
            lessons.append({
                "id": s.id,
                "period": s.period,
                "subject_id": s.subject_id,
                "subject_name": s.subject.name,
                "teacher_name": s.teacher.full_name if s.teacher else "",
                "start_time": s.start_time.strftime("%H:%M") if s.start_time else "",
                "end_time": s.end_time.strftime("%H:%M") if s.end_time else "",
                "room": s.room,
                "students_count": students_count,
                "attendance_marked": att.count(),
                "grades_count": grades.count(),
                "has_homework": bool(hw),
                "homework_title": hw.title if hw else "",
            })
        return Response({"date": day, "weekday": d.isoweekday(), "lessons": lessons})


class LessonWorkspaceAPIView(APIView):
    """Bitta dars: davomat, baho va uyga vazifani birga o'qish/saqlash."""

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdminOrTeacher()]
        return [IsAuthenticated()]

    def _schedule(self, request):
        schedule_id = request.query_params.get("schedule") or (request.data or {}).get("schedule")
        if not schedule_id:
            return None, Response({"detail": "schedule talab qilinadi"},
                                  status=status.HTTP_400_BAD_REQUEST)
        try:
            return get_object_or_404(Schedule, pk=schedule_id), None
        except Exception:
            return None, Response({"detail": "Dars topilmadi"},
                                  status=status.HTTP_404_NOT_FOUND)

    def get(self, request):
        s, err = self._schedule(request)
        if err:
            return err
        day = request.query_params.get("date") or date.today().isoformat()

        students = Student.objects.filter(
            school_class=s.school_class, is_active=True
        ).order_by("name")
        att_map = {
            a.student_id: a
            for a in Attendance.objects.filter(schedule=s, date=day)
        }
        grade_map = {}
        for g in (Grade.objects
                  .filter(school_class=s.school_class, subject=s.subject, date=day)
                  .exclude(type=Grade.CHORAK)):
            grade_map[g.student_id] = g
        hw = Homework.objects.filter(
            school_class=s.school_class, subject=s.subject, date=day
        ).first()

        rows = []
        for st in students:
            a = att_map.get(st.id)
            g = grade_map.get(st.id)
            rows.append({
                "student_id": st.id,
                "student_name": st.name,
                "status": a.status if a else "",
                "reason": a.reason if a else "",
                "grade_id": g.pk if g else None,
                "grade_value": g.value if g else None,
                "grade_comment": g.comment if g else "",
            })

        return Response({
            "schedule": {
                "id": s.id,
                "class_id": s.school_class_id,
                "class_name": s.school_class.name,
                "subject_id": s.subject_id,
                "subject_name": s.subject.name,
                "teacher_name": s.teacher.full_name if s.teacher else "",
                "period": s.period,
                "start_time": s.start_time.strftime("%H:%M") if s.start_time else "",
                "end_time": s.end_time.strftime("%H:%M") if s.end_time else "",
                "room": s.room,
            },
            "date": day,
            "students": rows,
            "homework": {
                "id": hw.pk, "title": hw.title, "description": hw.description,
                "due_date": hw.due_date.isoformat() if hw.due_date else "",
            } if hw else None,
        })

    def post(self, request):
        s, err = self._schedule(request)
        if err:
            return err
        data = request.data or {}
        day = data.get("date") or date.today().isoformat()
        teacher = teacher_of(request.user)

        att_saved = 0
        for row in data.get("attendance") or []:
            student_id = row.get("student")
            status_val = row.get("status")
            if not student_id:
                continue
            if not status_val:
                Attendance.objects.filter(
                    student_id=student_id, schedule=s, date=day
                ).delete()
                continue
            Attendance.objects.update_or_create(
                student_id=student_id, schedule=s, date=day,
                defaults={"status": status_val, "reason": row.get("reason", "")},
            )
            att_saved += 1

        grade_saved = 0
        for row in data.get("grades") or []:
            student_id = row.get("student")
            value = row.get("value")
            if not student_id:
                continue
            existing = Grade.objects.filter(
                school_class=s.school_class, subject=s.subject,
                student_id=student_id, date=day,
            ).exclude(type=Grade.CHORAK).first()
            if value in (None, ""):
                if existing:
                    existing.delete()
                continue
            if existing:
                existing.value = value
                existing.comment = row.get("comment", "")
                if teacher:
                    existing.teacher = teacher
                existing.save()
            else:
                Grade.objects.create(
                    school_class=s.school_class, subject=s.subject,
                    student_id=student_id, date=day, value=value,
                    type=Grade.JORIY, comment=row.get("comment", ""),
                    teacher=teacher,
                )
            grade_saved += 1

        hw_data = data.get("homework")
        if hw_data is not None:
            title = (hw_data.get("title") or "").strip()
            existing_hw = Homework.objects.filter(
                school_class=s.school_class, subject=s.subject, date=day
            ).first()
            if title:
                due = hw_data.get("due_date") or None
                if existing_hw:
                    existing_hw.title = title
                    existing_hw.description = hw_data.get("description", "")
                    existing_hw.due_date = due
                    existing_hw.save()
                else:
                    Homework.objects.create(
                        school_class=s.school_class, subject=s.subject,
                        teacher=teacher, date=day, due_date=due,
                        title=title, description=hw_data.get("description", ""),
                    )
            elif existing_hw:
                existing_hw.delete()

        return Response({
            "date": day,
            "attendance_saved": att_saved,
            "grades_saved": grade_saved,
        })


# --------------------------------------------------------------------------
# Boshqaruv paneli statistikasi
# --------------------------------------------------------------------------

DAY_NAMES = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]


def build_week_records(start_of_week, att_qs):
    week_map = {}
    for day, st in att_qs.values_list("date", "status"):
        key = day.isoformat()
        week_map.setdefault(key, {"present": 0, "absent": 0})
        if st in (Attendance.PRESENT, Attendance.LATE):
            week_map[key]["present"] += 1
        else:
            week_map[key]["absent"] += 1
    records = []
    for i in range(7):
        day = start_of_week + timedelta(days=i)
        data = week_map.get(day.isoformat(), {"present": 0, "absent": 0})
        data.update({"date": day.isoformat(), "label": DAY_NAMES[i]})
        records.append(data)
    return records


class SummaryAPIView(APIView):
    permission_classes = [IsAdminOrTeacher]

    def get(self, request):
        if role_of(request.user) == "teacher":
            return Response(self._teacher_summary(request.user.teacher_profile))
        return Response(self._admin_summary())

    def _admin_summary(self):
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())

        att_today = Attendance.objects.filter(date=today)
        total = att_today.count()
        present = att_today.filter(status__in=[Attendance.PRESENT, Attendance.LATE]).count()
        percent = round(present / total * 100, 1) if total else 0
        week_records = build_week_records(
            start_of_week,
            Attendance.objects.filter(date__gte=start_of_week, date__lte=today),
        )
        grade_avg = Grade.objects.aggregate(a=Avg("value"))["a"]

        return {
            "role": "admin",
            "students_total": Student.objects.count(),
            "students_active": Student.objects.filter(is_active=True).count(),
            "teachers_total": Teacher.objects.filter(is_active=True).count(),
            "classes_total": SchoolClass.objects.filter(is_active=True).count(),
            "subjects_total": Subject.objects.filter(is_active=True).count(),
            "today_present": present,
            "today_absent": total - present,
            "today_total": total,
            "today_percent": percent,
            "grade_avg": round(grade_avg, 2) if grade_avg else 0,
            "week_records": week_records,
            "class_stats": SchoolClassSerializer(
                SchoolClass.objects.filter(is_active=True).select_related("curator")[:12],
                many=True,
            ).data,
            "latest_grades": GradeSerializer(
                Grade.objects.select_related("student", "subject").order_by("-created_at")[:6],
                many=True,
            ).data,
            "announcements": AnnouncementSerializer(
                Announcement.objects.select_related("author").order_by("-created_at")[:4],
                many=True,
            ).data,
        }

    def _teacher_summary(self, teacher):
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())

        schedules = Schedule.objects.filter(teacher=teacher, is_active=True)
        class_ids = list(schedules.values_list("school_class_id", flat=True).distinct())
        students_count = Student.objects.filter(
            school_class_id__in=class_ids, is_active=True
        ).count()

        grades = Grade.objects.filter(teacher=teacher)
        grade_avg = grades.aggregate(a=Avg("value"))["a"]

        att_today = Attendance.objects.filter(schedule__teacher=teacher, date=today)
        total = att_today.count()
        present = att_today.filter(status__in=[Attendance.PRESENT, Attendance.LATE]).count()
        percent = round(present / total * 100, 1) if total else 0

        week_records = build_week_records(
            start_of_week,
            Attendance.objects.filter(schedule__teacher=teacher,
                                     date__gte=start_of_week, date__lte=today),
        )

        lessons = []
        for s in (schedules.filter(weekday=today.isoweekday())
                  .select_related("school_class", "subject").order_by("period")):
            att = Attendance.objects.filter(schedule=s, date=today)
            lessons.append({
                "schedule_id": s.id,
                "class_name": s.school_class.name,
                "subject_name": s.subject.name,
                "period": s.period,
                "start_time": s.start_time.strftime("%H:%M") if s.start_time else "",
                "end_time": s.end_time.strftime("%H:%M") if s.end_time else "",
                "room": s.room,
                "students_count": Student.objects.filter(
                    school_class=s.school_class, is_active=True).count(),
                "attendance_marked": att.count(),
            })

        announcements = Announcement.objects.filter(
            audience__in=["all", "teachers"]
        ).select_related("author").order_by("-created_at")[:4]

        return {
            "role": "teacher",
            "teacher": {"id": teacher.id, "name": teacher.full_name},
            "stats": {
                "classes": len(class_ids),
                "students": students_count,
                "lessons_today": len(lessons),
                "grades_total": grades.count(),
                "grade_avg": round(grade_avg, 2) if grade_avg else 0,
                "today_present": present,
                "today_total": total,
                "today_percent": percent,
            },
            "week_records": week_records,
            "today_lessons": lessons,
            "latest_grades": GradeSerializer(
                grades.select_related("student", "subject").order_by("-created_at")[:6],
                many=True,
            ).data,
            "announcements": AnnouncementSerializer(announcements, many=True).data,
        }
