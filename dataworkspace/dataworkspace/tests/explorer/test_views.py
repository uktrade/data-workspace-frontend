import time

from django.db import connections

try:
    from django.urls import reverse
except ImportError:
    from django.core.urlresolvers import reverse
from django.contrib.auth import get_user_model
from django.forms.models import model_to_dict

from lxml import html
import pytest

from dataworkspace.apps.core.utils import USER_SCHEMA_STEM, stable_identification_suffix
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.explorer.models import Query, QueryLog, PlaygroundSQL
from dataworkspace.tests.factories import UserFactory
from dataworkspace.tests.explorer.factories import (
    QueryLogFactory,
    SimpleQueryFactory,
    PlaygroundSQLFactory,
)


class TestQueryListView:
    def test_run_count(self, user, client):
        q = SimpleQueryFactory(title='foo - bar1', created_by_user=user)
        for _ in range(0, 4):
            QueryLog.objects.create(query=q)
        resp = client.get(reverse("explorer:list_queries"))
        assert '4' in resp.content.decode(resp.charset)


@pytest.mark.django_db(transaction=True)
class TestQueryCreateView:
    def test_renders_with_title(self, staff_user, staff_client):
        play_sql = PlaygroundSQLFactory(sql="", created_by_user=staff_user)
        resp = staff_client.get(
            reverse("explorer:query_create"), {"play_id": play_sql.id}
        )
        assert resp.template_name == ['explorer/query.html']
        assert "New Query" in resp.content.decode(resp.charset)

    def test_valid_query(self, staff_user, staff_client):
        query = SimpleQueryFactory.build(sql='SELECT 1;', created_by_user=staff_user)
        data = model_to_dict(query)
        data['action'] = "save"
        del data['id']
        del data['created_by_user']

        staff_client.post(reverse("explorer:query_create"), data)

        assert Query.objects.all()[0].sql == 'SELECT 1;'

    def test_invalid_query_saved(self, staff_user, staff_client):
        query = SimpleQueryFactory.build(
            sql='SELECT foo; DELETE FROM foo;', created_by_user=staff_user
        )
        data = model_to_dict(query)
        data['action'] = "save"
        del data['id']
        del data['created_by_user']

        staff_client.post(reverse("explorer:query_create"), data)

        assert Query.objects.all()[0].sql == 'SELECT foo; DELETE FROM foo;'

    @pytest.mark.django_db(transaction=True)
    def test_renders_back_link(self, staff_user, staff_client):
        play_sql = PlaygroundSQLFactory(
            sql="select 1, 2, 3", created_by_user=staff_user
        )
        response = staff_client.get(
            reverse("explorer:query_create"), {"play_id": play_sql.id}
        )
        assert (
            f'<a href="/data-explorer/?play_id={play_sql.id}" class="govuk-back-link">Back</a>'
            in response.content.decode(response.charset)
        )


