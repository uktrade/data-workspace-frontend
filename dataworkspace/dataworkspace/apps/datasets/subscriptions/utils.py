import logging

from django.http import Http404
from django.shortcuts import get_object_or_404

from dataworkspace.apps.datasets.models import DataSetSubscription

logger = logging.getLogger(__name__)


def unsubscribe_from_all(user):
    logger.info("unsubscribe from all subscriptions for %s", user)

    subscriptions = DataSetSubscription.objects.active(user=user)
    subscriptions.update(notify_on_data_change=False, notify_on_schema_change=False)

    return subscriptions


def unsubscribe(subscription_id: str, user):
    logger.info("unsubscribe %s from %s", user, subscription_id)

    subscription = get_object_or_404(DataSetSubscription, pk=subscription_id)

    if subscription.user.id != user.id:
        raise Http404()

    subscription.make_inactive()
    subscription.save()

    return subscription


def subscribe(user, dataset):
    try:
        subscription = dataset.subscriptions.get(user=user)
        return subscription
    except DataSetSubscription.DoesNotExist:
        return dataset.subscriptions.create(user=user)
