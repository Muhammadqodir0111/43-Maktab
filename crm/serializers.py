from django.contrib.auth.models import User
from rest_framework import serializers

from .models import (
    Subject, Teacher, Parent, SchoolClass, Student,
    Schedule, Grade, Homework, HomeworkSubmission, Attendance, Announcement,
    RegistrationRequest,
)


class LoginMixin:
    """Telefon/o'quvchi/o'qituvchi uchun login (User) yaratish va yangilash."""

    login_related_name = None

    def _save_login(self, instance, username, password):
        username = (username or "").strip()
        if not username:
            return
        if instance.user_id:
            user = instance.user
            user.username = username
            if password:
                user.set_password(password)
                user.save()
            else:
                user.save(update_fields=["username"])
        else:
            instance.user = User.objects.create_user(
                username=username, password=password or username,
            )
            instance.save(update_fields=["user"])

    def _check_login(self, attrs):
        username = (attrs.get("username") or "").strip()
        password = attrs.get("password") or ""
        if username and not self.instance and not password:
            raise serializers.ValidationError(
                {"password": "Yangi login uchun parol talab qilinadi."}
            )
        if username:
            qs = User.objects.filter(username=username)
            if self.instance and self.instance.user_id:
                qs = qs.exclude(pk=self.instance.user_id)
            if qs.exists():
                raise serializers.ValidationError({"username": "Bu login band."})
        return attrs


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ["id", "name", "code", "is_active", "created_at"]


