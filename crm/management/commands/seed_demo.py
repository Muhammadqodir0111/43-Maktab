from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from crm.models import (
    Subject, Teacher, Parent, SchoolClass, Student,
    Schedule, Grade, Homework, HomeworkSubmission, Attendance, Announcement,
)

SUBJECTS = [
    ("Matematika", "MAT"),
    ("Ona tili", "ONA"),
    ("Ingliz tili", "ING"),
    ("Fizika", "FIZ"),
    ("Informatika", "INF"),
    ("Tarix", "TAR"),
]

TEACHERS = [
    ("Karimov Ali Valiyevich", "+998 90 111 22 33", ["Matematika", "Fizika"]),
    ("Rahimova Malika Sobirovna", "+998 90 222 33 44", ["Ona tili", "Tarix"]),
    ("Toshmatov Bekzod Erkinovich", "+998 90 333 44 55", ["Ingliz tili"]),
    ("Yusupova Nilufar Qodirovna", "+998 90 444 55 66", ["Informatika", "Matematika"]),
]

STUDENTS = [
    ("Abdullayev Jasur", "5-A", "parent1"),
    ("Mirzayeva Dilnoza", "5-A", "parent2"),
    ("Saidov Sanjar", "5-A", "parent1"),
    ("Xolmatova Madina", "5-A", "parent3"),
    ("Qodirov Umid", "5-A", "parent2"),
    ("Nazarova Zilola", "9-B", "parent3"),
    ("Xasanov Doniyor", "9-B", "parent1"),
    ("Sattorova Kamola", "9-B", "parent2"),
]

PARENTS = [
    ("parent1", "Abdullayev Baxtiyor", "+998 91 100 10 10"),
    ("parent2", "Mirzayev Anvar", "+998 91 200 20 20"),
    ("parent3", "Xolmatov Rustam", "+998 91 300 30 30"),
]


def ensure_user(username, password):
    user, _ = User.objects.get_or_create(username=username)
    user.set_password(password)
    user.save()
    return user


