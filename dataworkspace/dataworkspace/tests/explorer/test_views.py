import time

from mock import mock

from waffle.testutils import override_flag

try:
    from django.urls import reverse
except ImportError:
    from django.core.urlresolvers import reverse
from django.conf import settings
from django.core.cache import cache
from django.db import connections
from django.contrib.auth import get_user_model
from django.forms.models import model_to_dict
from lxml import html
import pytest

from dataworkspace.apps.core.charts.models import ChartBuilderChart
from dataworkspace.apps.core.utils import USER_SCHEMA_STEM, stable_identification_suffix
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.explorer.constants import QueryLogState
from dataworkspace.apps.explorer.models import Query, QueryLog, PlaygroundSQL
from dataworkspace.tests.factories import UserFactory
from dataworkspace.tests.explorer.factories import (
    QueryLogFactory,
    SimpleQueryFactory,
    PlaygroundSQLFactory,
)


def create_temporary_results_table(querylog):
    # ID hardcoded in conftest.staff_user_data
    suffix = stable_identification_suffix("aae8901a-082f-4f12-8c6c-fdf4aeba2d68", short=True)
    schema_and_user_name = f"{USER_SCHEMA_STEM}{suffix}"

    with connections["my_database"].cursor() as cursor:
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_and_user_name}")
        cursor.execute(
            f"DROP TABLE IF EXISTS {schema_and_user_name}._data_explorer_tmp_query_{querylog.id}"
        )
        cursor.execute(
            f"CREATE TABLE {schema_and_user_name}._data_explorer_tmp_query_{querylog.id} "
            "(id int primary key, data text)"
        )
        cursor.execute(
            f"INSERT INTO {schema_and_user_name}._data_explorer_tmp_query_{querylog.id} VALUES (1, 2)"
        )
        cursor.execute(
            f"ALTER TABLE {schema_and_user_name}._data_explorer_tmp_query_{querylog.id} OWNER TO {schema_and_user_name}"
        )


def drop_temporary_results_table(querylog):
    # ID hardcoded in conftest.staff_user_data
    suffix = stable_identification_suffix("aae8901a-082f-4f12-8c6c-fdf4aeba2d68", short=True)
    schema_and_user_name = f"{USER_SCHEMA_STEM}{suffix}"

    with connections["my_database"].cursor() as cursor:
        cursor.execute(
            f"DROP TABLE IF EXISTS {schema_and_user_name}._data_explorer_tmp_query_{querylog.id}"
        )


class TestQueryListView:
    def test_run_count(self, user, client):
        q = SimpleQueryFactory(title="foo - bar1", created_by_user=user)
        for _ in range(0, 4):
            QueryLogFactory(query=q)
        resp = client.get(reverse("explorer:list_queries"))
        assert "4" in resp.content.decode(resp.charset)


@pytest.mark.django_db(transaction=True)
class TestQueryCreateView:
    def test_renders_with_title(self, staff_user, staff_client):
        play_sql = PlaygroundSQLFactory(sql="", created_by_user=staff_user)
        resp = staff_client.get(reverse("explorer:query_create"), {"play_id": play_sql.id})
        assert resp.template_name == ["explorer/query.html"]
        assert "New Query" in resp.content.decode(resp.charset)

    def test_valid_query(self, staff_user, staff_client):
        query = SimpleQueryFactory.build(sql="SELECT 1;", created_by_user=staff_user)
        data = model_to_dict(query)
        data["action"] = "save"
        del data["id"]
        del data["created_by_user"]

        staff_client.post(reverse("explorer:query_create"), data)

        assert Query.objects.all()[0].sql == "SELECT 1;"

    def test_invalid_query_saved(self, staff_user, staff_client):
        query = SimpleQueryFactory.build(
            sql="SELECT foo; DELETE FROM foo;", created_by_user=staff_user
        )
        data = model_to_dict(query)
        data["action"] = "save"
        del data["id"]
        del data["created_by_user"]

        staff_client.post(reverse("explorer:query_create"), data)

        assert Query.objects.all()[0].sql == "SELECT foo; DELETE FROM foo;"

    @pytest.mark.django_db(transaction=True)
    def test_renders_back_link(self, staff_user, staff_client):
        play_sql = PlaygroundSQLFactory(sql="select 1, 2, 3", created_by_user=staff_user)
        response = staff_client.get(reverse("explorer:query_create"), {"play_id": play_sql.id})
        assert (
            f'<a href="/data-explorer/?play_id={play_sql.id}" class="govuk-back-link">Back</a>'
            in response.content.decode(response.charset)
        )