class TestQueryDetailView:
    databases = ['my_database', 'test_external_db']

    def test_query_with_bad_sql_fails_on_save(self, staff_user, staff_client):
        query = SimpleQueryFactory(sql="select 1;", created_by_user=staff_user)

        resp = staff_client.post(
            reverse("explorer:query_detail", kwargs={'query_id': query.id}),
            data={'title': query.title, 'sql': 'error', "action": "save"},
        )

        assert (
            "Enter a SQL statement starting with SELECT or WITH"
            in resp.content.decode(resp.charset)
        )

    def test_posting_query_saves_correctly(self, staff_user, staff_client):
        expected = 'select 2;'
        query = SimpleQueryFactory(sql="select 1;", created_by_user=staff_user)
        data = model_to_dict(query)
        data['sql'] = expected
        data['action'] = 'save'

        staff_client.post(
            reverse("explorer:query_detail", kwargs={'query_id': query.id}), data
        )

        assert Query.objects.get(pk=query.id).sql == expected

    def test_saving_query_creates_eventlog_entry(self, staff_user, staff_client):
        expected = 'select 2;'
        query = SimpleQueryFactory(sql="select 1;", created_by_user=staff_user)
        data = model_to_dict(query)
        data['sql'] = expected
        data['action'] = 'save'

        eventlog_count = EventLog.objects.count()

        staff_client.post(
            reverse("explorer:query_detail", kwargs={'query_id': query.id}), data
        )

        assert (
            EventLog.objects.filter(
                event_type=EventLog.TYPE_DATA_EXPLORER_SAVED_QUERY
            ).count()
            == eventlog_count + 1
        )

    def test_change_permission_required_to_save_query(self, staff_user, staff_client):
        query = SimpleQueryFactory(created_by_user=staff_user)
        expected = query.sql

        staff_client.get(
            reverse("explorer:query_detail", kwargs={'query_id': query.id})
        )
        staff_client.post(
            reverse("explorer:query_detail", kwargs={'query_id': query.id}),
            {'sql': 'select 1;'},
        )

        assert Query.objects.get(pk=query.id).sql == expected

    def test_modified_date_gets_updated_after_viewing_query(
        self, staff_user, staff_client
    ):
        query = SimpleQueryFactory(created_by_user=staff_user)
        old = query.last_run_date
        time.sleep(0.1)

        staff_client.get(
            reverse("explorer:query_detail", kwargs={'query_id': query.id})
        )

        assert old != Query.objects.get(pk=query.id).last_run_date

    def test_cannot_view_another_users_query(self, staff_user, staff_client):
        other_user = UserFactory(email='foo@bar.net')
        other_query = SimpleQueryFactory(created_by_user=other_user)

        resp = staff_client.get(
            reverse("explorer:query_detail", kwargs={'query_id': other_query.id})
        )
        assert resp.status_code == 404

    def test_doesnt_render_results_if_show_is_none(self, staff_user, staff_client):
        query = SimpleQueryFactory(sql='select 6870+1;', created_by_user=staff_user)

        resp = staff_client.get(
            reverse("explorer:query_detail", kwargs={'query_id': query.id}) + '?show=0'
        )

        assert '6871' not in resp.content.decode(resp.charset)

    def test_doesnt_render_results_on_page(self, staff_user, staff_client):
        query = SimpleQueryFactory(sql='select 6870+1;', created_by_user=staff_user)

        resp = staff_client.post(
            reverse("explorer:query_detail", kwargs={'query_id': query.id}),
            {'sql': 'select 6870+2;', 'action': 'save'},
        )

        assert '6872' not in resp.content.decode(resp.charset)

    def test_renders_back_link(self, staff_user, staff_client):
        query = SimpleQueryFactory(sql='select 6870+1;', created_by_user=staff_user)
        play_sql = PlaygroundSQLFactory(
            sql='select 1+6870;', created_by_user=staff_user
        )

        response = staff_client.get(
            reverse("explorer:query_detail", kwargs={"query_id": query.id}),
            {"play_id": play_sql.id},
        )

        assert (
            f'<a href="/data-explorer/?query_id={query.id}&amp;play_id={play_sql.id}" class="govuk-back-link">Back</a>'
            in response.content.decode(response.charset)
        )

    def test_cannot_post_to_another_users_query(self, staff_user, staff_client):
        query_creator = get_user_model().objects.create_superuser(
            'admin', 'admin@admin.com', 'pwd'
        )
        query = SimpleQueryFactory.create(created_by_user=query_creator)

        data = model_to_dict(query)
        del data['id']
        data["created_by_user_id"] = staff_user.id

        resp = staff_client.post(
            reverse("explorer:query_detail", kwargs={'query_id': query.id}),
            {**data, "action": "save"},
        )
        query = Query.objects.get(id=query.id)
        assert resp.status_code == 404
        assert query.created_by_user_id == query_creator.id


