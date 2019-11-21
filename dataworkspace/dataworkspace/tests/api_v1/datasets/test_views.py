from django.test import TestCase
from django.urls import resolve


class TestAPIDatasetView(TestCase):

    url = '/api/v1/dataset/future-interest-countries/table-id'

    def test_route(self):
        resolver = resolve(self.url)
        self.assertEqual(
            resolver.view_name, 'api-v1:dataset:api-dataset-view'
        )

    def test_data(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_unauthorised_dataset(self):
        url = '/api/v1/dataset/restricted-dataset/table-id'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