class TestQueryDetailView:
    def test_query_with_bad_sql_fails_on_save(self, staff_user, staff_client):
        query = SimpleQueryFactory(sql="select 1;", created_by_user=staff_user)

        resp = staff_client.post(
            reverse("explorer:query_detail", kwargs={"query_id": query.id}),
            data={"title": query.title, "sql": "error", "action": "save"},
        )

        assert (
            "Enter a SQL statement starting with SELECT, WITH or EXPLAIN"
            in resp.content.decode(resp.charset)
        )

    def test_posting_query_saves_correctly(self, staff_user, staff_client):
        expected = "select 2;"
        query = SimpleQueryFactory(sql="select 1;", created_by_user=staff_user)
        data = model_to_dict(query)
        data["sql"] = expected
        data["action"] = "save"

        staff_client.post(reverse("explorer:query_detail", kwargs={"query_id": query.id}), data)

        assert Query.objects.get(pk=query.id).sql == expected

    def test_saving_query_creates_eventlog_entry(self, staff_user, staff_client):
        expected = "select 2;"
        query = SimpleQueryFactory(sql="select 1;", created_by_user=staff_user)
        data = model_to_dict(query)
        data["sql"] = expected
        data["action"] = "save"

        eventlog_count = EventLog.objects.count()

        staff_client.post(reverse("explorer:query_detail", kwargs={"query_id": query.id}), data)

        assert (
            EventLog.objects.filter(event_type=EventLog.TYPE_DATA_EXPLORER_SAVED_QUERY).count()
            == eventlog_count + 1
        )

    def test_change_permission_required_to_save_query(self, staff_user, staff_client):
        query = SimpleQueryFactory(created_by_user=staff_user)
        expected = query.sql

        staff_client.get(reverse("explorer:query_detail", kwargs={"query_id": query.id}))
        staff_client.post(
            reverse("explorer:query_detail", kwargs={"query_id": query.id}),
            {"sql": "select 1;"},
        )

        assert Query.objects.get(pk=query.id).sql == expected

    def test_modified_date_gets_updated_after_viewing_query(self, staff_user, staff_client):
        query = SimpleQueryFactory(created_by_user=staff_user)
        old = query.last_run_date
        time.sleep(0.1)

        staff_client.get(reverse("explorer:query_detail", kwargs={"query_id": query.id}))

        assert old != Query.objects.get(pk=query.id).last_run_date

    def test_cannot_view_another_users_query(self, staff_user, staff_client):
        other_user = UserFactory(email="foo@bar.net")
        other_query = SimpleQueryFactory(created_by_user=other_user)

        resp = staff_client.get(
            reverse("explorer:query_detail", kwargs={"query_id": other_query.id})
        )
        assert resp.status_code == 404

    def test_doesnt_render_results_if_show_is_none(self, staff_user, staff_client):
        query = SimpleQueryFactory(sql="select 6870+1;", created_by_user=staff_user)

        resp = staff_client.get(
            reverse("explorer:query_detail", kwargs={"query_id": query.id}) + "?show=0"
        )

        assert "6871" not in resp.content.decode(resp.charset)

    def test_doesnt_render_results_on_page(self, staff_user, staff_client):
        query = SimpleQueryFactory(sql="select 6870+1;", created_by_user=staff_user)

        resp = staff_client.post(
            reverse("explorer:query_detail", kwargs={"query_id": query.id}),
            {"sql": "select 6870+2;", "action": "save"},
        )

        assert "6872" not in resp.content.decode(resp.charset)

    def test_renders_back_link(self, staff_user, staff_client):
        query = SimpleQueryFactory(sql="select 6870+1;", created_by_user=staff_user)
        play_sql = PlaygroundSQLFactory(sql="select 1+6870;", created_by_user=staff_user)

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
            "admin", "admin@admin.com", "pwd"
        )
        query = SimpleQueryFactory.create(created_by_user=query_creator)

        data = model_to_dict(query)
        del data["id"]
        data["created_by_user_id"] = staff_user.id

        resp = staff_client.post(
            reverse("explorer:query_detail", kwargs={"query_id": query.id}),
            {**data, "action": "save"},
        )
        query = Query.objects.get(id=query.id)
        assert resp.status_code == 404
        assert query.created_by_user_id == query_creator.id


