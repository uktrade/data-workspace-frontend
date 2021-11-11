from django.shortcuts import get_object_or_404, render
from django.views import View
from django.views.generic import UpdateView

from dataworkspace.apps.datasets.models import DataSet


def get_or_create_dataset_subscription_for_user(dataset, user):
    subscription = dataset.datasetsubscription_set.filter(user=user)
    if not subscription.exists():
        subscription = dataset.datasetsubscription_set.create(user=user)

    return subscription


class DataSetSubscriptionStartView(UpdateView):
    def get(self, request, dataset_uuid):
        dataset = get_object_or_404(DataSet, id=dataset_uuid)

        subscription = get_or_create_dataset_subscription_for_user(dataset=dataset, user=request.user)

        return render(request, 'datasets/subscriptions/step_1_start.html', context={
            'dataset': dataset,
            'subscription': subscription
        })


class DataSetSubscriptionView(View):
    def get(self, request, dataset_uuid):
        dataset = get_object_or_404(DataSet, id=dataset_uuid)

        subscription = get_or_create_dataset_subscription_for_user(dataset=dataset, user=request.user)

        return render(request, 'datasets/subscriptions/step_2_options.html', context={
            'dataset': dataset,
            'subscription': subscription
        })


class DataSetSubscriptionReview(View):
    def get(self, request, dataset_uuid):
        dataset = get_object_or_404(DataSet, id=dataset_uuid)

        subscription = get_or_create_dataset_subscription_for_user(dataset=dataset, user=request.user)

        return render(request, 'datasets/subscriptions/step_3_review.html', context={
            'dataset': dataset,
            'subscription': subscription
        })


class DataSetSubscriptionConfirm(View):
    def get(self, request, dataset_uuid):
        dataset = get_object_or_404(DataSet, id=dataset_uuid)

        subscription = get_or_create_dataset_subscription_for_user(dataset=dataset, user=request.user)

        return render(request, 'datasets/subscriptions/step_4_confirm.html', context={
            'dataset': dataset,
            'subscription': subscription
        })