class TeacherSerializer(LoginMixin, serializers.ModelSerializer):
    subjects = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Subject.objects.all(), required=False,
    )
    subject_names = serializers.SerializerMethodField()
    username = serializers.CharField(write_only=True, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    has_login = serializers.SerializerMethodField()

    class Meta:
        model = Teacher
        fields = ["id", "full_name", "phone", "is_active", "created_at",
                  "subjects", "subject_names", "username", "password", "has_login"]

    def get_subject_names(self, obj):
        return [s.name for s in obj.subjects.all()]

    def get_has_login(self, obj):
        return obj.user_id is not None

    def validate(self, attrs):
        return self._check_login(attrs)

    def create(self, validated_data):
        username = validated_data.pop("username", "")
        password = validated_data.pop("password", "")
        obj = super().create(validated_data)
        self._save_login(obj, username, password)
        return obj

    def update(self, instance, validated_data):
        username = validated_data.pop("username", "")
        password = validated_data.pop("password", "")
        obj = super().update(instance, validated_data)
        self._save_login(obj, username, password)
        return obj


class ParentSerializer(LoginMixin, serializers.ModelSerializer):
    username = serializers.CharField(write_only=True, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    has_login = serializers.SerializerMethodField()
    children_names = serializers.SerializerMethodField()

    class Meta:
        model = Parent
        fields = ["id", "full_name", "phone", "is_active", "created_at",
                  "username", "password", "has_login", "children_names"]

    def get_has_login(self, obj):
        return obj.user_id is not None

    def get_children_names(self, obj):
        return [c.name for c in obj.children.all()]

    def validate(self, attrs):
        return self._check_login(attrs)

    def create(self, validated_data):
        username = validated_data.pop("username", "")
        password = validated_data.pop("password", "")
        obj = super().create(validated_data)
        self._save_login(obj, username, password)
        return obj

    def update(self, instance, validated_data):
        username = validated_data.pop("username", "")
        password = validated_data.pop("password", "")
        obj = super().update(instance, validated_data)
        self._save_login(obj, username, password)
        return obj


class SchoolClassSerializer(serializers.ModelSerializer):
    curator_name = serializers.CharField(source="curator.full_name", read_only=True)
    students_count = serializers.SerializerMethodField()

    class Meta:
        model = SchoolClass
        fields = ["id", "name", "year", "curator", "curator_name", "is_active",
                  "created_at", "students_count"]

    def get_students_count(self, obj):
        return obj.students.filter(is_active=True).count()


class StudentSerializer(LoginMixin, serializers.ModelSerializer):
    username = serializers.CharField(write_only=True, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    has_login = serializers.SerializerMethodField()
    school_class = serializers.PrimaryKeyRelatedField(
        queryset=SchoolClass.objects.all(), required=False, allow_null=True,
    )
    class_name = serializers.CharField(source="school_class.name", read_only=True)
    parents = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Parent.objects.all(), required=False,
    )
    parent_names = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = ["id", "name", "phone", "note", "is_active", "created_at",
                  "school_class", "class_name", "parents", "parent_names",
                  "username", "password", "has_login"]

    def get_has_login(self, obj):
        return obj.user_id is not None

    def get_parent_names(self, obj):
        return [p.full_name for p in obj.parents.all()]

    def validate(self, attrs):
        return self._check_login(attrs)

    def create(self, validated_data):
        username = validated_data.pop("username", "")
        password = validated_data.pop("password", "")
        parents = validated_data.pop("parents", None)
        obj = super().create(validated_data)
        if parents is not None:
            obj.parents.set(parents)
        self._save_login(obj, username, password)
        return obj

    def update(self, instance, validated_data):
        username = validated_data.pop("username", "")
        password = validated_data.pop("password", "")
        obj = super().update(instance, validated_data)
        self._save_login(obj, username, password)
        return obj


class ScheduleSerializer(serializers.ModelSerializer):
    school_class_name = serializers.CharField(source="school_class.name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    teacher_name = serializers.CharField(source="teacher.full_name", read_only=True)
    weekday_display = serializers.CharField(source="get_weekday_display", read_only=True)

    class Meta:
        model = Schedule
        fields = ["id", "school_class", "school_class_name", "subject", "subject_name",
                  "teacher", "teacher_name", "weekday", "weekday_display", "period",
                  "start_time", "end_time", "room", "is_active"]


class GradeSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    teacher_name = serializers.CharField(source="teacher.full_name", read_only=True)
    class_name = serializers.CharField(source="student.class_name", read_only=True)

    class Meta:
        model = Grade
        fields = ["id", "student", "student_name", "subject", "subject_name",
                  "teacher", "teacher_name", "school_class", "class_name",
                  "date", "value", "type", "comment", "created_at"]

    def create(self, validated_data):
        student = validated_data.get("student")
        if not validated_data.get("school_class") and student:
            validated_data["school_class"] = student.school_class
        return super().create(validated_data)


class HomeworkSubmissionSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.name", read_only=True)

    class Meta:
        model = HomeworkSubmission
        fields = ["id", "homework", "student", "student_name", "is_done",
                  "grade", "comment", "submitted_at"]


class HomeworkSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    class_name = serializers.CharField(source="school_class.name", read_only=True)
    teacher_name = serializers.CharField(source="teacher.full_name", read_only=True)
    submissions_count = serializers.SerializerMethodField()
    done_count = serializers.SerializerMethodField()

    class Meta:
        model = Homework
        fields = ["id", "school_class", "class_name", "subject", "subject_name",
                  "teacher", "teacher_name", "date", "due_date", "title",
                  "description", "created_at", "submissions_count", "done_count"]

    def get_submissions_count(self, obj):
        return obj.submissions.count()

    def get_done_count(self, obj):
        return obj.submissions.filter(is_done=True).count()


class AttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.name", read_only=True)
    class_name = serializers.CharField(source="student.class_name", read_only=True)
    subject_name = serializers.CharField(source="schedule.subject.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Attendance
        fields = ["id", "student", "student_name", "class_name", "schedule",
                  "subject_name", "date", "status", "status_display", "reason",
                  "arrived_at", "left_at", "note", "created_at"]


class AnnouncementSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.get_full_name", read_only=True)
    class_name = serializers.CharField(source="school_class.name", read_only=True)

    class Meta:
        model = Announcement
        fields = ["id", "title", "body", "audience", "school_class", "class_name",
                  "author", "author_name", "is_pinned", "created_at"]


class RegisterSerializer(serializers.Serializer):
    """Ommaviy ro'yxatdan o'tish so'rovi (tasdiqlanmaguncha hisob nofaol bo'ladi)."""

    role = serializers.ChoiceField(choices=RegistrationRequest.ROLE_CHOICES)
    full_name = serializers.CharField(max_length=150)
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=4)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    school_class = serializers.PrimaryKeyRelatedField(
        queryset=SchoolClass.objects.all(), required=False, allow_null=True,
    )
    message = serializers.CharField(required=False, allow_blank=True)

    def validate_full_name(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError("F.I.Sh. juda qisqa.")
        return value.strip()

    def validate_username(self, value):
        value = value.strip()
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Bu login allaqachon band.")
        return value

    def validate(self, attrs):
        if attrs.get("role") == RegistrationRequest.STUDENT and not attrs.get("school_class"):
            raise serializers.ValidationError({"school_class": "O'quvchi uchun sinf tanlanishi shart."})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User.objects.create(username=validated_data["username"], is_active=False)
        user.set_password(password)
        user.save(update_fields=["password"])
        return RegistrationRequest.objects.create(user=user, **validated_data)


class RegistrationRequestSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    class_name = serializers.CharField(source="school_class.name", read_only=True)

    class Meta:
        model = RegistrationRequest
        fields = ["id", "full_name", "username", "role", "role_display",
                  "phone", "school_class", "class_name", "message",
                  "status", "status_display", "created_at", "reviewed_at"]