@pytest.mark.django_db(transaction=True)
class TestHomePage:
    @pytest.fixture(scope="function", autouse=True)
    def _clear_cache(self):
        # We want each test to generate new user database credentials to avoid cached permission issues.
        cache.clear()

    def test_empty_playground_renders(self, staff_client):
        resp = staff_client.get(reverse("explorer:index"))
        assert resp.status_code == 200

    def test_support_and_feedback_link(self, staff_client):
        resp = staff_client.get(reverse("explorer:index"))

        doc = html.fromstring(resp.content.decode(resp.charset))
        assert doc.xpath('//a[normalize-space(text()) = "feedback"]/@href')[0] == "/feedback/"

    def test_playground_renders_with_query_sql(self, staff_user, staff_client):
        query = SimpleQueryFactory(sql="select 1;", created_by_user=staff_user)
        resp = staff_client.get("%s?query_id=%s" % (reverse("explorer:index"), query.id))
        assert resp.status_code == 200
        assert "select 1;" in resp.content.decode(resp.charset)

    def test_cannot_open_playground_with_another_users_query(self, staff_client):
        other_user = UserFactory(email="foo@bar.net")
        query = SimpleQueryFactory(sql="select 1;", created_by_user=other_user)
        resp = staff_client.get("%s?query_id=%s" % (reverse("explorer:index"), query.id))
        assert resp.status_code == 404

    def test_cannot_post_to_another_users_query(self, staff_client):
        other_user = UserFactory(email="foo@bar.net")
        query = SimpleQueryFactory(sql="select 1;", created_by_user=other_user)

        resp = staff_client.post(
            reverse("explorer:index") + f"?query_id={query.id}",
            {"title": "test", "sql": "select 1+3400;", "action": "save"},
        )
        assert resp.status_code == 404

    def test_async_playground_redirects_to_results_page(self, staff_client):
        resp = staff_client.post(
            reverse("explorer:index"),
            {"title": "test", "sql": "select 1+3400;", "action": "run"},
        )
        assert resp.status_code == 302
        assert resp["Location"] == reverse(
            "explorer:running_query", args=(QueryLog.objects.last().id,)
        )

    def test_playground_redirects_to_query_create_on_save_with_sql_query_param(
        self, staff_user, staff_client
    ):
        resp = staff_client.post(
            reverse("explorer:index"), {"sql": "select 1+3400;", "action": "save"}
        )
        play_sql = PlaygroundSQL.objects.get(sql="select 1+3400;", created_by_user=staff_user)

        assert resp.url == f"/data-explorer/queries/create/?play_id={play_sql.id}"

    def test_playground_renders_with_empty_posted_sql(self, staff_client):
        resp = staff_client.post(reverse("explorer:index"), {"sql": "", "action": "run"})
        assert resp.status_code == 200

    def test_query_with_no_resultset_doesnt_throw_error(self, staff_user, staff_client):
        query = SimpleQueryFactory(sql="", created_by_user=staff_user)
        resp = staff_client.get("%s?query_id=%s" % (reverse("explorer:index"), query.id))
        assert resp.status_code == 200

    def test_can_only_load_query_log_run_by_current_user(self, staff_user, staff_client):
        user = UserFactory(email="test@foo.bar")
        my_querylog = QueryLogFactory(run_by_user=staff_user)
        other_querylog = QueryLogFactory(run_by_user=user)

        resp = staff_client.get("%s?querylog_id=%s" % (reverse("explorer:index"), my_querylog.id))
        assert resp.status_code == 200
        assert "FOUR" in resp.content.decode(resp.charset)

        resp = staff_client.get(
            "%s?querylog_id=%s" % (reverse("explorer:index"), other_querylog.id)
        )
        assert resp.status_code == 404


