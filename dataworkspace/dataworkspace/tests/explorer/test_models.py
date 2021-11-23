from unittest.mock import Mock

import pytest
from django.test import TestCase

from dataworkspace.apps.explorer.models import (
    extract_params,
    get_params_for_url,
    shared_dict_update,
    swap_params,
)

from dataworkspace.apps.explorer.utils import (
    EXPLORER_PARAM_TOKEN,
    get_params_from_request,
    param,
)


from dataworkspace.tests.explorer.factories import SimpleQueryFactory, QueryLogFactory


@pytest.mark.django_db(transaction=True)
class TestQueryModel:
    def test_params_get_merged(self):
        q = SimpleQueryFactory(sql="select '$$foo$$';")
        q.params = {"foo": "bar", "mux": "qux"}
        assert q.available_params() == {"foo": "bar"}

    def test_default_params_used(self):
        q = SimpleQueryFactory(sql="select '$$foo:bar$$';")
        assert q.available_params() == {"foo": "bar"}

    def test_get_run_count(self):
        q = SimpleQueryFactory()
        assert q.get_run_count() == 0
        expected = 4
        for _ in range(0, expected):
            QueryLogFactory(query=q)
        assert q.get_run_count() == expected

    def test_avg_duration(self):
        q = SimpleQueryFactory()
        assert q.avg_duration() is None
        QueryLogFactory(query=q, duration=2)
        QueryLogFactory(query=q, duration=3)
        assert q.avg_duration() == 2.5

    def test_final_sql_uses_merged_params(self):
        q = SimpleQueryFactory(sql="select '$$foo:bar$$', '$$qux$$';")
        q.params = {"qux": "mux"}
        expected = "select 'bar', 'mux';"

        assert q.final_sql() == expected


class TestParams(TestCase):
    def test_swappable_params_are_built_correctly(self):
        expected = EXPLORER_PARAM_TOKEN + "foo" + EXPLORER_PARAM_TOKEN
        self.assertEqual(expected, param("foo"))

    def test_params_get_swapped(self):
        sql = "please Swap $$this$$ and $$THat$$"
        expected = "please Swap here and there"
        params = {"this": "here", "that": "there"}
        got = swap_params(sql, params)
        self.assertEqual(got, expected)

    def test_empty_params_does_nothing(self):
        sql = "please swap $$this$$ and $$that$$"
        params = None
        got = swap_params(sql, params)
        self.assertEqual(got, sql)

    def test_non_string_param_gets_swapper(self):
        sql = "please swap $$this$$"
        expected = "please swap 1"
        params = {"this": 1}
        got = swap_params(sql, params)
        self.assertEqual(got, expected)

    def _assertSwap(self, tuple_):
        self.assertEqual(extract_params(tuple_[0]), tuple_[1])

    def test_extracting_params(self):
        tests = [
            ("please swap $$this0$$", {"this0": ""}),
            ("please swap $$THis0$$", {"this0": ""}),
            ("please swap $$this6$$ $$this6:that$$", {"this6": "that"}),
            ("please swap $$this_7:foo, bar$$", {"this_7": "foo, bar"}),
            ("please swap $$this8:$$", {}),
            ("do nothing with $$this1 $$", {}),
            ("do nothing with $$this2 :$$", {}),
            ("do something with $$this3: $$", {"this3": " "}),
            ("do nothing with $$this4: ", {}),
            ("do nothing with $$this5$that$$", {}),
        ]
        for s in tests:
            self._assertSwap(s)

    def test_shared_dict_update(self):
        source = {"foo": 1, "bar": 2}
        target = {"bar": None}  # ha ha!
        self.assertEqual({"bar": 2}, shared_dict_update(target, source))

    def test_get_params_from_url(self):
        r = Mock()
        r.GET = {"params": "foo:bar|qux:mux"}
        res = get_params_from_request(r)
        self.assertEqual(res["foo"], "bar")
        self.assertEqual(res["qux"], "mux")

    def test_get_params_for_request(self):
        q = SimpleQueryFactory(params={"a": 1, "b": 2})
        # For some reason the order of the params is non-deterministic,
        # causing the following to periodically fail:
        #     self.assertEqual(get_params_for_url(q), 'a:1|b:2')
        # So instead we go for the following, convoluted, asserts:
        res = get_params_for_url(q)
        res = res.split("|")
        expected = ["a:1", "b:2"]
        for e in expected:
            self.assertIn(e, res)

    def test_get_params_for_request_empty(self):
        q = SimpleQueryFactory()
        self.assertEqual(get_params_for_url(q), None)
