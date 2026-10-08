from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from .models import (
    Subject, Teacher, Parent, SchoolClass, Student,
    Schedule, Grade, Homework, Attendance, Announcement, RegistrationRequest,
)


class BaseSetup(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("admin", "a@a.uz", "admin123")
        cls.subject = Subject.objects.create(name="Matematika", code="MAT")
        cls.tclass = SchoolClass.objects.create(name="5-A", year="2025-2026")

        cls.teacher_user = User.objects.create_user("teacher", password="teacher123")
        cls.teacher = Teacher.objects.create(user=cls.teacher_user, full_name="Ali Karimov")
        cls.teacher.subjects.add(cls.subject)

        cls.parent_user = User.objects.create_user("parent", password="parent123")
        cls.parent = Parent.objects.create(user=cls.parent_user, full_name="Baxtiyor A.")

        cls.student_user = User.objects.create_user("student", password="student123")
        cls.student = Student.objects.create(
            user=cls.student_user, name="Jasur Abdullayev", school_class=cls.tclass,
        )
        cls.student.parents.add(cls.parent)

        Schedule.objects.create(
            school_class=cls.tclass, subject=cls.subject, teacher=cls.teacher,
            weekday=1, period=1, start_time="08:30", end_time="09:15",
        )
        Grade.objects.create(
            student=cls.student, subject=cls.subject, school_class=cls.tclass,
            teacher=cls.teacher, date=date(2026, 9, 15), value=5,
        )


class RoleAccessTests(BaseSetup):
    def test_me_admin(self):
        c = APIClient()
        c.force_authenticate(self.admin)
        r = c.get("/api/me/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["role"], "admin")

    def test_me_student(self):
        c = APIClient()
        c.force_authenticate(self.student_user)
        r = c.get("/api/me/")
        self.assertEqual(r.data["role"], "student")
        self.assertEqual(r.data["student_id"], self.student.id)

    def test_me_parent_children(self):
        c = APIClient()
        c.force_authenticate(self.parent_user)
        r = c.get("/api/me/")
        self.assertEqual(r.data["role"], "parent")
        self.assertEqual(len(r.data["children"]), 1)

    def test_student_cannot_create_class(self):
        c = APIClient()
        c.force_authenticate(self.student_user)
        r = c.post("/api/classes/", {"name": "X"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_student_sees_only_own_grades(self):
        other = Student.objects.create(name="Boshqa", school_class=self.tclass)
        Grade.objects.create(student=other, subject=self.subject, date=date(2026, 9, 15), value=2)
        c = APIClient()
        c.force_authenticate(self.student_user)
        r = c.get("/api/grades/")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["student"], self.student.id)

    def test_parent_sees_child_grades(self):
        c = APIClient()
        c.force_authenticate(self.parent_user)
        r = c.get("/api/grades/")
        self.assertEqual(len(r.data), 1)


class TeacherWorkflowTests(BaseSetup):
    def test_teacher_creates_grade(self):
        c = APIClient()
        c.force_authenticate(self.teacher_user)
        r = c.post("/api/grades/", {
            "student": self.student.id, "subject": self.subject.id,
            "date": "2026-09-16", "value": 4, "type": "joriy",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Grade.objects.filter(value=4).count(), 1)

    def test_teacher_cannot_create_teacher(self):
        c = APIClient()
        c.force_authenticate(self.teacher_user)
        r = c.post("/api/teachers/", {"full_name": "Yangi"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_teacher_marks_attendance(self):
        c = APIClient()
        c.force_authenticate(self.teacher_user)
        r = c.post("/api/attendance/mark/", {
            "student": self.student.id, "date": "2026-09-16", "status": "absent",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(Attendance.objects.filter(status="absent").exists())


class JournalTests(BaseSetup):
    def test_journal_returns_cells(self):
        c = APIClient()
        c.force_authenticate(self.admin)
        r = c.get(f"/api/grades/journal/?class={self.tclass.id}&subject={self.subject.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["students"]), 1)
        self.assertIn(f"{self.student.id}:2026-09-15", r.data["cells"])


class HomeworkTests(BaseSetup):
    def test_submit_homework(self):
        hw = Homework.objects.create(
            school_class=self.tclass, subject=self.subject,
            teacher=self.teacher, date=date(2026, 9, 16), title="Test",
        )
        c = APIClient()
        c.force_authenticate(self.teacher_user)
        r = c.post(f"/api/homework/{hw.id}/submit/", {
            "student": self.student.id, "is_done": True, "grade": 5,
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(hw.submissions.first().is_done)

    def test_student_dashboard(self):
        c = APIClient()
        c.force_authenticate(self.student_user)
        r = c.get(f"/api/students/{self.student.id}/dashboard/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["stats"]["grades_count"], 1)


class LessonWorkspaceTests(BaseSetup):
    def test_lesson_day_lists_lessons(self):
        c = APIClient()
        c.force_authenticate(self.teacher_user)
        r = c.get(f"/api/lessons/?class={self.tclass.id}&date=2026-09-14")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["lessons"]), 1)
        self.assertEqual(r.data["lessons"][0]["subject_name"], "Matematika")

    def test_workspace_saves_attendance_grade_homework(self):
        sch = Schedule.objects.get(school_class=self.tclass, weekday=1, period=1)
        c = APIClient()
        c.force_authenticate(self.teacher_user)
        r = c.post("/api/lessons/workspace/", {
            "schedule": sch.id, "date": "2026-09-14",
            "attendance": [{"student": self.student.id, "status": "late"}],
            "grades": [{"student": self.student.id, "value": 5}],
            "homework": {"title": "12-bet", "description": "mashq", "due_date": "2026-09-16"},
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["attendance_saved"], 1)
        self.assertEqual(r.data["grades_saved"], 1)
        self.assertTrue(Attendance.objects.filter(student=self.student, status="late").exists())
        self.assertTrue(Grade.objects.filter(student=self.student, value=5, date=date(2026, 9, 14)).exists())
        self.assertTrue(Homework.objects.filter(title="12-bet").exists())

    def test_student_cannot_save_workspace(self):
        sch = Schedule.objects.get(school_class=self.tclass, weekday=1, period=1)
        c = APIClient()
        c.force_authenticate(self.student_user)
        r = c.post("/api/lessons/workspace/", {
            "schedule": sch.id, "date": "2026-09-14", "attendance": [],
        }, format="json")
        self.assertEqual(r.status_code, 403)


class QuarterGradeTests(BaseSetup):
    def test_quarter_computed_from_grades(self):
        c = APIClient()
        c.force_authenticate(self.admin)
        r = c.get(f"/api/grades/quarter/?class={self.tclass.id}&subject={self.subject.id}&quarter=1")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["label"], "I chorak")
        self.assertEqual(r.data["rows"][0]["computed"], 5)

    def test_quarter_save_creates_chorak_grade(self):
        c = APIClient()
        c.force_authenticate(self.teacher_user)
        r = c.post("/api/grades/quarter/", {
            "class": self.tclass.id, "subject": self.subject.id, "quarter": 1,
            "grades": [{"student": self.student.id, "value": 4}],
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["saved"], 1)
        self.assertTrue(
            Grade.objects.filter(student=self.student, type="chorak", value=4).exists()
        )

    def test_journal_includes_quarter(self):
        c = APIClient()
        c.force_authenticate(self.admin)
        r = c.get(
            f"/api/grades/journal/?class={self.tclass.id}&subject={self.subject.id}"
            "&start=2026-09-01&end=2026-09-30"
        )
        self.assertEqual(r.data["quarter"], 1)
        self.assertEqual(r.data["students"][0]["quarter_computed"], 5)


class RoleLoginTests(BaseSetup):
    def test_login_with_correct_role(self):
        r = self.client.post("/login/", {
            "username": "teacher", "password": "teacher123", "role": "teacher",
        })
        self.assertEqual(r.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_with_wrong_role_rejected(self):
        r = self.client.post("/login/", {
            "username": "teacher", "password": "teacher123", "role": "student",
        })
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(r, "roli tanlandi", status_code=200)

    def test_admin_login_with_admin_role(self):
        r = self.client.post("/login/", {
            "username": "admin", "password": "admin123", "role": "admin",
        })
        self.assertEqual(r.status_code, 302)


class TeacherDashboardTests(BaseSetup):
    def test_teacher_summary_is_teacher_scoped(self):
        c = APIClient()
        c.force_authenticate(self.teacher_user)
        r = c.get("/api/summary/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["role"], "teacher")
        self.assertEqual(r.data["stats"]["classes"], 1)
        self.assertIn("today_lessons", r.data)

    def test_admin_summary_is_school_wide(self):
        c = APIClient()
        c.force_authenticate(self.admin)
        r = c.get("/api/summary/")
        self.assertEqual(r.data["role"], "admin")
        self.assertEqual(r.data["students_total"], 1)


class RegistrationTests(BaseSetup):
    def _payload(self, **over):
        data = {
            "role": "teacher", "full_name": "Yangi O'qituvchi",
            "username": "yangi_teacher", "password": "parol123",
        }
        data.update(over)
        return data

    def test_register_creates_pending_request(self):
        r = APIClient().post("/api/register/", self._payload(), format="json")
        self.assertEqual(r.status_code, 201)
        req = RegistrationRequest.objects.get(username="yangi_teacher")
        self.assertEqual(req.status, RegistrationRequest.PENDING)
        self.assertFalse(req.user.is_active)

    def test_register_duplicate_username_rejected(self):
        r = APIClient().post("/api/register/", self._payload(username="teacher"), format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("username", r.data)

    def test_register_student_requires_class(self):
        r = APIClient().post(
            "/api/register/", self._payload(role="student", username="yangi_student"), format="json"
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("school_class", r.data)

    def test_non_admin_cannot_list_requests(self):
        c = APIClient()
        c.force_authenticate(self.teacher_user)
        r = c.get("/api/registrations/")
        self.assertEqual(r.status_code, 403)

    def test_admin_approve_creates_profile_and_activates(self):
        APIClient().post("/api/register/", self._payload(), format="json")
        req = RegistrationRequest.objects.get(username="yangi_teacher")
        c = APIClient()
        c.force_authenticate(self.admin)
        r = c.post(f"/api/registrations/{req.id}/approve/")
        self.assertEqual(r.status_code, 200)
        req.refresh_from_db()
        self.assertEqual(req.status, RegistrationRequest.APPROVED)
        self.assertTrue(req.user.is_active)
        self.assertTrue(Teacher.objects.filter(user=req.user).exists())

    def test_admin_reject_deletes_user(self):
        APIClient().post("/api/register/", self._payload(username="rad_etiladi"), format="json")
        req = RegistrationRequest.objects.get(username="rad_etiladi")
        uid = req.user_id
        c = APIClient()
        c.force_authenticate(self.admin)
        r = c.post(f"/api/registrations/{req.id}/reject/")
        self.assertEqual(r.status_code, 200)
        req.refresh_from_db()
        self.assertEqual(req.status, RegistrationRequest.REJECTED)
        self.assertFalse(User.objects.filter(id=uid).exists())

    def test_approved_teacher_can_login(self):
        APIClient().post("/api/register/", self._payload(), format="json")
        req = RegistrationRequest.objects.get(username="yangi_teacher")
        req.approve()
        r = self.client.post("/login/", {
            "username": "yangi_teacher", "password": "parol123", "role": "teacher",
        })
        self.assertEqual(r.status_code, 302)

    def test_pending_user_cannot_login(self):
        APIClient().post("/api/register/", self._payload(username="kutayotgan"), format="json")
        r = self.client.post("/login/", {
            "username": "kutayotgan", "password": "parol123", "role": "teacher",
        })
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)


class AnnouncementTests(BaseSetup):
    def test_student_sees_all_audience(self):
        Announcement.objects.create(title="Umumiy", audience="all", author=self.admin)
        Announcement.objects.create(title="Faqat o'qituvchilar", audience="teachers", author=self.admin)
        c = APIClient()
        c.force_authenticate(self.student_user)
        r = c.get("/api/announcements/")
        titles = [a["title"] for a in r.data]
        self.assertIn("Umumiy", titles)
        self.assertNotIn("Faqat o'qituvchilar", titles)