@pytest.mark.django_db(transaction=True)
class TestHomePage:
    databases = ['my_database', 'test_external_db']

    @pytest.fixture(scope='function', autouse=True)
    def setUp(self, staff_user_data):
        suffix = stable_identification_suffix(
            staff_user_data["HTTP_SSO_PROFILE_USER_ID"], short=True
        )
        schema_and_user_name = f'{USER_SCHEMA_STEM}{suffix}'
        for alias in self.databases:
            with connections[alias].cursor() as cursor:
                cursor.execute(f'CREATE SCHEMA IF NOT EXISTS {schema_and_user_name}')
                cursor.execute(
                    f'GRANT ALL ON SCHEMA {schema_and_user_name} TO {schema_and_user_name}'
                )

    def test_empty_playground_renders(self, staff_client):
        resp = staff_client.get(reverse("explorer:index"))
        assert resp.status_code == 200

    def test_support_and_feedback_link(self, staff_client):
        resp = staff_client.get(reverse("explorer:index"))

        doc = html.fromstring(resp.content.decode(resp.charset))
        assert (
            doc.xpath('//a[normalize-space(text()) = "feedback"]/@href')[0]
            == '/support-and-feedback/'
        )

    def test_playground_renders_with_query_sql(self, staff_user, staff_client):
        query = SimpleQueryFactory(sql="select 1;", created_by_user=staff_user)
        resp = staff_client.get(
            '%s?query_id=%s' % (reverse("explorer:index"), query.id)
        )
        assert resp.status_code == 200
        assert 'select 1;' in resp.content.decode(resp.charset)

    def test_cannot_open_playground_with_another_users_query(self, staff_client):
        other_user = UserFactory(email='foo@bar.net')
        query = SimpleQueryFactory(sql="select 1;", created_by_user=other_user)
        resp = staff_client.get(
            '%s?query_id=%s' % (reverse("explorer:index"), query.id)
        )
        assert resp.status_code == 404

    def test_cannot_post_to_another_users_query(self, staff_client):
        other_user = UserFactory(email='foo@bar.net')
        query = SimpleQueryFactory(sql="select 1;", created_by_user=other_user)

        resp = staff_client.post(
            reverse("explorer:index") + f"?query_id={query.id}",
            {'title': 'test', 'sql': 'select 1+3400;', "action": "save"},
        )
        assert resp.status_code == 404

    def test_playground_renders_with_posted_sql(self, staff_client):
        resp = staff_client.post(
            reverse("explorer:index"),
            {'title': 'test', 'sql': 'select 1+3400;', "action": "run"},
        )
        assert '3401' in resp.content.decode(resp.charset)

    @pytest.mark.parametrize(
        "page, rows, expected_page, expected_rows",
        (("1", "1000", "1", "1000"), ("2", "3", "2", "3"), ("a", "b", "1", "1000"),),
    )
    def test_playground_suppresses_errors_from_invalid_pagination_values(
        self, page, rows, expected_page, expected_rows, staff_client
    ):
        resp = staff_client.post(
            reverse("explorer:index"),
            {
                'title': 'test',
                'sql': 'select 1+3400;',
                "query-page": page,
                "query-rows": rows,
                "action": "fetch-page",
            },
        )
        doc = html.fromstring(resp.content.decode(resp.charset))

        assert resp.status_code == 200
        assert doc.xpath("//input[@id='query-page']/@value")[0] == expected_page
        assert doc.xpath("//input[@id='query-rows']/@value")[0] == expected_rows

    def test_playground_redirects_to_query_create_on_save_with_sql_query_param(
        self, staff_user, staff_client
    ):
        resp = staff_client.post(
            reverse("explorer:index"), {'sql': 'select 1+3400;', "action": "save"}
        )
        play_sql = PlaygroundSQL.objects.get(
            sql='select 1+3400;', created_by_user=staff_user
        )

        assert resp.url == f'/data-explorer/queries/create/?play_id={play_sql.id}'

    def test_playground_renders_with_empty_posted_sql(self, staff_client):
        resp = staff_client.post(
            reverse("explorer:index"), {'sql': '', "action": "run"}
        )
        assert resp.status_code == 200

    def test_query_with_no_resultset_doesnt_throw_error(self, staff_user, staff_client):
        query = SimpleQueryFactory(sql="", created_by_user=staff_user)
        resp = staff_client.get(
            '%s?query_id=%s' % (reverse("explorer:index"), query.id)
        )
        assert resp.status_code == 200

    def test_can_only_load_query_log_run_by_current_user(
        self, staff_user, staff_client
    ):
        user = UserFactory(email='test@foo.bar')
        my_querylog = QueryLogFactory(run_by_user=staff_user)
        other_querylog = QueryLogFactory(run_by_user=user)

        resp = staff_client.get(
            '%s?querylog_id=%s' % (reverse("explorer:index"), my_querylog.id)
        )
        assert resp.status_code == 200
        assert "FOUR" in resp.content.decode(resp.charset)

        resp = staff_client.get(
            '%s?querylog_id=%s' % (reverse("explorer:index"), other_querylog.id)
        )
        assert resp.status_code == 404


class TestCSVFromSQL:
    databases = ['my_database']

    @pytest.fixture(scope='function', autouse=True)
    def setUp(self, staff_user_data):
        suffix = stable_identification_suffix(
            staff_user_data["HTTP_SSO_PROFILE_USER_ID"], short=True
        )
        schema_and_user_name = f'{USER_SCHEMA_STEM}{suffix}'
        for alias in self.databases:
            with connections[alias].cursor() as cursor:
                cursor.execute(f'CREATE SCHEMA IF NOT EXISTS {schema_and_user_name}')
                cursor.execute(
                    f'GRANT ALL ON SCHEMA {schema_and_user_name} TO {schema_and_user_name}'
                )

    def test_downloading_from_playground(self, staff_user, staff_client):
        sql = "select 1;"
        resp = staff_client.post(reverse("explorer:download_sql"), {'sql': sql})

        assert 'attachment' in resp['Content-Disposition']
        assert 'text/csv' in resp['content-type']
        assert 'filename="Playground_-_select_1.csv"' in resp['Content-Disposition']


