from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from polls.cache import (
    get_next_question_from_cache,
    get_survey_stats,
    get_survey_structure,
    invalidate_survey_stats,
)
from polls.models import AnswerOption, Question, Survey, SurveyAttempt, SurveyStatus, UserAnswer
from polls.serializers import (
    AnswerResponseSerializer,
    DemoDataRequestSerializer,
    DemoDataResponseSerializer,
    NextQuestionResponseSerializer,
    QuestionSerializer,
    SurveyStatsSerializer,
    UserAnswerSerializer,
)


def get_user_or_404(user_id: int):
    user_model = get_user_model()
    return get_object_or_404(user_model, id=user_id)


def build_progress(attempt: SurveyAttempt, total_questions: int) -> dict[str, int]:
    answered = UserAnswer.objects.filter(attempt=attempt).count()
    return {
        "total_questions": total_questions,
        "answered": answered,
        "remaining": max(total_questions - answered, 0),
    }


class NextQuestionView(APIView):
    @extend_schema(
        tags=["Опросы"],
        summary="Получить следующий вопрос",
        description=(
            "Возвращает первый вопрос опроса, на который пользователь еще не ответил. "
            "Если пользователь впервые открывает опрос, прохождение создается автоматически. "
            "Если все вопросы уже пройдены, ручка завершает прохождение "
            "и возвращает question = null."
        ),
        parameters=[
            OpenApiParameter(
                name="user_id",
                type=int,
                location=OpenApiParameter.QUERY,
                required=True,
                description="ID пользователя, который проходит опрос.",
            )
        ],
        responses={200: NextQuestionResponseSerializer},
    )
    def get(self, request, survey_id: int) -> Response:
        user_id = request.query_params.get("user_id")
        if not user_id:
            return Response(
                {"detail": "Передайте user_id в query-параметрах."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = get_user_or_404(user_id=int(user_id))
        except ValueError:
            return Response(
                {"detail": "user_id должен быть целым числом."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        survey = get_object_or_404(Survey, id=survey_id, status=SurveyStatus.PUBLISHED)

        with transaction.atomic():
            attempt, _ = SurveyAttempt.objects.get_or_create(
                survey=survey,
                user=user,
            )

            answered_question_ids = set(
                UserAnswer.objects.filter(attempt=attempt).values_list("question_id", flat=True)
            )
            # Ответов в одном прохождении максимум 15, поэтому такой set маленький и быстрый.
            survey_structure = get_survey_structure(survey.id)
            question = get_next_question_from_cache(survey.id, answered_question_ids)

            total_questions = len(survey_structure)
            progress = build_progress(attempt, total_questions)

            if question is None:
                attempt.complete()
                return Response(
                    {
                        "survey_id": survey.id,
                        "attempt_id": attempt.id,
                        "status": "completed",
                        "progress": progress,
                        "question": None,
                    }
                )

        return Response(
            {
                "survey_id": survey.id,
                "attempt_id": attempt.id,
                "status": attempt.status,
                "progress": progress,
                "question": question,
            }
        )


class AnswerQuestionView(APIView):
    @extend_schema(
        tags=["Опросы"],
        summary="Ответить на вопрос",
        description=(
            "Сохраняет ответ пользователя на конкретный вопрос. "
            "Один пользователь может ответить на каждый вопрос в рамках одного прохождения "
            "только один раз."
        ),
        request=UserAnswerSerializer,
        responses={201: AnswerResponseSerializer},
    )
    def post(self, request, survey_id: int) -> Response:
        serializer = UserAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = get_user_or_404(user_id=data["user_id"])
        survey = get_object_or_404(Survey, id=survey_id, status=SurveyStatus.PUBLISHED)
        question = get_object_or_404(Question, id=data["question_id"], survey=survey)
        option = get_object_or_404(AnswerOption, id=data["option_id"], question=question)

        with transaction.atomic():
            attempt, _ = SurveyAttempt.objects.get_or_create(
                survey=survey,
                user=user,
            )
            try:
                answer = UserAnswer.objects.create(
                    attempt=attempt,
                    question=question,
                    option=option,
                    time_spent_ms=data.get("time_spent_ms"),
                )
                # Новый ответ меняет статистику, но не меняет структуру опубликованного опроса.
                invalidate_survey_stats(survey.id)
            except IntegrityError:
                return Response(
                    {"detail": "Пользователь уже ответил на этот вопрос."},
                    status=status.HTTP_409_CONFLICT,
                )

        return Response(
            {
                "id": answer.id,
                "attempt_id": attempt.id,
                "question_id": question.id,
                "option_id": option.id,
            },
            status=status.HTTP_201_CREATED,
        )


class SurveyStatsView(APIView):
    @extend_schema(
        tags=["Опросы"],
        summary="Получить статистику опроса",
        description=(
            "Возвращает количество прохождений, среднее время прохождения "
            "и популярность вариантов ответа по каждому вопросу."
        ),
        responses={200: SurveyStatsSerializer},
    )
    def get(self, request, survey_id: int) -> Response:
        survey = get_object_or_404(Survey, id=survey_id)
        return Response(get_survey_stats(survey))


class DemoDataView(APIView):
    @extend_schema(
        tags=["Демо-данные"],
        summary="Создать демо-данные",
        description=(
            "Создает опубликованный демо-опрос, пользователя, два вопроса и варианты ответов. "
            "Эта ручка нужна только для быстрой ручной проверки через Swagger или Postman."
        ),
        request=DemoDataRequestSerializer,
        responses={201: DemoDataResponseSerializer},
    )
    def post(self, request) -> Response:
        serializer = DemoDataRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user_model = get_user_model()
        author, _ = user_model.objects.get_or_create(username="demo_author")
        respondent, _ = user_model.objects.get_or_create(
            username=data.get("username", "respondent")
        )

        with transaction.atomic():
            survey = Survey.objects.create(
                title=data.get("title", "Звездные войны"),
                author=author,
                status=SurveyStatus.PUBLISHED,
            )
            question_texts = [
                "Какая трилогия Star Wars тебе нравится больше всего?",
                "Кого ты считаешь самым интересным джедаем?",
                "Кто из ситхов кажется тебе самым сильным?",
                "Какой корабль из Star Wars ты бы выбрал?",
                "На какой планете ты хотел бы побывать?",
                "Какой дроид тебе нравится больше всего?",
                "Какой световой меч ты бы выбрал?",
                "Какая фракция тебе ближе?",
                "Какой фильм ты бы пересмотрел первым?",
                "Какой сериал по Star Wars тебе интереснее?",
                "Какой наставник был бы полезнее для обучения Силе?",
                "Какой персонаж заслуживал больше экранного времени?",
                "Какая сцена дуэли тебе запомнилась сильнее?",
                "Что в Star Wars для тебя важнее всего?",
                "Какой формат истории по Star Wars ты бы выбрал дальше?",
            ]
            question_options = [
                ["Оригинальная", "Приквелы", "Сиквелы", "Все по-своему", "Затрудняюсь ответить"],
                ["Люк Скайуокер", "Оби-Ван Кеноби", "Йода", "Асока Тано", "Квай-Гон Джинн"],
                ["Дарт Вейдер", "Дарт Сидиус", "Дарт Мол", "Граф Дуку", "Кайло Рен"],
                [
                    "Тысячелетний сокол",
                    "X-wing",
                    "TIE-истребитель",
                    "Звездный разрушитель",
                    "Slave I",
                ],
                ["Татуин", "Набу", "Корусант", "Мустафар", "Эндор"],
                ["R2-D2", "C-3PO", "BB-8", "K-2SO", "BD-1"],
                ["Синий", "Зеленый", "Красный", "Фиолетовый", "Двойной"],
                ["Повстанцы", "Республика", "Империя", "Мандалорцы", "Джедаи"],
                [
                    "Новая надежда",
                    "Империя наносит ответный удар",
                    "Месть ситхов",
                    "Изгой-один",
                    "Пробуждение силы",
                ],
                ["Мандалорец", "Андор", "Асока", "Войны клонов", "Оби-Ван Кеноби"],
                ["Йода", "Оби-Ван", "Люк", "Квай-Гон", "Асока"],
                ["Мейс Винду", "Дарт Мол", "Падме Амидала", "Финн", "Капитан Фазма"],
                [
                    "Оби-Ван против Энакина",
                    "Люк против Вейдера",
                    "Квай-Гон и Оби-Ван против Мола",
                    "Рей против Кайло",
                    "Асока против Мола",
                ],
                ["Сила", "Персонажи", "Космические битвы", "Политика галактики", "Приключение"],
                ["Фильм", "Сериал", "Анимация", "Игра", "Книга"],
            ]

            questions = Question.objects.bulk_create(
                [
                    Question(survey=survey, text=text, order=order)
                    for order, text in enumerate(question_texts, start=1)
                ]
            )

            # В демо-опросе фиксируем размер из задания: 15 вопросов и 5 вариантов на вопрос.
            AnswerOption.objects.bulk_create(
                [
                    AnswerOption(question=question, text=option_text, order=order)
                    for question, options in zip(questions, question_options, strict=True)
                    for order, option_text in enumerate(options, start=1)
                ]
            )

        questions = (
            Question.objects.filter(survey=survey)
            .prefetch_related(Prefetch("options", queryset=AnswerOption.objects.order_by("order")))
            .order_by("order")
        )

        return Response(
            {
                "survey_id": survey.id,
                "user_id": respondent.id,
                "next_question_url": (
                    f"/api/surveys/{survey.id}/next-question/?user_id={respondent.id}"
                ),
                "answer_url": f"/api/surveys/{survey.id}/answers/",
                "stats_url": f"/api/surveys/{survey.id}/stats/",
                "questions": QuestionSerializer(questions, many=True).data,
            },
            status=status.HTTP_201_CREATED,
        )
