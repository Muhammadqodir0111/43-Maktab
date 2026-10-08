from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Subject(models.Model):
    """Fan (Matematika, Ona tili, Ingliz tili ...)."""

    name = models.CharField("Fan nomi", max_length=80)
    code = models.CharField("Kod", max_length=20, blank=True, default="")
    is_active = models.BooleanField("Faol", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Fan"
        verbose_name_plural = "Fanlar"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Teacher(models.Model):
    """O'qituvchi — tizimga o'z logini bilan kiradi."""

    user = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="teacher_profile", verbose_name="Login",
    )
    full_name = models.CharField("F.I.Sh.", max_length=120)
    phone = models.CharField("Telefon", max_length=30, blank=True, default="")
    subjects = models.ManyToManyField(
        Subject, blank=True, related_name="teachers", verbose_name="Fanlar",
    )
    is_active = models.BooleanField("Faol", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "O'qituvchi"
        verbose_name_plural = "O'qituvchilar"
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class Parent(models.Model):
    """Ota-ona — farzandlarini kuzatadi."""

    user = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="parent_profile", verbose_name="Login",
    )
    full_name = models.CharField("F.I.Sh.", max_length=120)
    phone = models.CharField("Telefon", max_length=30, blank=True, default="")
    is_active = models.BooleanField("Faol", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ota-ona"
        verbose_name_plural = "Ota-onalar"
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class SchoolClass(models.Model):
    """Sinf (5-A, 9-B ...)."""

    name = models.CharField("Sinf", max_length=20)
    year = models.CharField("O'quv yili", max_length=9, default="2025-2026")
    curator = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="curated_classes", verbose_name="Sinf rahbari",
    )
    is_active = models.BooleanField("Faol", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Sinf"
        verbose_name_plural = "Sinflar"
        ordering = ["name"]
        unique_together = [["name", "year"]]

    def __str__(self):
        return f"{self.name} ({self.year})"


class Student(models.Model):
    """O'quvchi."""

    user = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="student_profile", verbose_name="Login",
    )
    name = models.CharField("Ism familiya", max_length=120)
    phone = models.CharField("Telefon raqami", max_length=30, blank=True, default="")
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="students", verbose_name="Sinf",
    )
    parents = models.ManyToManyField(
        Parent, blank=True, related_name="children", verbose_name="Ota-onalar",
    )
    note = models.TextField("Izoh", blank=True, default="")
    is_active = models.BooleanField("Faol", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "O'quvchi"
        verbose_name_plural = "O'quvchilar"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def class_name(self):
        return self.school_class.name if self.school_class else ""


class Schedule(models.Model):
    """Dars jadvali qatori: sinf + kun + para."""

    WEEKDAYS = [
        (1, "Dushanba"),
        (2, "Seshanba"),
        (3, "Chorshanba"),
        (4, "Payshanba"),
        (5, "Juma"),
        (6, "Shanba"),
    ]

    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE,
        related_name="schedules", verbose_name="Sinf",
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.PROTECT,
        related_name="schedules", verbose_name="Fan",
    )
    teacher = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="schedules", verbose_name="O'qituvchi",
    )
    weekday = models.PositiveSmallIntegerField("Kun", choices=WEEKDAYS)
    period = models.PositiveSmallIntegerField("Para")
    start_time = models.TimeField("Boshlanishi", null=True, blank=True)
    end_time = models.TimeField("Tugashi", null=True, blank=True)
    room = models.CharField("Xona", max_length=30, blank=True, default="")
    is_active = models.BooleanField("Faol", default=True)

    class Meta:
        verbose_name = "Dars jadvali"
        verbose_name_plural = "Dars jadvali"
        ordering = ["weekday", "period"]
        unique_together = [["school_class", "weekday", "period"]]

    def __str__(self):
        return f"{self.school_class} · {self.get_weekday_display()} · {self.period}-para"


class Grade(models.Model):
    """Baho (1-5)."""

    JORIY = "joriy"
    ORALIQ = "oraliq"
    CHORAK = "chorak"
    TYPE_CHOICES = [
        (JORIY, "Joriy"),
        (ORALIQ, "Oraliq"),
        (CHORAK, "Chorak"),
    ]

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE,
        related_name="grades", verbose_name="O'quvchi",
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE,
        related_name="grades", verbose_name="Fan",
    )
    teacher = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="grades", verbose_name="O'qituvchi",
    )
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="grades", verbose_name="Sinf",
    )
    date = models.DateField("Sana")
    value = models.PositiveSmallIntegerField("Baho")
    type = models.CharField(
        "Turi", max_length=10, choices=TYPE_CHOICES, default=JORIY,
    )
    comment = models.CharField("Izoh", max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Baho"
        verbose_name_plural = "Baholar"
        ordering = ["-date", "student__name"]

    def __str__(self):
        return f"{self.student} — {self.subject}: {self.value}"


class Homework(models.Model):
    """Uyga vazifa."""

    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE,
        related_name="homeworks", verbose_name="Sinf",
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE,
        related_name="homeworks", verbose_name="Fan",
    )
    teacher = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="homeworks", verbose_name="O'qituvchi",
    )
    date = models.DateField("Berilgan sana")
    due_date = models.DateField("Topshirish muddati", null=True, blank=True)
    title = models.CharField("Sarlavha", max_length=160)
    description = models.TextField("Mazmuni", blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Uyga vazifa"
        verbose_name_plural = "Uyga vazifalar"
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.school_class} · {self.subject}: {self.title}"