class TestSQLDownloadViews:
    databases = ['my_database']

    @pytest.fixture(scope='function', autouse=True)
    def setUp(self, staff_user_data):
        suffix = stable_identification_suffix(
            staff_user_data["HTTP_SSO_PROFILE_USER_ID"], short=True
        )
        schema_and_user_name = f'{USER_SCHEMA_STEM}{suffix}'
        for alias in self.databases:
            with connections[alias].cursor() as cursor:
                cursor.execute(f'CREATE SCHEMA IF NOT EXISTS {schema_and_user_name}')
                cursor.execute(
                    f'GRANT ALL ON SCHEMA {schema_and_user_name} TO {schema_and_user_name}'
                )

    def test_sql_download_csv(self, staff_client):
        url = reverse("explorer:download_sql") + '?format=csv'

        response = staff_client.post(url, {'sql': 'select 1;'})

        assert response.status_code == 200
        assert response['content-type'] == 'text/csv'

    def test_sql_download_csv_with_custom_delim(self, staff_client):
        url = reverse("explorer:download_sql") + '?format=csv&delim=|'

        response = staff_client.post(url, {'sql': 'select 1,2;'})

        assert response.status_code == 200
        assert response['content-type'] == 'text/csv'
        assert response.content.decode('utf-8') == '?column?|?column?\r\n1|2\r\n'

    def test_sql_download_csv_with_tab_delim(self, staff_client):
        url = reverse("explorer:download_sql") + '?format=csv&delim=tab'

        response = staff_client.post(url, {'sql': 'select 1,2;'})

        assert response.status_code == 200
        assert response['content-type'] == 'text/csv'
        assert response.content.decode('utf-8') == '?column?\t?column?\r\n1\t2\r\n'

    def test_sql_download_csv_with_bad_delim(self, staff_client):
        url = reverse("explorer:download_sql") + '?format=csv&delim=foo'

        response = staff_client.post(url, {'sql': 'select 1,2;'})

        assert response.status_code == 200
        assert response['content-type'] == 'text/csv'
        assert response.content.decode('utf-8') == '?column?,?column?\r\n1,2\r\n'

    def test_sql_download_json(self, staff_client):
        url = reverse("explorer:download_sql") + '?format=json'

        response = staff_client.post(url, {'sql': 'select 1;'})

        assert response.status_code == 200
        assert response['content-type'] == 'application/json'


@pytest.mark.django_db(transaction=True)
class TestParamsInViews:
    def test_retrieving_query_works_with_params(self, staff_user, staff_client):
        query = SimpleQueryFactory(sql="select $$swap$$;", created_by_user=staff_user)
        resp = staff_client.get(
            reverse("explorer:index") + f"?query_id={query.id}&params=swap:1234567890"
        )
        assert "1234567890" in resp.content.decode(resp.charset)


@pytest.mark.django_db(transaction=True)
class TestCreatedBy:
    def test_new_query_gets_created_by_logged_in_user(self, staff_user, staff_client):
        query = SimpleQueryFactory.build(created_by_user=staff_user)
        data = model_to_dict(query)
        del data['id']

        staff_client.post(reverse("explorer:query_create"), {**data, "action": "save"})
        query = Query.objects.first()
        assert query.created_by_user_id == staff_user.id


@pytest.mark.django_db(transaction=True)
class TestQueryLog:
    def test_playground_saves_query_to_log(self, staff_client):
        staff_client.post(
            reverse("explorer:index"),
            {'title': 'test', 'sql': 'select 1', "action": "run"},
        )
        log = QueryLog.objects.first()
        assert log.is_playground
        assert log.sql == 'select 1'

    # Since it will be saved on the initial query creation, no need to log it
    def test_creating_query_does_not_save_to_log(self, staff_user, staff_client):
        query = SimpleQueryFactory(created_by_user=staff_user)
        staff_client.post(reverse("explorer:query_create"), model_to_dict(query))
        assert QueryLog.objects.count() == 0

    def test_query_saves_to_log(self, staff_user, staff_client):
        query = SimpleQueryFactory(created_by_user=staff_user)
        data = model_to_dict(query)
        data['sql'] = 'select 12345;'
        data['action'] = 'run'
        staff_client.post(reverse("explorer:index") + f"?query_id={query.id}", data)
        assert QueryLog.objects.count() == 1

    def test_user_can_only_see_their_own_queries_on_log_page(
        self, staff_user, staff_client
    ):
        other_user = UserFactory(email='foo@bar.net')
        QueryLogFactory(sql="select 1234", run_by_user=other_user)
        QueryLogFactory(sql="select 9876", run_by_user=staff_user)

        resp = staff_client.get(reverse("explorer:explorer_logs"))

        assert "select 9876" in resp.content.decode(resp.charset)
        assert "select 1234" not in resp.content.decode(resp.charset)

    def test_is_playground(self):
        assert QueryLog(sql='foo').is_playground is True
        q = SimpleQueryFactory()
        assert QueryLog(sql='foo', query_id=q.id).is_playground is False