class TestCSVFromSQL:
    @pytest.fixture(scope="function", autouse=True)
    def _clear_cache(self):
        # We want each test to generate new user database credentials to avoid cached permission issues.
        cache.clear()

    def test_downloading_from_playground(self, staff_user, staff_client):
        querylog = QueryLogFactory.create(sql="select 1, 2", run_by_user=staff_user)
        create_temporary_results_table(querylog)

        resp = staff_client.get(
            reverse("explorer:download_querylog", kwargs=dict(querylog_id=querylog.id))
        )

        assert "attachment" in resp["Content-Disposition"]
        assert "text/csv" in resp["content-type"]
        assert 'filename="Playground_-_select_1_2.csv"' in resp["Content-Disposition"]

    def test_downloading_from_results_table_redirects_with_error_if_table_is_not_there(
        self, staff_user, staff_client
    ):
        querylog = QueryLogFactory.create(sql="select 1, 2", run_by_user=staff_user)

        # Make sure it's not there
        drop_temporary_results_table(querylog)

        resp = staff_client.get(
            reverse("explorer:download_querylog", kwargs=dict(querylog_id=querylog.id)),
        )

        assert resp.status_code == 302
        assert resp["Location"] == f"/data-explorer/?querylog_id={querylog.id}&error=download"


class TestSQLDownloadViews:
    @pytest.fixture(scope="function", autouse=True)
    def _clear_cache(self):
        # We want each test to generate new user database credentials to avoid cached permission issues.
        cache.clear()

    def test_sql_download_csv(self, staff_user, staff_client):
        my_querylog = QueryLogFactory(sql="select 1,2", run_by_user=staff_user)
        create_temporary_results_table(my_querylog)

        url = (
            reverse(
                "explorer:download_querylog",
                kwargs=dict(querylog_id=my_querylog.id),
            )
            + "?format=csv"
        )

        response = staff_client.get(url)

        assert response.status_code == 200
        assert response["content-type"] == "text/csv"

    def test_sql_download_csv_with_custom_delim(self, staff_user, staff_client):
        my_querylog = QueryLogFactory(sql="select 1 as id, 2 as data", run_by_user=staff_user)
        create_temporary_results_table(my_querylog)

        url = (
            reverse(
                "explorer:download_querylog",
                kwargs=dict(querylog_id=my_querylog.id),
            )
            + "?format=csv&delim=|"
        )

        response = staff_client.get(url)

        assert response.status_code == 200
        assert response["content-type"] == "text/csv"
        assert response.content.decode("utf-8") == "id|data\r\n1|2\r\n"

    def test_sql_download_csv_with_tab_delim(self, staff_user, staff_client):
        my_querylog = QueryLogFactory(sql="select 1 as id, 2 as data", run_by_user=staff_user)
        create_temporary_results_table(my_querylog)

        url = (
            reverse(
                "explorer:download_querylog",
                kwargs=dict(querylog_id=my_querylog.id),
            )
            + "?format=csv&delim=tab"
        )

        response = staff_client.get(url)

        assert response.status_code == 200
        assert response["content-type"] == "text/csv"
        assert response.content.decode("utf-8") == "id\tdata\r\n1\t2\r\n"

    def test_sql_download_csv_with_bad_delim(self, staff_user, staff_client):
        my_querylog = QueryLogFactory(sql="select 1 as id, 2 as data", run_by_user=staff_user)
        create_temporary_results_table(my_querylog)

        url = (
            reverse(
                "explorer:download_querylog",
                kwargs=dict(querylog_id=my_querylog.id),
            )
            + "?format=csv&delim=foo"
        )

        response = staff_client.get(url)

        assert response.status_code == 200
        assert response["content-type"] == "text/csv"
        assert response.content.decode("utf-8") == "id,data\r\n1,2\r\n"

    def test_sql_download_json(self, staff_user, staff_client):
        my_querylog = QueryLogFactory(sql="select 1,2", run_by_user=staff_user)
        create_temporary_results_table(my_querylog)

        url = (
            reverse(
                "explorer:download_querylog",
                kwargs=dict(querylog_id=my_querylog.id),
            )
            + "?format=json"
        )

        response = staff_client.get(url)

        assert response.status_code == 200
        assert response["content-type"] == "application/json"

    def test_cannot_download_someone_elses_querylog(self, staff_user, staff_client):
        other_user = UserFactory(email="foo@bar.net")
        my_querylog = QueryLogFactory(sql="select 1,2", run_by_user=other_user)
        create_temporary_results_table(my_querylog)

        url = (
            reverse(
                "explorer:download_querylog",
                kwargs=dict(querylog_id=my_querylog.id),
            )
            + "?format=json"
        )

        response = staff_client.get(url)
        assert response.status_code == 404


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
        del data["id"]

        staff_client.post(reverse("explorer:query_create"), {**data, "action": "save"})
        query = Query.objects.first()
        assert query.created_by_user_id == staff_user.id