class HomeworkSubmission(models.Model):
    """O'quvchining uyga vazifa holati."""

    homework = models.ForeignKey(
        Homework, on_delete=models.CASCADE,
        related_name="submissions", verbose_name="Vazifa",
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE,
        related_name="submissions", verbose_name="O'quvchi",
    )
    is_done = models.BooleanField("Bajarildi", default=False)
    grade = models.PositiveSmallIntegerField("Baho", null=True, blank=True)
    comment = models.CharField("Izoh", max_length=255, blank=True, default="")
    submitted_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Vazifa topshirig'i"
        verbose_name_plural = "Vazifa topshiriqlari"
        unique_together = [["homework", "student"]]

    def __str__(self):
        return f"{self.student} — {self.homework}"


class Attendance(models.Model):
    """Davomat."""

    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    SICK = "sick"
    STATUS_CHOICES = [
        (PRESENT, "Keldi"),
        (ABSENT, "Kelmadi"),
        (LATE, "Kechikdi"),
        (SICK, "Kasal"),
    ]

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE,
        related_name="attendances", verbose_name="O'quvchi",
    )
    schedule = models.ForeignKey(
        Schedule, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="attendances", verbose_name="Dars",
    )
    date = models.DateField("Sana")
    status = models.CharField(
        "Holat", max_length=10, choices=STATUS_CHOICES, default=PRESENT,
    )
    reason = models.CharField("Sabab", max_length=160, blank=True, default="")
    arrived_at = models.TimeField("Kelgan vaqti", null=True, blank=True)
    left_at = models.TimeField("Ketgan vaqti", null=True, blank=True)
    note = models.CharField("Izoh", max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Davomat"
        verbose_name_plural = "Davomat"
        ordering = ["-date", "student__name"]
        unique_together = [["student", "schedule", "date"]]

    def __str__(self):
        return f"{self.student} - {self.date} ({self.get_status_display()})"


class RegistrationRequest(models.Model):
    """O'zini ro'yxatdan o'tkazish so'rovi — admin tasdiqlagach hisob faollashadi."""

    TEACHER = "teacher"
    STUDENT = "student"
    PARENT = "parent"
    ROLE_CHOICES = [
        (TEACHER, "O'qituvchi"),
        (STUDENT, "O'quvchi"),
        (PARENT, "Ota-ona"),
    ]

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    STATUS_CHOICES = [
        (PENDING, "Kutilmoqda"),
        (APPROVED, "Tasdiqlangan"),
        (REJECTED, "Rad etilgan"),
    ]

    user = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="registration_request", verbose_name="Login",
    )
    full_name = models.CharField("F.I.Sh.", max_length=150)
    username = models.CharField("Login", max_length=150)
    role = models.CharField("Rol", max_length=20, choices=ROLE_CHOICES)
    phone = models.CharField("Telefon", max_length=30, blank=True, default="")
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="registration_requests", verbose_name="Sinf (o'quvchi uchun)",
    )
    message = models.TextField("Izoh", blank=True, default="")
    status = models.CharField(
        "Holat", max_length=10, choices=STATUS_CHOICES, default=PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reviewed_registrations", verbose_name="Ko'rib chiqqan",
    )

    class Meta:
        verbose_name = "Ro'yxatdan o'tish so'rovi"
        verbose_name_plural = "Ro'yxatdan o'tish so'rovlari"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.get_role_display()}) — {self.get_status_display()}"

    def approve(self, reviewer=None):
        """Hisobni faollashtiradi va rolga mos profil yaratadi."""
        user = self.user
        if user:
            user.is_active = True
            parts = (self.full_name or "").split()
            if parts:
                user.first_name = parts[0][:150]
                user.last_name = " ".join(parts[1:])[:150]
            user.save()

            if self.role == self.TEACHER:
                Teacher.objects.get_or_create(
                    user=user,
                    defaults={"full_name": self.full_name, "phone": self.phone},
                )
            elif self.role == self.STUDENT:
                Student.objects.get_or_create(
                    user=user,
                    defaults={"name": self.full_name, "school_class": self.school_class,
                              "phone": self.phone},
                )
            elif self.role == self.PARENT:
                Parent.objects.get_or_create(
                    user=user,
                    defaults={"full_name": self.full_name, "phone": self.phone},
                )

        self.status = self.APPROVED
        self.reviewed_at = timezone.now()
        if reviewer is not None:
            self.reviewed_by = reviewer
        self.save()
        return self

    def reject(self, reviewer=None):
        """So'rovni rad etadi va vaqtinchalik loginni o'chiradi."""
        user = self.user
        self.user = None
        self.status = self.REJECTED
        self.reviewed_at = timezone.now()
        if reviewer is not None:
            self.reviewed_by = reviewer
        self.save()
        if user and not user.is_staff and not user.is_superuser:
            user.delete()
        return self


class Announcement(models.Model):
    """E'lon."""

    AUDIENCE_CHOICES = [
        ("all", "Hamma"),
        ("teachers", "O'qituvchilar"),
        ("students", "O'quvchilar"),
        ("parents", "Ota-onalar"),
        ("class", "Bitta sinf"),
    ]

    title = models.CharField("Sarlavha", max_length=160)
    body = models.TextField("Matn", blank=True, default="")
    audience = models.CharField(
        "Kimga", max_length=10, choices=AUDIENCE_CHOICES, default="all",
    )
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="announcements", verbose_name="Sinf",
    )
    author = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="announcements", verbose_name="Muallif",
    )
    is_pinned = models.BooleanField("Qadab qo'yilgan", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "E'lon"
        verbose_name_plural = "E'lonlar"
        ordering = ["-is_pinned", "-created_at"]

    def __str__(self):
        return self.title
