from django.urls import path

from polls.views import AnswerQuestionView, DemoDataView, NextQuestionView, SurveyStatsView

urlpatterns = [
    path("demo-data/", DemoDataView.as_view()),
    path("surveys/<int:survey_id>/next-question/", NextQuestionView.as_view()),
    path("surveys/<int:survey_id>/answers/", AnswerQuestionView.as_view()),
    path("surveys/<int:survey_id>/stats/", SurveyStatsView.as_view()),
]