@pytest.mark.django_db(transaction=True)
class TestQueryLog:
    def test_playground_saves_query_to_log(self, staff_client):
        staff_client.post(
            reverse("explorer:index"),
            {"title": "test", "sql": "select 1", "action": "run"},
        )
        log = QueryLog.objects.first()
        assert log.is_playground
        assert log.sql == "select 1"

    # Since it will be saved on the initial query creation, no need to log it
    def test_creating_query_does_not_save_to_log(self, staff_user, staff_client):
        query = SimpleQueryFactory(created_by_user=staff_user)
        staff_client.post(reverse("explorer:query_create"), model_to_dict(query))
        assert QueryLog.objects.count() == 0

    def test_query_saves_to_log(
        self,
        staff_user,
        staff_client,
    ):
        query = SimpleQueryFactory(created_by_user=staff_user)
        data = model_to_dict(query)
        data["sql"] = "select 12345;"
        data["action"] = "run"
        staff_client.post(reverse("explorer:index") + f"?query_id={query.id}", data)
        assert QueryLog.objects.count() == 1

    def test_user_can_only_see_their_own_queries_on_log_page(self, staff_user, staff_client):
        other_user = UserFactory(email="foo@bar.net")
        QueryLogFactory(sql="select 1234", run_by_user=other_user)
        QueryLogFactory(sql="select 9876", run_by_user=staff_user)

        resp = staff_client.get(reverse("explorer:explorer_logs"))

        assert "select 9876" in resp.content.decode(resp.charset)
        assert "select 1234" not in resp.content.decode(resp.charset)

    def test_is_playground(self):
        assert QueryLog(sql="foo").is_playground is True
        q = SimpleQueryFactory()
        assert QueryLog(sql="foo", query_id=q.id).is_playground is False


