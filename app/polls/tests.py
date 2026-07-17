import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from polls.models import AnswerOption, Question, Survey, SurveyStatus, UserAnswer


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def vegetable_survey(db):
    user_model = get_user_model()
    author = user_model.objects.create_user(username="author")
    respondent = user_model.objects.create_user(username="respondent")
    survey = Survey.objects.create(
        title="Vegetables",
        author=author,
        status=SurveyStatus.PUBLISHED,
    )

    first_question = Question.objects.create(
        survey=survey,
        text="Do you like burrata with tomatoes?",
        order=1,
    )
    second_question = Question.objects.create(
        survey=survey,
        text="Do you like cucumbers?",
        order=2,
    )

    AnswerOption.objects.create(question=first_question, text="Yes", order=1)
    AnswerOption.objects.create(question=first_question, text="No", order=2)
    AnswerOption.objects.create(question=second_question, text="Yes", order=1)
    AnswerOption.objects.create(question=second_question, text="Only in cocktails", order=2)

    return {
        "survey": survey,
        "respondent": respondent,
        "first_question": first_question,
        "second_question": second_question,
    }


@pytest.mark.django_db
def test_next_question_returns_first_unanswered_question(api_client, vegetable_survey):
    survey = vegetable_survey["survey"]
    respondent = vegetable_survey["respondent"]

    response = api_client.get(f"/api/surveys/{survey.id}/next-question/?user_id={respondent.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "started"
    assert body["progress"] == {"total_questions": 2, "answered": 0, "remaining": 2}
    assert body["question"]["text"] == "Do you like burrata with tomatoes?"
    assert [option["text"] for option in body["question"]["options"]] == ["Yes", "No"]


@pytest.mark.django_db
def test_next_question_skips_answered_question(api_client, vegetable_survey):
    survey = vegetable_survey["survey"]
    respondent = vegetable_survey["respondent"]
    first_question = vegetable_survey["first_question"]
    option = first_question.options.first()

    response = api_client.post(
        f"/api/surveys/{survey.id}/answers/",
        {
            "user_id": respondent.id,
            "question_id": first_question.id,
            "option_id": option.id,
            "time_spent_ms": 1200,
        },
        format="json",
    )
    assert response.status_code == 201

    next_response = api_client.get(
        f"/api/surveys/{survey.id}/next-question/?user_id={respondent.id}"
    )

    assert next_response.status_code == 200
    body = next_response.json()
    assert body["progress"]["answered"] == 1
    assert body["question"]["text"] == "Do you like cucumbers?"


@pytest.mark.django_db
def test_attempt_is_completed_when_all_questions_are_answered(api_client, vegetable_survey):
    survey = vegetable_survey["survey"]
    respondent = vegetable_survey["respondent"]
    attempt_response = api_client.get(
        f"/api/surveys/{survey.id}/next-question/?user_id={respondent.id}"
    )
    attempt_id = attempt_response.json()["attempt_id"]

    for question in Question.objects.filter(survey=survey):
        UserAnswer.objects.create(
            attempt_id=attempt_id,
            question=question,
            option=question.options.first(),
        )

    response = api_client.get(f"/api/surveys/{survey.id}/next-question/?user_id={respondent.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["question"] is None


@pytest.mark.django_db
def test_stats_counts_answers_by_option(api_client, vegetable_survey):
    survey = vegetable_survey["survey"]
    respondent = vegetable_survey["respondent"]
    first_question = vegetable_survey["first_question"]
    option = first_question.options.first()

    api_client.post(
        f"/api/surveys/{survey.id}/answers/",
        {
            "user_id": respondent.id,
            "question_id": first_question.id,
            "option_id": option.id,
        },
        format="json",
    )

    response = api_client.get(f"/api/surveys/{survey.id}/stats/")

    assert response.status_code == 200
    body = response.json()
    assert body["total_questions"] == 2
    assert body["total_attempts"] == 1
    options = {row["option_id"]: row["answers_count"] for row in body["popular_answers"]}
    assert options[option.id] == 1


@pytest.mark.django_db
def test_demo_data_endpoint_creates_survey_for_swagger(api_client):
    response = api_client.post(
        "/api/demo-data/",
        {"title": "Swagger demo", "username": "swagger_user"},
        format="json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["survey_id"]
    assert body["user_id"]
    assert body["next_question_url"].startswith("/api/surveys/")
    assert len(body["questions"]) == 15
    assert all(len(question["options"]) == 5 for question in body["questions"])


@pytest.mark.django_db
def test_openapi_schema_and_swagger_are_available(api_client):
    schema_response = api_client.get("/api/schema/")
    docs_response = api_client.get("/api/docs/")

    assert schema_response.status_code == 200
    assert docs_response.status_code == 200
