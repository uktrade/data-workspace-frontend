import logging

from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views import View
from django.views.generic import UpdateView

from dataworkspace.apps.datasets.models import DataSet, DataSetSubscription
from dataworkspace.apps.datasets.subscriptions.forms import DataSetSubscriptionForm
from dataworkspace.apps.datasets.subscriptions.utils import (
    get_or_create_dataset_subscription_for_user,
)

logger = logging.getLogger(__name__)


class DataSetSubscriptionStartView(View):
    def get(self, request, dataset_uuid):
        dataset = get_object_or_404(DataSet, id=dataset_uuid)

        subscription = get_or_create_dataset_subscription_for_user(
            dataset=dataset, user=request.user
        )

        return render(
            request,
            'datasets/subscriptions/step_1_start.html',
            context={'dataset': dataset, 'subscription': subscription},
        )


class DataSetSubscriptionView(UpdateView):
    template_name = 'datasets/subscriptions/step_2_options.html'
    form_class = DataSetSubscriptionForm
    model = DataSetSubscription

    def get_success_url(self):
        return reverse("datasets:subscription_review", args=[self.object.id])


class DataSetSubscriptionReview(UpdateView):
    template_name = 'datasets/subscriptions/step_3_review.html'
    form_class = DataSetSubscriptionForm
    model = DataSetSubscription

    def get_success_url(self):
        return reverse("datasets:subscription_confirm", args=[self.object.id])


class DataSetSubscriptionConfirm(View):
    def get(self, request, subscription_id):
        subscription = get_object_or_404(DataSetSubscription, id=subscription_id)

        return render(
            request,
            'datasets/subscriptions/step_4_confirm.html',
            context={'dataset': subscription.dataset, 'subscription': subscription},
        )