@pytest.mark.django_db(transaction=True)
class TestQueryLogEndpoint:
    def test_query_does_not_exist(self, staff_user, staff_client):
        resp = staff_client.get(reverse("explorer:querylog_results", args=(999,)))
        assert resp.status_code == 200
        assert (
            resp.json()["error"] == "Error fetching results. Please try running your query again."
        )

    def test_query_owned_by_other_user(self, staff_user, staff_client):
        QueryLogFactory(sql="select 123", run_by_user=staff_user)
        query_log = QueryLogFactory(
            sql="select 456", run_by_user=UserFactory(email="bob@test.com")
        )
        resp = staff_client.get(reverse("explorer:querylog_results", args=(query_log.id,)))
        assert resp.status_code == 200
        assert (
            resp.json()["error"] == "Error fetching results. Please try running your query again."
        )

    def test_query_running(self, staff_user, staff_client):
        query_log = QueryLogFactory(
            sql="select 123", run_by_user=staff_user, state=QueryLogState.RUNNING
        )
        resp = staff_client.get(reverse("explorer:querylog_results", args=(query_log.id,)))
        assert resp.status_code == 200
        json_response = resp.json()
        assert json_response["query_log_id"] == query_log.id
        assert json_response["state"] == query_log.state
        assert json_response["error"] is None
        assert "Your query is currently being executed by Data Explorer" in json_response["html"]

    def test_query_failed(self, staff_user, staff_client):
        query_log = QueryLogFactory(
            sql="select 123",
            run_by_user=staff_user,
            state=QueryLogState.FAILED,
            error="This is an error message",
        )
        resp = staff_client.get(reverse("explorer:querylog_results", args=(query_log.id,)))
        assert resp.status_code == 200
        json_response = resp.json()
        assert json_response["query_log_id"] == query_log.id
        assert json_response["state"] == query_log.state
        assert json_response["error"] == "This is an error message"
        assert json_response["html"] is None

    def test_query_complete(self, staff_user, staff_client, mocker):
        mock_fetch = mocker.patch("dataworkspace.apps.explorer.views.fetch_query_results")
        mock_fetch.return_value = (
            ["col1", "col2"],
            [[1, "record1"], [2, "record2"]],
            None,
        )
        query_log = QueryLogFactory(
            sql="select 123",
            run_by_user=staff_user,
            state=QueryLogState.COMPLETE,
            rows=100,
        )
        resp = staff_client.get(reverse("explorer:querylog_results", args=(query_log.id,)))
        assert resp.status_code == 200
        json_response = resp.json()
        assert json_response["query_log_id"] == query_log.id
        assert json_response["state"] == query_log.state
        assert json_response["error"] is None
        assert "Showing 2 rows from a total of 100" in json_response["html"]
        assert "record1" in json_response["html"]
        assert "record2" in json_response["html"]


