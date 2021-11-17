from dataworkspace.apps.datasets.models import DataSet, DataSetSubscription


def get_or_create_dataset_subscription_for_user(
    dataset: DataSet, user
) -> DataSetSubscription:
    subscription = dataset.datasetsubscription_set.filter(user=user)
    if subscription.exists():
        return subscription.first()

    subscription = dataset.datasetsubscription_set.create(user=user)
    return subscription