class Command(BaseCommand):
    help = "Maktab CRM uchun demo ma'lumotlarni yaratadi"

    def handle(self, *args, **options):
        with transaction.atomic():
            self._run(*args, **options)

    def _run(self, *args, **options):
        admin, created = User.objects.get_or_create(
            username="admin", defaults={"is_staff": True, "is_superuser": True}
        )
        admin.is_staff = True
        admin.is_superuser = True
        admin.set_password("admin123")
        admin.save()
        if created:
            self.stdout.write("Admin yaratildi: admin / admin123")

        subjects = {}
        for name, code in SUBJECTS:
            subjects[name], _ = Subject.objects.get_or_create(
                name=name, defaults={"code": code}
            )

        teachers = {}
        for i, (name, phone, subs) in enumerate(TEACHERS, 1):
            t, _ = Teacher.objects.get_or_create(
                full_name=name, defaults={"phone": phone}
            )
            t.phone = phone
            t.is_active = True
            t.user = ensure_user(f"teacher{i}", "teacher123")
            t.save()
            t.subjects.set([subjects[s] for s in subs])
            teachers[name] = t

        parents = {}
        for username, name, phone in PARENTS:
            p, _ = Parent.objects.get_or_create(
                full_name=name, defaults={"phone": phone}
            )
            p.phone = phone
            p.user = ensure_user(username, "parent123")
            p.save()
            parents[username] = p

        classes = {}
        for cname, curator in [("5-A", "Rahimova Malika Sobirovna"),
                               ("9-B", "Karimov Ali Valiyevich")]:
            c, _ = SchoolClass.objects.get_or_create(
                name=cname, year="2025-2026", defaults={"curator": teachers[curator]}
            )
            classes[cname] = c

        students = []
        for idx, (name, cname, parent_key) in enumerate(STUDENTS, 1):
            s, _ = Student.objects.get_or_create(
                name=name, defaults={"school_class": classes[cname]}
            )
            s.school_class = classes[cname]
            s.is_active = True
            s.user = ensure_user(f"student{idx}", "student123")
            s.save()
            s.parents.set([parents[parent_key]])
            students.append(s)

        # Dars jadvali
        base_times = {1: ("08:30", "09:15"), 2: ("09:25", "10:10"),
                      3: ("10:25", "11:10"), 4: ("11:20", "12:05"),
                      5: ("12:35", "13:20")}
        plan = {
            "5-A": {1: ["Matematika", "Ona tili", "Ingliz tili"],
                    2: ["Fizika", "Matematika", "Informatika"],
                    3: ["Ona tili", "Tarix", "Matematika"],
                    4: ["Ingliz tili", "Fizika", "Informatika"],
                    5: ["Matematika", "Ona tili", "Tarix"]},
            "9-B": {1: ["Fizika", "Matematika", "Ingliz tili"],
                    2: ["Informatika", "Ona tili", "Matematika"],
                    3: ["Tarix", "Fizika", "Informatika"],
                    4: ["Matematika", "Ingliz tili", "Ona tili"],
                    5: ["Informatika", "Tarix", "Fizika"]},
        }
        teacher_by_subject = {}
        for name, phone, subs in TEACHERS:
            for s in subs:
                teacher_by_subject.setdefault(s, teachers[name])

        for cname, days in plan.items():
            for weekday, sub_list in days.items():
                for period, sub_name in enumerate(sub_list, start=1):
                    st, et = base_times[period]
                    Schedule.objects.update_or_create(
                        school_class=classes[cname], weekday=weekday, period=period,
                        defaults={
                            "subject": subjects[sub_name],
                            "teacher": teacher_by_subject.get(sub_name),
                            "start_time": st, "end_time": et,
                            "room": f"{100 + period}",
                        },
                    )

        # Baholar (oxirgi 20 kun)
        import random
        random.seed(42)
        today = date.today()
        for s in students:
            for offset in range(0, 20, 3):
                day = today - timedelta(days=offset)
                if day.weekday() >= 6:
                    continue
                subj = subjects[random.choice(list(subjects.keys()))]
                Grade.objects.get_or_create(
                    student=s, subject=subj, date=day,
                    defaults={"value": random.choice([3, 4, 4, 5, 5]),
                              "type": "joriy",
                              "school_class": s.school_class,
                              "teacher": teacher_by_subject.get(subj.name)},
                )

        # Uyga vazifalar
        for cname, cls in classes.items():
            sub = subjects["Matematika"]
            hw, _ = Homework.objects.get_or_create(
                school_class=cls, subject=sub, date=today - timedelta(days=1),
                defaults={"title": "3-masalalar to'plami",
                          "description": "Darslikdagi 45-50-masalalarni bajaring.",
                          "due_date": today + timedelta(days=2),
                          "teacher": teacher_by_subject["Matematika"]},
            )
            for s in cls.students.all():
                HomeworkSubmission.objects.get_or_create(
                    homework=hw, student=s,
                    defaults={"is_done": random.choice([True, False]),
                              "grade": random.choice([4, 5, None])},
                )

        # Davomat (oxirgi 10 kun)
        for s in students:
            for offset in range(10):
                day = today - timedelta(days=offset)
                if day.weekday() >= 6:
                    continue
                Attendance.objects.get_or_create(
                    student=s, schedule=None, date=day,
                    defaults={"status": random.choices(
                        ["present", "absent", "late", "sick"],
                        weights=[75, 10, 10, 5])[0]},
                )

        Announcement.objects.get_or_create(
            title="Ota-onalar yig'ilishi",
            defaults={
                "body": "Shanba kuni soat 10:00 da umumiy ota-onalar yig'ilishi bo'lib o'tadi.",
                "audience": "parents", "author": admin, "is_pinned": True,
            },
        )
        Announcement.objects.get_or_create(
            title="Haftalik test",
            defaults={
                "body": "Juma kuni barcha sinflarda matematikadan nazorat ishi o'tkaziladi.",
                "audience": "all", "author": admin,
            },
        )

        self.stdout.write(self.style.SUCCESS(
            "Demo ma'lumot tayyor!\n"
            "  Admin:       admin / admin123\n"
            "  O'qituvchi:  teacher1 / teacher123\n"
            "  O'quvchi:    student1 / student123\n"
            "  Ota-ona:     parent1 / parent123"
        ))