@pytest.mark.django_db
class TestShareQuery:
    @mock.patch("dataworkspace.apps.explorer.views.send_email")
    def test_homepage_redirects(self, mock_send_email, client):
        response = client.post(
            reverse("explorer:index"),
            data={"sql": "select 6870+2;", "action": "share"},
            follow=True,
        )
        assert b"Share Query" in response.content
        assert b"select 6870+2" in response.content
        mock_send_email.assert_not_called()

    @pytest.mark.parametrize(
        "query_param, query_factory",
        (("play_id", PlaygroundSQLFactory), ("query_id", SimpleQueryFactory)),
    )
    @mock.patch("dataworkspace.apps.explorer.views.send_email")
    def test_share_query_too_long(
        self,
        mock_send_email,
        query_param,
        query_factory,
        client,
        user,
    ):
        query_obj = query_factory.create(created_by_user=user)
        response = client.post(
            f"{reverse('explorer:share_query')}?{query_param}={query_obj.id}",
            data={
                "query": "*" * 1951,
                "to_user": user.email,
                "message": "A test message",
            },
        )
        assert (
            b"The character length of your query (1951 characters), is longer "
            b"than the current shared query length limit (1950 characters)."
        ) in response.content
        mock_send_email.assert_not_called()

    @pytest.mark.parametrize(
        "query_param, query_factory",
        (("play_id", PlaygroundSQLFactory), ("query_id", SimpleQueryFactory)),
    )
    @mock.patch("dataworkspace.apps.explorer.views.send_email")
    def test_invalid_recipient(self, mock_send_email, query_param, query_factory, client, user):
        query_obj = query_factory.create(created_by_user=user)
        response = client.post(
            f"{reverse('explorer:share_query')}?{query_param}={query_obj.id}",
            data={
                "query": "select 6870+2;",
                "to_user": "a-bad-email@somewhere.com",
                "message": "A test message",
            },
        )
        assert (
            b"The user you are sharing with must have a DIT staff SSO account" in response.content
        )
        mock_send_email.assert_not_called()

    @pytest.mark.parametrize(
        "query_param, query_factory",
        (("play_id", PlaygroundSQLFactory), ("query_id", SimpleQueryFactory)),
    )
    @mock.patch("dataworkspace.apps.explorer.views.send_email")
    def test_share_query(self, mock_send_email, query_param, query_factory, client, user):
        query_obj = query_factory.create(created_by_user=user)
        response = client.post(
            f"{reverse('explorer:share_query')}?{query_param}={query_obj.id}",
            data={
                "query": "select 6870+2;",
                "to_user": user.email,
                "message": "A test message",
                "copy_sender": False,
            },
            follow=True,
        )
        assert b"Query shared" in response.content
        mock_send_email.assert_has_calls(
            [
                mock.call(
                    settings.NOTIFY_SHARE_EXPLORER_QUERY_TEMPLATE_ID,
                    user.email,
                    personalisation={
                        "message": "A test message",
                        "sharer_first_name": "Frank",
                    },
                )
            ]
        )

    @pytest.mark.parametrize(
        "query_param, query_factory",
        (("play_id", PlaygroundSQLFactory), ("query_id", SimpleQueryFactory)),
    )
    @mock.patch("dataworkspace.apps.explorer.views.send_email")
    def test_share_query_copy_sender(
        self, mock_send_email, query_param, query_factory, client, user, staff_user
    ):
        query_obj = query_factory.create(created_by_user=user)
        response = client.post(
            f"{reverse('explorer:share_query')}?{query_param}={query_obj.id}",
            data={
                "query": "select 6870+2;",
                "to_user": staff_user.email,
                "message": "A test message",
                "copy_sender": True,
            },
            follow=True,
        )
        assert b"Query shared" in response.content
        mock_send_email.assert_has_calls(
            [
                mock.call(
                    settings.NOTIFY_SHARE_EXPLORER_QUERY_TEMPLATE_ID,
                    "bob.testerson@test.com",
                    personalisation={
                        "message": "A test message",
                        "sharer_first_name": "Frank",
                    },
                ),
                mock.call(
                    settings.NOTIFY_SHARE_EXPLORER_QUERY_TEMPLATE_ID,
                    "frank.exampleson@test.com",
                    personalisation={
                        "message": "A test message",
                        "sharer_first_name": "Frank",
                    },
                ),
            ],
            any_order=True,
        )


@pytest.mark.django_db
class TestCreateChart:
    @override_flag(settings.CHART_BUILDER_BUILD_CHARTS_FLAG, active=True)
    def test_create_chart_not_owner(self, staff_user, client):
        query_log = QueryLogFactory.create(run_by_user=staff_user)
        response = client.get(reverse("explorer:create_chart", args=(query_log.id,)))
        assert response.status_code == 403

    @override_flag(settings.CHART_BUILDER_BUILD_CHARTS_FLAG, active=True)
    def test_create_chart(self, staff_user, staff_client):
        query_log = QueryLogFactory(run_by_user=staff_user)
        num_query_logs = QueryLog.objects.count()
        num_charts = ChartBuilderChart.objects.count()
        response = staff_client.get(reverse("explorer:create_chart", args=(query_log.id,)))
        assert QueryLog.objects.count() == num_query_logs + 1
        assert ChartBuilderChart.objects.count() == num_charts + 1
        assert response.status_code == 302
