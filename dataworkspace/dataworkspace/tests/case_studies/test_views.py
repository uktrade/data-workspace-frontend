import pytest
from django.urls import reverse

from dataworkspace.tests import factories


def test_list_view_no_results(client):
    response = client.get(reverse("case-studies:case-studies"))
    assert response.status_code == 200
    assert "There are no case studies to show currently" in response.content.decode(
        response.charset
    )


@pytest.mark.django_db
def test_list_view_single_page(client):
    case_studies = [
        factories.CaseStudyFactory.create(),
        factories.CaseStudyFactory.create(),
    ]
    response = client.get(reverse("case-studies:case-studies"))
    assert response.status_code == 200
    for case_study in case_studies:
        assert case_study.name in response.content.decode(response.charset)
        assert case_study.short_description in response.content.decode(response.charset)
    assert "Displaying case studies 1&ndash;2 of 2" in response.content.decode(response.charset)


@pytest.mark.django_db
def test_list_view_multiple_pages(client):
    factories.CaseStudyFactory.create_batch(20)
    response = client.get(reverse("case-studies:case-studies"))
    assert response.status_code == 200
    assert "Displaying case studies 1&ndash;10 of 20" in response.content.decode(response.charset)
    response = client.get(reverse("case-studies:case-studies") + "?page=2")
    assert response.status_code == 200
    assert "Displaying case studies 11&ndash;20 of 20" in response.content.decode(response.charset)


@pytest.mark.django_db
def test_detail_view_unpublished(client):
    case_study = factories.CaseStudyFactory.create(published=False)
    response = client.get(reverse("case-studies:case-study", args=(case_study.id,)))
    assert response.status_code == 404


@pytest.mark.django_db
def test_detail_view_published(client):
    case_study1 = factories.CaseStudyFactory.create(published=True)
    case_study2 = factories.CaseStudyFactory.create(published=True)
    case_study3 = factories.CaseStudyFactory.create(published=False)
    response = client.get(reverse("case-studies:case-study", args=(case_study1.slug,)))
    assert response.status_code == 200
    content = response.content.decode(response.charset)
    assert case_study1.name in content
    assert case_study1.background in content
    assert case_study1.solution in content
    assert case_study1.impact in content
    assert case_study2.name in content
    assert case_study3.name not in content
