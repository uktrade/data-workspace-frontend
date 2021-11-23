from datetime import datetime

import pytest
from freezegun import freeze_time

from dataworkspace.tests import factories


@pytest.mark.django_db
@freeze_time("2021-05-25 15:23:00")
def test_publish_unpublished():
    case_study = factories.CaseStudyFactory(published=False)
    assert case_study.publish_date is None
    case_study.published = True
    case_study.save()
    assert case_study.publish_date == datetime(2021, 5, 25, 15, 23, 0)


@pytest.mark.django_db
@freeze_time("2021-05-25 15:25:00")
def test_publish():
    case_study = factories.CaseStudyFactory(published=True)
    assert case_study.publish_date == datetime(2021, 5, 25, 15, 25, 0)


@pytest.mark.django_db
@freeze_time("2021-05-25 15:44:00")
def test_unpublish_published():
    case_study = factories.CaseStudyFactory(published=True)
    assert case_study.publish_date == datetime(2021, 5, 25, 15, 44, 0)
    case_study.published = False
    case_study.save()
    assert case_study.publish_date is None
