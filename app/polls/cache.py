from django.conf import settings
from django.core.cache import cache
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Prefetch

from polls.models import AnswerOption, Question, Survey, SurveyAttempt
from polls.serializers import QuestionSerializer


def survey_structure_cache_key(survey_id: int) -> str:
    return f"survey:{survey_id}:structure"


def survey_stats_cache_key(survey_id: int) -> str:
    return f"survey:{survey_id}:stats"


def get_survey_structure(survey_id: int) -> list[dict]:
    cache_key = survey_structure_cache_key(survey_id)
    cached_structure = cache.get(cache_key)
    if cached_structure is not None:
        return cached_structure

    # Структура опроса одинаковая для всех пользователей, поэтому ее выгодно держать в Redis.
    options = AnswerOption.objects.order_by("order", "id")
    questions = (
        Question.objects.filter(survey_id=survey_id)
        .prefetch_related(Prefetch("options", queryset=options))
        .order_by("order", "id")
    )
    structure = list(QuestionSerializer(questions, many=True).data)
    cache.set(cache_key, structure, settings.CACHE_TTL_SECONDS["survey_structure"])
    return structure


def get_next_question_from_cache(survey_id: int, answered_question_ids: set[int]) -> dict | None:
    # Персональное состояние остается в БД, а из кеша берем только общий порядок вопросов.
    for question in get_survey_structure(survey_id):
        if question["id"] not in answered_question_ids:
            return question
    return None


def get_survey_stats(survey: Survey) -> dict:
    cache_key = survey_stats_cache_key(survey.id)
    cached_stats = cache.get(cache_key)
    if cached_stats is not None:
        return cached_stats

    # Статистика может быть тяжелее обычной выдачи вопроса, поэтому кешируем ее коротким TTL.
    completion_time = ExpressionWrapper(
        F("completed_at") - F("started_at"),
        output_field=DurationField(),
    )
    attempts = SurveyAttempt.objects.filter(survey=survey)
    summary = attempts.aggregate(
        total_attempts=Count("id"),
        average_completion_time=Avg(completion_time),
    )

    popular_answers = (
        AnswerOption.objects.filter(question__survey=survey)
        .annotate(answers_count=Count("answers"))
        .select_related("question")
        .order_by("question__order", "-answers_count", "order")
    )

    stats = {
        "survey_id": survey.id,
        "title": survey.title,
        "total_questions": len(get_survey_structure(survey.id)),
        "total_attempts": summary["total_attempts"],
        "average_completion_time": str(summary["average_completion_time"] or ""),
        "popular_answers": [
            {
                "question_id": option.question_id,
                "question": option.question.text,
                "option_id": option.id,
                "option": option.text,
                "answers_count": option.answers_count,
            }
            for option in popular_answers
        ],
    }
    cache.set(cache_key, stats, settings.CACHE_TTL_SECONDS["survey_stats"])
    return stats


def invalidate_survey_stats(survey_id: int) -> None:
    # После нового ответа счетчики вариантов уже неактуальны, сбрасываем только статистику.
    cache.delete(survey_stats_cache_key(survey_id))
