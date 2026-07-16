from django.contrib import admin

from polls.models import AnswerOption, Question, Survey, SurveyAttempt, UserAnswer


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0


class AnswerOptionInline(admin.TabularInline):
    model = AnswerOption
    extra = 0


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "author", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("title", "author__username")
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "survey", "order", "text")
    list_filter = ("survey",)
    search_fields = ("text",)
    inlines = [AnswerOptionInline]


@admin.register(AnswerOption)
class AnswerOptionAdmin(admin.ModelAdmin):
    list_display = ("id", "question", "order", "text")
    list_filter = ("question__survey",)
    search_fields = ("text",)


@admin.register(SurveyAttempt)
class SurveyAttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "survey", "user", "status", "started_at", "completed_at")
    list_filter = ("status", "survey")
    search_fields = ("survey__title", "user__username")


@admin.register(UserAnswer)
class UserAnswerAdmin(admin.ModelAdmin):
    list_display = ("id", "attempt", "question", "option", "created_at")
    list_filter = ("question__survey",)
