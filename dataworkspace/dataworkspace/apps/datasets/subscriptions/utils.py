import logging

from django.http import Http404
from django.shortcuts import get_object_or_404

from dataworkspace.apps.datasets.models import DataSet, DataSetSubscription

logger = logging.getLogger(__name__)


def get_or_create_dataset_subscription_for_user(
    dataset: DataSet, user
) -> DataSetSubscription:
    subscription = dataset.datasetsubscription_set.filter(user=user)
    if subscription.exists():
        return subscription.first()

    subscription = dataset.datasetsubscription_set.create(user=user)
    return subscription


def unsubscribe_from_all(user):
    logger.info("unsubscribe from all subscriptions for %s", user)

    subscriptions = DataSetSubscription.objects.active(user=user)

    subscriptions.update(notify_on_data_change=False, notify_on_schema_change=False)

    # for subscription in subscriptions:
    #     subscription.make_inactive()
    #
    # DataSetSubscription.objects.bulk_update(
    #     subscriptions, ["notify_on_data_change", "notify_on_schema_change"]
    # )

    return subscriptions


def unsubscribe(subscription_id: str, user):
    logger.info("unsubscribe %s from %s", user, subscription_id)

    subscription = get_object_or_404(DataSetSubscription, pk=subscription_id)

    if subscription.user.id != user.id:
        raise Http404()

    subscription.make_inactive()
    subscription.save()

    return subscription
