from django.test import TestCase
from django.urls import resolve


class TestFutureInterestCountriesDataset(TestCase):

    url = '/api/v1/dataset/future-interest-countries'

    def test_route(self):
        resolver = resolve(self.url)
        print(dir(resolver.func))
        self.assertEqual(
            resolver.view_name, 'api-v1:dataset:future-interest-countries'
        )
