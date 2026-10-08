from django.contrib import admin
from django.db.models import Count
from django.utils.safestring import mark_safe

from .models import (
    Subject, Teacher, Parent, SchoolClass, Student,
    Schedule, Grade, Homework, HomeworkSubmission, Attendance, Announcement,
    RegistrationRequest,
)


def badge(text, kind):
    return mark_safe(f'<span class="badge {kind}">{text}</span>')


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "active_badge", "teachers_count"]
    list_filter = ["is_active"]
    search_fields = ["name"]

    @admin.display(description="Holat")
    def active_badge(self, obj):
        return badge("● Faol", "green") if obj.is_active else badge("● Nofaol", "red")

    @admin.display(description="O'qituvchilar")
    def teachers_count(self, obj):
        return obj.teachers.count()


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ["full_name", "phone", "active_badge", "subject_list", "has_login_badge"]
    list_filter = ["is_active"]
    search_fields = ["full_name", "phone"]
    filter_horizontal = ["subjects"]

    @admin.display(description="Holat")
    def active_badge(self, obj):
        return badge("● Faol", "green") if obj.is_active else badge("● Nofaol", "red")

    @admin.display(description="Fanlar")
    def subject_list(self, obj):
        return ", ".join(s.name for s in obj.subjects.all()) or "—"

    @admin.display(description="Login")
    def has_login_badge(self, obj):
        return badge("🔑 Mavjud", "green") if obj.user_id else badge("Yo'q", "red")


@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    list_display = ["full_name", "phone", "active_badge", "children_count", "has_login_badge"]
    list_filter = ["is_active"]
    search_fields = ["full_name", "phone"]

    @admin.display(description="Holat")
    def active_badge(self, obj):
        return badge("● Faol", "green") if obj.is_active else badge("● Nofaol", "red")

    @admin.display(description="Farzandlar")
    def children_count(self, obj):
        return obj.children.count()

    @admin.display(description="Login")
    def has_login_badge(self, obj):
        return badge("🔑 Mavjud", "green") if obj.user_id else badge("Yo'q", "red")


@admin.register(SchoolClass)
class SchoolClassAdmin(admin.ModelAdmin):
    list_display = ["name", "year", "curator", "students_count", "active_badge"]
    list_filter = ["year", "is_active"]
    search_fields = ["name"]

    @admin.display(description="O'quvchilar")
    def students_count(self, obj):
        return obj.students.filter(is_active=True).count()

    @admin.display(description="Holat")
    def active_badge(self, obj):
        return badge("● Faol", "green") if obj.is_active else badge("● Nofaol", "red")


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ["name", "school_class", "phone", "active_badge", "has_login_badge"]
    list_filter = ["is_active", "school_class"]
    search_fields = ["name", "phone"]
    list_select_related = ["school_class"]
    filter_horizontal = ["parents"]
    actions = ["make_active", "make_inactive"]

    @admin.display(description="Holat")
    def active_badge(self, obj):
        return badge("● Faol", "green") if obj.is_active else badge("● Nofaol", "red")

    @admin.display(description="Login")
    def has_login_badge(self, obj):
        return badge("🔑 Mavjud", "green") if obj.user_id else badge("Yo'q", "red")

    @admin.action(description="Faollashtirish")
    def make_active(self, request, queryset):
        n = queryset.update(is_active=True)
        self.message_user(request, f"{n} ta o'quvchi faollashtirildi.")

    @admin.action(description="Faolsizlantirish")
    def make_inactive(self, request, queryset):
        n = queryset.update(is_active=False)
        self.message_user(request, f"{n} ta o'quvchi faolsizlantirildi.")


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ["school_class", "weekday", "period", "subject", "teacher", "room", "is_active"]
    list_filter = ["weekday", "school_class", "teacher", "is_active"]
    search_fields = ["subject__name", "teacher__full_name", "school_class__name"]
    list_select_related = ["school_class", "subject", "teacher"]


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ["date", "student", "subject", "value", "type", "teacher"]
    list_filter = ["type", "subject", "school_class", "date"]
    search_fields = ["student__name"]
    list_select_related = ["student", "subject", "teacher"]
    date_hierarchy = "date"


@admin.register(Homework)
class HomeworkAdmin(admin.ModelAdmin):
    list_display = ["date", "school_class", "subject", "title", "due_date", "teacher"]
    list_filter = ["school_class", "subject", "date"]
    search_fields = ["title", "description"]
    list_select_related = ["school_class", "subject", "teacher"]


@admin.register(HomeworkSubmission)
class HomeworkSubmissionAdmin(admin.ModelAdmin):
    list_display = ["homework", "student", "is_done", "grade", "submitted_at"]
    list_filter = ["is_done", "homework"]
    list_select_related = ["homework", "student"]


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ["date", "student", "school_class_name", "status", "reason", "arrived_at", "left_at"]
    list_filter = ["date", "status", "student__school_class"]
    search_fields = ["student__name", "reason"]
    list_select_related = ["student", "schedule"]
    date_hierarchy = "date"
    list_editable = ["status"]
    actions = ["mark_present", "mark_absent"]

    @admin.display(description="Sinf")
    def school_class_name(self, obj):
        return obj.student.class_name or "—"

    @admin.action(description="Tanlanganlarni 'Keldi' deb belgilash")
    def mark_present(self, request, queryset):
        n = queryset.update(status=Attendance.PRESENT)
        self.message_user(request, f"{n} ta yozuv 'Keldi' deb belgilandi.")

    @admin.action(description="Tanlanganlarni 'Kelmadi' deb belgilash")
    def mark_absent(self, request, queryset):
        n = queryset.update(status=Attendance.ABSENT)
        self.message_user(request, f"{n} ta yozuv 'Kelmadi' deb belgilandi.")


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ["title", "audience", "school_class", "is_pinned", "created_at"]
    list_filter = ["audience", "is_pinned"]
    search_fields = ["title", "body"]


@admin.register(RegistrationRequest)
class RegistrationRequestAdmin(admin.ModelAdmin):
    list_display = ["full_name", "username", "role", "school_class", "status",
                    "phone", "created_at", "reviewed_at"]
    list_filter = ["role", "status"]
    search_fields = ["full_name", "username", "phone"]
    list_editable = ["status"]
    readonly_fields = ["created_at", "reviewed_at", "reviewed_by"]
    actions = ["approve_requests", "reject_requests"]

    @admin.action(description="Tasdiqlash (profil yaratish va faollashtirish)")
    def approve_requests(self, request, queryset):
        n = 0
        for req in queryset.filter(status=RegistrationRequest.PENDING):
            req.approve(reviewer=request.user)
            n += 1
        self.message_user(request, f"{n} ta so'rov tasdiqlandi.")

    @admin.action(description="Rad etish")
    def reject_requests(self, request, queryset):
        n = 0
        for req in queryset.exclude(status=RegistrationRequest.REJECTED):
            req.reject(reviewer=request.user)
            n += 1
        self.message_user(request, f"{n} ta so'rov rad etildi.")


admin.site.site_header = "Maktab CRM — Boshqaruv"
admin.site.site_title = "Maktab CRM"
admin.site.index_title = "Kirish paneli"
