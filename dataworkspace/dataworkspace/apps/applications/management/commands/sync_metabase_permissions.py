from itertools import groupby

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from dataworkspace.apps.datasets.models import MasterDataset


def deepupdate(d, u):
    for k, v in u.items():
        if isinstance(v, dict):
            d[k] = deepupdate(d.get(k, {}), v)
        else:
            d[k] = v
    return d


class MetabaseClient:
    def __init__(self):
        self.token = self._get_auth_token()

    def _request(self, method, path, params=None, json=None):
        return requests.request(
            method,
            f"{settings.METABASE_ROOT.rstrip('/')}/api/{path.strip('/')}",
            params=params,
            json=json,
            headers={"X-Metabase-Session": self.token},
        )

    def _get_auth_token(self):
        return requests.post(
            f"{settings.METABASE_ROOT.rstrip('/')}/api/session",
            json={
                "username": settings.METABASE_BOT_USER_EMAIL,
                "password": settings.METABASE_BOT_USER_PASSWORD,
            },
        ).json()["id"]

    def get_tables(self):
        return self._request("GET", "table").json()

    def get_groups(self):
        return self._request("GET", "permissions/group").json()

    def get_users(self):
        return self._request("GET", "user").json()

    def get_group_membership(self):
        return self._request("GET", "permissions/membership").json()

    def get_group_permissions(self):
        return self._request("GET", "permissions/graph").json()

    def create_group(self, group_name):
        return self._request(
            "POST", "permissions/group", json={"name": group_name}
        ).json()

    def delete_group(self, group_id):
        return self._request("DELETE", f"permissions/group/{group_id}")

    def create_group_membership(self, group_id, user_id):
        return self._request(
            "POST",
            "permissions/membership",
            json={"group_id": group_id, "user_id": user_id},
        ).json()

    def delete_group_membership(self, membership_id):
        return self._request("DELETE", f"permissions/membership/{membership_id}")

    def update_group_permissions(self, graph):
        return self._request("PUT", "permissions/graph", json=graph).json()

    def update_user(self, user_id, groups=None):
        return self._request(
            "PUT", f"user/{user_id}", json={"id": user_id, "group_ids": groups}
        )

    def update_table(self, table_id, visible=False):
        return self._request(
            "PUT",
            f"table/{table_id}",
            json={
                "id": table_id,
                "display_name": None,
                "entity_type": None,
                "visibility_type": None if visible else "hidden",
                "description": None,
                "caveats": None,
                "points_of_interest": None,
                "show_in_getting_started": None,
            },
        )


