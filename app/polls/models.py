from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class SurveyStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    ARCHIVED = "archived", "Archived"


class AttemptStatus(models.TextChoices):
    STARTED = "started", "Started"
    COMPLETED = "completed", "Completed"


class Survey(models.Model):
    title = models.CharField("title", max_length=255)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="author",
        on_delete=models.PROTECT,
        related_name="created_surveys",
    )
    status = models.CharField(
        "status",
        max_length=20,
        choices=SurveyStatus.choices,
        default=SurveyStatus.DRAFT,
    )
    created_at = models.DateTimeField("created at", auto_now_add=True)
    updated_at = models.DateTimeField("updated at", auto_now=True)

    class Meta:
        verbose_name = "survey"
        verbose_name_plural = "surveys"
        indexes = [
            models.Index(fields=["status", "created_at"], name="survey_status_created_idx"),
            models.Index(fields=["author", "created_at"], name="survey_author_created_idx"),
        ]

    def __str__(self) -> str:
        return self.title


class Question(models.Model):
    survey = models.ForeignKey(
        Survey,
        verbose_name="survey",
        on_delete=models.CASCADE,
        related_name="questions",
    )
    text = models.TextField("question text")
    order = models.PositiveSmallIntegerField("order")
    created_at = models.DateTimeField("created at", auto_now_add=True)

    class Meta:
        verbose_name = "question"
        verbose_name_plural = "questions"
        ordering = ["order", "id"]
        # Один и тот же порядковый номер вопроса внутри опроса запрещен на уровне БД.
        constraints = [
            models.UniqueConstraint(fields=["survey", "order"], name="uniq_question_order")
        ]
        indexes = [
            models.Index(fields=["survey", "order"], name="question_survey_order_idx"),
        ]

    def __str__(self) -> str:
        return self.text


class AnswerOption(models.Model):
    question = models.ForeignKey(
        Question,
        verbose_name="question",
        on_delete=models.CASCADE,
        related_name="options",
    )
    text = models.CharField("option text", max_length=500)
    order = models.PositiveSmallIntegerField("order")

    class Meta:
        verbose_name = "answer option"
        verbose_name_plural = "answer options"
        ordering = ["order", "id"]
        # Автор может менять порядок вариантов, но внутри вопроса он должен быть уникальным.
        constraints = [
            models.UniqueConstraint(fields=["question", "order"], name="uniq_option_order")
        ]
        indexes = [
            models.Index(fields=["question", "order"], name="option_question_order_idx"),
        ]

    def __str__(self) -> str:
        return self.text


class SurveyAttempt(models.Model):
    survey = models.ForeignKey(
        Survey,
        verbose_name="survey",
        on_delete=models.PROTECT,
        related_name="attempts",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="user",
        on_delete=models.PROTECT,
        related_name="survey_attempts",
    )
    status = models.CharField(
        "status",
        max_length=20,
        choices=AttemptStatus.choices,
        default=AttemptStatus.STARTED,
    )
    started_at = models.DateTimeField("started at", auto_now_add=True)
    completed_at = models.DateTimeField("completed at", null=True, blank=True)

    class Meta:
        verbose_name = "survey attempt"
        verbose_name_plural = "survey attempts"
        # В этой реализации пользователь проходит конкретный опрос только один раз.
        constraints = [
            models.UniqueConstraint(
                fields=["survey", "user"],
                name="uniq_survey_attempt_user",
            )
        ]
        indexes = [
            models.Index(fields=["user", "status"], name="attempt_user_status_idx"),
            models.Index(fields=["survey", "status"], name="attempt_survey_status_idx"),
            models.Index(fields=["survey", "completed_at"], name="attempt_survey_done_idx"),
        ]

    def complete(self) -> None:
        # Keep completion logic in one place for API and background jobs.
        if self.status == AttemptStatus.COMPLETED:
            return
        self.status = AttemptStatus.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at"])


class UserAnswer(models.Model):
    attempt = models.ForeignKey(
        SurveyAttempt,
        verbose_name="attempt",
        on_delete=models.CASCADE,
        related_name="answers",
    )
    question = models.ForeignKey(
        Question,
        verbose_name="question",
        on_delete=models.PROTECT,
        related_name="answers",
    )
    option = models.ForeignKey(
        AnswerOption,
        verbose_name="answer option",
        on_delete=models.PROTECT,
        related_name="answers",
    )
    time_spent_ms = models.PositiveIntegerField("time spent, ms", null=True, blank=True)
    created_at = models.DateTimeField("created at", auto_now_add=True)

    class Meta:
        verbose_name = "user answer"
        verbose_name_plural = "user answers"
        # Один вопрос в одном прохождении нельзя закрыть двумя разными ответами.
        constraints = [
            models.UniqueConstraint(fields=["attempt", "question"], name="uniq_answer_question")
        ]
        indexes = [
            models.Index(fields=["question", "option"], name="answer_question_option_idx"),
            models.Index(fields=["attempt", "created_at"], name="answer_attempt_created_idx"),
        ]

    def clean(self) -> None:
        if self.option_id and self.question_id and self.option.question_id != self.question_id:
            msg = "Вариант ответа должен принадлежать выбранному вопросу."
            raise ValidationError(msg)
