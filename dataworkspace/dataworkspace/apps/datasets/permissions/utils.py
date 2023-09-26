from django.contrib.auth import get_user_model

from dataworkspace.apps.api_v1.core.views import (
    invalidate_superset_user_cached_credentials,
    remove_superset_user_cached_credentials,
)
from dataworkspace.apps.applications.utils import sync_quicksight_permissions
from dataworkspace.apps.core.utils import clear_table_permissions_cache_for_user
from dataworkspace.apps.datasets.models import DataSetUserPermission, VisualisationUserPermission
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.eventlog.utils import log_permission_change
from dataworkspace.apps.explorer.schema import clear_schema_info_cache_for_user
from dataworkspace.apps.explorer.utils import (
    invalidate_data_explorer_user_cached_credentials,
    remove_data_explorer_user_cached_credentials,
)


def process_dataset_authorized_users_change(
    authorized_users,
    request_user,
    dataset,
    access_type_changed,
    authorized_email_domains_changed,
    is_master_dataset,
):
    current_authorized_users = set(
        get_user_model().objects.filter(datasetuserpermission__dataset=dataset)
    )

    changed_users = set()

    for user in authorized_users - current_authorized_users:
        DataSetUserPermission.objects.create(dataset=dataset, user=user)
        log_permission_change(
            request_user,
            dataset,
            EventLog.TYPE_GRANTED_DATASET_PERMISSION,
            {"for_user_id": user.id},
            f"Added dataset {dataset} permission",
        )
        changed_users.add(user)
        clear_schema_info_cache_for_user(user)
        clear_table_permissions_cache_for_user(user)

    for user in current_authorized_users - authorized_users:
        DataSetUserPermission.objects.filter(dataset=dataset, user=user).delete()
        log_permission_change(
            request_user,
            dataset,
            EventLog.TYPE_REVOKED_DATASET_PERMISSION,
            {"for_user_id": user.id},
            f"Removed dataset {dataset} permission",
        )
        changed_users.add(user)
        clear_schema_info_cache_for_user(user)
        clear_table_permissions_cache_for_user(user)

    if access_type_changed or authorized_email_domains_changed:
        log_permission_change(
            request_user,
            dataset,
            EventLog.TYPE_SET_DATASET_USER_ACCESS_TYPE
            if access_type_changed
            else EventLog.TYPE_CHANGED_AUTHORIZED_EMAIL_DOMAIN,
            {"access_type": dataset.user_access_type},
            f"user_access_type set to {dataset.user_access_type}",
        )

        # As the dataset's access type has changed, clear cached credentials for all
        # users to ensure they either:
        #   - lose access if it went from REQUIRES_AUTHENTICATION/OPEN to REQUIRES_AUTHORIZATION
        #   - get access if it went from REQUIRES_AUTHORIZATION to REQUIRES_AUTHENTICATION/OPEN
        invalidate_data_explorer_user_cached_credentials()
        invalidate_superset_user_cached_credentials()
    else:
        for user in changed_users:
            remove_data_explorer_user_cached_credentials(user)
            remove_superset_user_cached_credentials(user)
            clear_table_permissions_cache_for_user(user)

    if is_master_dataset:
        if changed_users:
            # If we're changing permissions for loads of users, let's just do a full quicksight re-sync.
            # Makes fewer AWS calls and probably completes as quickly if not quicker.
            if len(changed_users) >= 50:
                sync_quicksight_permissions.delay()
            else:
                changed_user_sso_ids = [str(u.profile.sso_id) for u in changed_users]
                sync_quicksight_permissions.delay(
                    user_sso_ids_to_update=tuple(changed_user_sso_ids)
                )
        elif access_type_changed:
            sync_quicksight_permissions.delay()


def process_visualisation_catalogue_item_authorized_users_change(
    authorized_users,
    request_user,
    visualisation_catalogue_item,
    access_type_changed,
    authorized_email_domains_changed,
):
    current_authorized_users = set(
        get_user_model().objects.filter(
            visualisationuserpermission__visualisation=visualisation_catalogue_item
        )
    )

    changed_users = set()

    for user in authorized_users - current_authorized_users:
        VisualisationUserPermission.objects.create(
            visualisation=visualisation_catalogue_item, user=user
        )
        log_permission_change(
            request_user,
            visualisation_catalogue_item,
            EventLog.TYPE_GRANTED_VISUALISATION_PERMISSION,
            {"for_user_id": user.id},
            f"Added visualisation {visualisation_catalogue_item} permission",
        )
        changed_users.add(user)

    for user in current_authorized_users - authorized_users:
        VisualisationUserPermission.objects.filter(
            visualisation=visualisation_catalogue_item, user=user
        ).delete()
        log_permission_change(
            request_user,
            visualisation_catalogue_item,
            EventLog.TYPE_REVOKED_VISUALISATION_PERMISSION,
            {"for_user_id": user.id},
            f"Removed visualisation {visualisation_catalogue_item} permission",
        )
        changed_users.add(user)

    if access_type_changed or authorized_email_domains_changed:
        log_permission_change(
            request_user,
            visualisation_catalogue_item,
            EventLog.TYPE_SET_DATASET_USER_ACCESS_TYPE
            if access_type_changed
            else EventLog.TYPE_CHANGED_AUTHORIZED_EMAIL_DOMAIN,
            {"access_type": visualisation_catalogue_item.user_access_type},
            f"user_access_type set to {visualisation_catalogue_item.user_access_type}",
        )

        # As the visualisation's access type has changed, clear cached credentials for all
        # users to ensure they either:
        #   - lose access if it went from REQUIRES_AUTHENTICATION/OPEN to REQUIRES_AUTHORIZATION
        #   - get access if it went from REQUIRES_AUTHORIZATION to REQUIRES_AUTHENTICATION/OPEN
        invalidate_superset_user_cached_credentials()
    else:
        for user in changed_users:
            remove_superset_user_cached_credentials(user)
