from rest_framework import serializers

from polls.models import AnswerOption, Question, Survey


class AnswerOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnswerOption
        fields = ("id", "text", "order")
        extra_kwargs = {
            "id": {"help_text": "ID варианта ответа."},
            "text": {"help_text": "Текст варианта ответа."},
            "order": {"help_text": "Порядок показа варианта внутри вопроса."},
        }


class QuestionSerializer(serializers.ModelSerializer):
    options = AnswerOptionSerializer(
        many=True,
        read_only=True,
        help_text="Варианты ответа в порядке, заданном автором опроса.",
    )

    class Meta:
        model = Question
        fields = ("id", "text", "order", "options")
        extra_kwargs = {
            "id": {"help_text": "ID вопроса."},
            "text": {"help_text": "Текст вопроса."},
            "order": {"help_text": "Порядок показа вопроса внутри опроса."},
        }


class UserAnswerSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(
        min_value=1,
        help_text="ID пользователя, который проходит опрос.",
    )
    question_id = serializers.IntegerField(
        min_value=1,
        help_text="ID вопроса, на который отвечает пользователь.",
    )
    option_id = serializers.IntegerField(
        min_value=1,
        help_text="ID выбранного варианта ответа.",
    )
    time_spent_ms = serializers.IntegerField(
        min_value=0,
        required=False,
        allow_null=True,
        help_text="Сколько миллисекунд пользователь потратил на вопрос.",
    )


class SurveySerializer(serializers.ModelSerializer):
    class Meta:
        model = Survey
        fields = ("id", "title", "author_id", "status", "created_at")
        extra_kwargs = {
            "id": {"help_text": "ID опроса."},
            "title": {"help_text": "Название опроса."},
            "author_id": {"help_text": "ID автора опроса."},
            "status": {"help_text": "Статус опроса."},
            "created_at": {"help_text": "Дата создания опроса."},
        }


class ProgressSerializer(serializers.Serializer):
    total_questions = serializers.IntegerField(help_text="Всего вопросов в опросе.")
    answered = serializers.IntegerField(help_text="Сколько вопросов пользователь уже прошел.")
    remaining = serializers.IntegerField(help_text="Сколько вопросов осталось пройти.")


class NextQuestionResponseSerializer(serializers.Serializer):
    survey_id = serializers.IntegerField(help_text="ID опроса.")
    attempt_id = serializers.IntegerField(help_text="ID прохождения опроса.")
    status = serializers.CharField(help_text="Статус прохождения: started или completed.")
    progress = ProgressSerializer()
    question = QuestionSerializer(
        allow_null=True,
        help_text="Следующий вопрос. Если опрос завершен, будет null.",
    )


class AnswerResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField(help_text="ID сохраненного ответа.")
    attempt_id = serializers.IntegerField(help_text="ID прохождения опроса.")
    question_id = serializers.IntegerField(help_text="ID вопроса.")
    option_id = serializers.IntegerField(help_text="ID выбранного варианта ответа.")


class PopularAnswerSerializer(serializers.Serializer):
    question_id = serializers.IntegerField(help_text="ID вопроса.")
    question = serializers.CharField(help_text="Текст вопроса.")
    option_id = serializers.IntegerField(help_text="ID варианта ответа.")
    option = serializers.CharField(help_text="Текст варианта ответа.")
    answers_count = serializers.IntegerField(help_text="Сколько раз выбрали этот вариант.")


class SurveyStatsSerializer(serializers.Serializer):
    survey_id = serializers.IntegerField(help_text="ID опроса.")
    title = serializers.CharField(help_text="Название опроса.")
    total_questions = serializers.IntegerField(help_text="Всего вопросов в опросе.")
    total_attempts = serializers.IntegerField(help_text="Всего начатых прохождений опроса.")
    average_completion_time = serializers.CharField(
        help_text="Среднее время прохождения завершенных попыток."
    )
    popular_answers = PopularAnswerSerializer(
        many=True,
        help_text="Популярность вариантов ответа по каждому вопросу.",
    )


class DemoDataRequestSerializer(serializers.Serializer):
    title = serializers.CharField(
        default="Звездные войны",
        required=False,
        help_text="Название демо-опроса.",
    )
    username = serializers.CharField(
        default="respondent",
        required=False,
        help_text="Username демо-пользователя, который будет проходить опрос.",
    )


class DemoDataResponseSerializer(serializers.Serializer):
    survey_id = serializers.IntegerField(help_text="ID созданного демо-опроса.")
    user_id = serializers.IntegerField(help_text="ID демо-пользователя.")
    next_question_url = serializers.CharField(help_text="URL для получения следующего вопроса.")
    answer_url = serializers.CharField(help_text="URL для отправки ответа.")
    stats_url = serializers.CharField(help_text="URL статистики по опросу.")
    questions = QuestionSerializer(many=True, help_text="Созданные вопросы с вариантами.")
