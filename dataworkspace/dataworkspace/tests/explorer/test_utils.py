from unittest.mock import Mock

from django.test import TestCase

from dataworkspace.tests.explorer.factories import SimpleQueryFactory
from dataworkspace.apps.explorer.utils import (
    EXPLORER_PARAM_TOKEN,
    extract_params,
    get_params_for_url,
    get_params_from_request,
    get_total_pages,
    param,
    shared_dict_update,
    swap_params,
)


class TestParams(TestCase):
    def test_swappable_params_are_built_correctly(self):
        expected = EXPLORER_PARAM_TOKEN + 'foo' + EXPLORER_PARAM_TOKEN
        self.assertEqual(expected, param('foo'))

    def test_params_get_swapped(self):
        sql = 'please Swap $$this$$ and $$THat$$'
        expected = 'please Swap here and there'
        params = {'this': 'here', 'that': 'there'}
        got = swap_params(sql, params)
        self.assertEqual(got, expected)

    def test_empty_params_does_nothing(self):
        sql = 'please swap $$this$$ and $$that$$'
        params = None
        got = swap_params(sql, params)
        self.assertEqual(got, sql)

    def test_non_string_param_gets_swapper(self):
        sql = 'please swap $$this$$'
        expected = 'please swap 1'
        params = {'this': 1}
        got = swap_params(sql, params)
        self.assertEqual(got, expected)

    def _assertSwap(self, tuple_):
        self.assertEqual(extract_params(tuple_[0]), tuple_[1])

    def test_extracting_params(self):
        tests = [
            ('please swap $$this0$$', {'this0': ''}),
            ('please swap $$THis0$$', {'this0': ''}),
            ('please swap $$this6$$ $$this6:that$$', {'this6': 'that'}),
            ('please swap $$this_7:foo, bar$$', {'this_7': 'foo, bar'}),
            ('please swap $$this8:$$', {}),
            ('do nothing with $$this1 $$', {}),
            ('do nothing with $$this2 :$$', {}),
            ('do something with $$this3: $$', {'this3': ' '}),
            ('do nothing with $$this4: ', {}),
            ('do nothing with $$this5$that$$', {}),
        ]
        for s in tests:
            self._assertSwap(s)

    def test_shared_dict_update(self):
        source = {'foo': 1, 'bar': 2}
        target = {'bar': None}  # ha ha!
        self.assertEqual({'bar': 2}, shared_dict_update(target, source))

    def test_get_params_from_url(self):
        r = Mock()
        r.GET = {'params': 'foo:bar|qux:mux'}
        res = get_params_from_request(r)
        self.assertEqual(res['foo'], 'bar')
        self.assertEqual(res['qux'], 'mux')

    def test_get_params_for_request(self):
        q = SimpleQueryFactory(params={'a': 1, 'b': 2})
        # For some reason the order of the params is non-deterministic,
        # causing the following to periodically fail:
        #     self.assertEqual(get_params_for_url(q), 'a:1|b:2')
        # So instead we go for the following, convoluted, asserts:
        res = get_params_for_url(q)
        res = res.split('|')
        expected = ['a:1', 'b:2']
        for e in expected:
            self.assertIn(e, res)

    def test_get_params_for_request_empty(self):
        q = SimpleQueryFactory()
        self.assertEqual(get_params_for_url(q), None)


class TestConnections(TestCase):
    def test_only_registered_connections_are_in_connections(self):
        from dataworkspace.apps.explorer.connections import (  # pylint: disable=import-outside-toplevel
            connections,
        )
        from dataworkspace.apps.explorer.app_settings import (  # pylint: disable=import-outside-toplevel
            EXPLORER_DEFAULT_CONNECTION,
        )
        from django.db import (  # pylint: disable=import-outside-toplevel
            connections as djcs,
        )

        self.assertTrue(EXPLORER_DEFAULT_CONNECTION in connections)
        self.assertNotEqual(
            len(connections),
            len([_ for _ in djcs]),  # pylint: disable=unnecessary-comprehension
        )


class TestGetTotalPages(TestCase):
    def test_get_total_pages(self):
        tests = [
            (None, 10, 1),
            (10, None, 1),
            (80, 10, 8),
            (80, 5, 16),
            (81, 10, 9),
            (79, 10, 8),
        ]
        for total_rows, page_size, expected_total_pages in tests:
            actual_result = get_total_pages(total_rows, page_size)
            self.assertEqual(
                actual_result,
                expected_total_pages,
                msg=f'Total rows {total_rows}, Page size {page_size}',
            )
