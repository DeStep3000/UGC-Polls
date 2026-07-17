from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from polls.models import AnswerOption, Question, Survey, SurveyAttempt, SurveyStatus, UserAnswer


class Command(BaseCommand):
    help = "Create configurable poll data for local load checks."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--surveys", type=int, default=100)
        parser.add_argument("--users", type=int, default=100)
        parser.add_argument("--questions-per-survey", type=int, default=15)
        parser.add_argument("--options-per-question", type=int, default=5)
        parser.add_argument("--attempts", type=int, default=0)
        parser.add_argument("--prefix", default="load")
        parser.add_argument("--batch-size", type=int, default=1000)

    def handle(self, *args, **options) -> None:
        prefix = options["prefix"]
        batch_size = options["batch_size"]
        surveys_count = options["surveys"]
        users_count = options["users"]
        questions_per_survey = options["questions_per_survey"]
        options_per_question = options["options_per_question"]
        attempts_count = options["attempts"]

        user_model = get_user_model()

        with transaction.atomic():
            author, _ = user_model.objects.get_or_create(username=f"{prefix}_author")
            # Пользователей создаем пачкой, чтобы не делать тысячи отдельных INSERT.
            users = [
                user_model(username=f"{prefix}_user_{index}") for index in range(1, users_count + 1)
            ]
            user_model.objects.bulk_create(users, batch_size=batch_size, ignore_conflicts=True)
            users = list(user_model.objects.filter(username__startswith=f"{prefix}_user_"))

            surveys = [
                Survey(
                    title=f"{prefix} survey {index}",
                    author=author,
                    status=SurveyStatus.PUBLISHED,
                )
                for index in range(1, surveys_count + 1)
            ]
            Survey.objects.bulk_create(surveys, batch_size=batch_size)
            surveys = list(Survey.objects.filter(title__startswith=f"{prefix} survey "))

            questions = []
            for survey in surveys:
                questions.extend(
                    Question(
                        survey=survey,
                        text=f"Question {number}",
                        order=number,
                    )
                    for number in range(1, questions_per_survey + 1)
                )
            Question.objects.bulk_create(questions, batch_size=batch_size)
            # После bulk_create перечитываем вопросы, чтобы стабильно получить id во всех БД.
            questions = list(
                Question.objects.filter(survey__in=surveys).order_by("survey_id", "order")
            )

            options_to_create = []
            for question in questions:
                options_to_create.extend(
                    AnswerOption(
                        question=question,
                        text=f"Option {number}",
                        order=number,
                    )
                    for number in range(1, options_per_question + 1)
                )
            AnswerOption.objects.bulk_create(options_to_create, batch_size=batch_size)

            if attempts_count:
                self._create_attempts(surveys, users, attempts_count, batch_size)

        self.stdout.write(
            self.style.SUCCESS(
                "Created "
                f"{len(surveys)} surveys, "
                f"{len(questions)} questions, "
                f"{len(options_to_create)} options, "
                f"{len(users)} users."
            )
        )

    def _create_attempts(self, surveys, users, attempts_count: int, batch_size: int) -> None:
        questions = Question.objects.filter(survey__in=surveys, order=1).order_by("survey_id")
        first_question_by_survey = {question.survey_id: question for question in questions}
        first_options = AnswerOption.objects.filter(
            question__in=first_question_by_survey.values(),
            order=1,
        )
        first_option_by_question = {option.question_id: option for option in first_options}

        attempts = []
        for index in range(attempts_count):
            survey = surveys[index % len(surveys)]
            user = users[index % len(users)]
            attempts.append(SurveyAttempt(survey=survey, user=user))

        # ignore_conflicts нужен, если команду запускают повторно с тем же prefix.
        SurveyAttempt.objects.bulk_create(attempts, batch_size=batch_size, ignore_conflicts=True)
        attempts = list(
            SurveyAttempt.objects.filter(survey__in=surveys, user__in=users).order_by("id")[
                :attempts_count
            ]
        )

        answers = []
        for attempt in attempts:
            question = first_question_by_survey[attempt.survey_id]
            answers.append(
                UserAnswer(
                    attempt=attempt,
                    question=question,
                    option=first_option_by_question[question.id],
                    time_spent_ms=1000,
                )
            )
        UserAnswer.objects.bulk_create(answers, batch_size=batch_size, ignore_conflicts=True)