class Command(BaseCommand):
    def _get_sourcetable_mapping(self, datasets, metabase_tables):
        metabase_tables = {
            (t["db"]["name"], t["schema"], t["name"]): (
                t["db_id"],
                t["schema"],
                t["id"],
                t["visibility_type"],
            )
            for t in metabase_tables
        }

        mapping = {}

        sourcetables = set(
            table for dataset in datasets for table in dataset.sourcetable_set.all()
        )

        for table in sourcetables:
            key = (table.database.memorable_name, table.schema, table.table)
            if key in metabase_tables:
                mapping[table.id] = metabase_tables[key][:3]
            else:
                self.stderr.write(
                    f"   Table {table.schema}.{table.table} doesn't exist in Metabase, database sync might be required"
                )

        unmatched_table_ids = set(
            t[2] for t in metabase_tables.values() if t[3] != "hidden"
        ) - set(t[2] for t in mapping.values())

        return mapping, unmatched_table_ids

    def _create_metabase_groups(self, metabase, datasets):
        existing_groups = {
            group["name"]: group["id"]
            for group in metabase.get_groups()
            if group["id"] > 2  # exclude built-in Metabase groups
        }

        mapping = {}

        for dataset in datasets:
            if dataset.user_access_type == "REQUIRES_AUTHENTICATION":
                continue
            key = f"{dataset.name} [{dataset.id}]"
            if key not in existing_groups:
                self.stdout.write(f"   Creating Metabase group for {key}")
                mapping[dataset.id] = metabase.create_group(key)["id"]
            else:
                self.stdout.write(f"   Found existing Metabase group {key}")
                mapping[dataset.id] = existing_groups[key]

        return mapping, set(existing_groups.values()) - set(mapping.values())

    def _update_metabase_permission_graph(
        self, metabase, datasets, group_mapping, table_mapping
    ):
        graph = metabase.get_group_permissions()

        for dataset in datasets:
            table_permissions = {}
            for table in dataset.sourcetable_set.all():
                if table.id not in table_mapping:
                    self.stderr.write(
                        f"   Cannot assign permissions for missing table {table.schema}.{table.table}"
                    )
                    continue
                db_id, schema, table_id = table_mapping[table.id]
                if db_id not in table_permissions:
                    table_permissions[db_id] = {"schemas": {}}
                if schema not in table_permissions[db_id]["schemas"]:
                    table_permissions[db_id]["schemas"][schema] = {}
                table_permissions[db_id]["schemas"][schema][table_id] = "all"

            if dataset.user_access_type == 'REQUIRES_AUTHORIZATION':
                graph["groups"][group_mapping[dataset.id]] = table_permissions
            else:
                # Give table permissions to 'All users' instead of dataset group
                graph["groups"]["1"] = deepupdate(
                    graph["groups"].get("1", {}), table_permissions
                )

        return metabase.update_group_permissions(graph)

    def _update_metabase_group_membership(self, metabase, datasets, group_mapping):
        metabase_users = {
            user["email"]: (user["id"], set(g for g in user["group_ids"] if g > 2))
            for user in metabase.get_users()
        }

        metabase_memberships = {
            (m["group_id"], m["user_id"]): m["membership_id"]
            for memberships in metabase.get_group_membership().values()
            for m in memberships
            if m["group_id"] > 2  # exclude built-in Metabase groups
        }

        user_datasets = [
            (permission.user.email, group_mapping[dataset.id])
            for dataset in datasets
            for permission in dataset.datasetuserpermission_set.all()
            if dataset.user_access_type == "REQUIRES_AUTHORIZATION"
            and permission.user.email in metabase_users
        ]

        for email, permissions in groupby(user_datasets, key=lambda x: x[0]):
            group_ids = set(permission[1] for permission in permissions)

            user_id, existing_groups = metabase_users[email]

            for group in group_ids - existing_groups:
                self.stdout.write(f"   Adding Metabase user {user_id} to group {group}")
                metabase.create_group_membership(group, user_id)

            for group in existing_groups - group_ids:
                self.stdout.write(
                    f"   Removing Metabase user {user_id} from group {group}"
                )
                metabase.delete_group_membership(metabase_memberships[(group, user_id)])

    def _delete_unmatched_groups(self, metabase, group_ids):
        for group in group_ids:
            self.stdout.write(f"   Deleting Metabase group {group}")
            metabase.delete_group(group)

    def _hide_unmatched_tables(self, metabase, unmatched_table_ids):
        for table in unmatched_table_ids:
            self.stdout.write(f"   Hiding Metabase table {table}")
            metabase.update_table(table, visible=False)

    def handle(self, *args, **options):
        metabase = MetabaseClient()

        datasets = (
            MasterDataset.objects.live()
            .filter(published=True)
            .prefetch_related(
                "sourcetable_set__database", "datasetuserpermission_set__user"
            )
            .all()
        )
        self.stdout.write(
            "-> Creatng Metabase user groups for published master datasets"
        )
        group_mapping, unmatched_group_ids = self._create_metabase_groups(
            metabase, datasets
        )

        self.stdout.write(
            "-> Mapping master dataset source tables to Metabase table ids"
        )
        table_mapping, unmatched_table_ids = self._get_sourcetable_mapping(
            datasets, metabase.get_tables()
        )

        self.stdout.write("-> Updating Metabase dataset access permissions graph")
        self._update_metabase_permission_graph(
            metabase, datasets, group_mapping, table_mapping
        )

        self.stdout.write("-> Updating Metabase group membership")
        self._update_metabase_group_membership(metabase, datasets, group_mapping)

        self.stdout.write("-> Deleting Metabase groups not matching a master dataset")
        self._delete_unmatched_groups(metabase, unmatched_group_ids)

        self.stdout.write("-> Hiding Metabase tables not connected to a master dataset")
        self._hide_unmatched_tables(metabase, unmatched_table_ids)

        return "-> Done"
