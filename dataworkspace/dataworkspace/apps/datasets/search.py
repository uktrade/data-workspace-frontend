from django.contrib.postgres.aggregates.general import ArrayAgg, BoolOr
from django.contrib.postgres.search import SearchRank
from django.db.models import (
    Exists,
    F,
    IntegerField,
    Q,
    Value,
    Case,
    When,
    BooleanField,
    OuterRef,
    FilteredRelation,
)
from django.db.models import QuerySet

from dataworkspace.apps.datasets.constants import DataSetType, UserAccessType, TagType
from dataworkspace.apps.datasets.forms import SearchDatasetsFilters
from dataworkspace.apps.datasets.models import (
    ReferenceDataset,
    DataSet,
    DataSetVisualisation,
    VisualisationCatalogueItem,
)
from dataworkspace.apps.datasets.utils import (
    dataset_type_to_manage_unpublished_permission_codename,
)


def _get_datasets_data_for_user_matching_query(
    datasets: QuerySet,
    query,
    id_field,
    user,
):
    #####################################################################
    # Filter out datasets that the user is not allowed to even know about

    visibility_filter = Q(published=True)

    if datasets.model is ReferenceDataset:
        if user.has_perm(
            dataset_type_to_manage_unpublished_permission_codename(DataSetType.REFERENCE)
        ):
            visibility_filter |= Q(published=False)

    if datasets.model is DataSet:
        if user.has_perm(
            dataset_type_to_manage_unpublished_permission_codename(DataSetType.MASTER)
        ):
            visibility_filter |= Q(published=False, type=DataSetType.MASTER)

        if user.has_perm(
            dataset_type_to_manage_unpublished_permission_codename(DataSetType.DATACUT)
        ):
            visibility_filter |= Q(published=False, type=DataSetType.DATACUT)

    if datasets.model is VisualisationCatalogueItem:
        if user.has_perm(
            dataset_type_to_manage_unpublished_permission_codename(DataSetType.VISUALISATION)
        ):
            visibility_filter |= Q(published=False)

    datasets = datasets.filter(visibility_filter)

    #######################################################
    # Filter out datasets that don't match the search terms

    search_filter = Q()

    if datasets.model is DataSet and query:
        search_filter |= Q(sourcetable__table=query)

    if query:
        search_filter |= Q(search_vector=query)

    datasets = datasets.filter(search_filter)

    # Annotate with rank so we can order by this
    datasets = datasets.annotate(search_rank=SearchRank(F("search_vector"), query))

    #########################################################################
    # Annotate datasets for filtering in Python and showing totals in filters

    # has_access

    if datasets.model is ReferenceDataset:
        datasets = datasets.annotate(has_access=Value(True, BooleanField()))

    if datasets.model is DataSet or datasets.model is VisualisationCatalogueItem:
        if datasets.model is DataSet:
            datasets = datasets.annotate(
                user_permission=FilteredRelation(
                    "datasetuserpermission", condition=Q(datasetuserpermission__user=user)
                ),
            )
        if datasets.model is VisualisationCatalogueItem:
            datasets = datasets.annotate(
                user_permission=FilteredRelation(
                    "visualisationuserpermission",
                    condition=Q(visualisationuserpermission__user=user),
                ),
            )
        datasets = datasets.annotate(
            has_access=BoolOr(
                Case(
                    When(
                        Q(
                            user_access_type__in=[
                                UserAccessType.REQUIRES_AUTHENTICATION,
                                UserAccessType.OPEN,
                            ]
                        )
                        | (
                            Q(
                                user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
                                user_permission__user__isnull=False,
                            )
                        )
                        | Q(authorized_email_domains__contains=[user.email.split("@")[1]]),
                        then=True,
                    ),
                    default=False,
                    output_field=BooleanField(),
                )
            ),
        )

    # is_bookmarked

    if datasets.model is ReferenceDataset:
        datasets = datasets.annotate(
            user_bookmark=FilteredRelation(
                "referencedatasetbookmark", condition=Q(referencedatasetbookmark__user=user)
            )
        )
    if datasets.model is DataSet:
        datasets = datasets.annotate(
            user_bookmark=FilteredRelation(
                "datasetbookmark", condition=Q(datasetbookmark__user=user)
            )
        )
    if datasets.model is VisualisationCatalogueItem:
        datasets = datasets.annotate(
            user_bookmark=FilteredRelation(
                "visualisationbookmark", condition=Q(visualisationbookmark__user=user)
            )
        )

    datasets = datasets.annotate(
        is_bookmarked=BoolOr(
            Case(
                When(user_bookmark__user__isnull=False, then=True),
                default=False,
                output_field=BooleanField(),
            )
        ),
    )

    # is_subscribed

    if datasets.model is ReferenceDataset or datasets.model is VisualisationCatalogueItem:
        datasets = datasets.annotate(is_subscribed=Value(False, BooleanField()))

    if datasets.model is DataSet:
        datasets = datasets.annotate(
            user_subscription=FilteredRelation(
                "subscriptions", condition=Q(subscriptions__user=user)
            ),
        )
        datasets = datasets.annotate(
            is_subscribed=BoolOr(
                Case(
                    When(user_subscription__user__isnull=False, then=True),
                    default=False,
                    output_field=BooleanField(),
                )
            )
        )

    # tags

    datasets = datasets.annotate(
        source_tag_ids=ArrayAgg("tags", filter=Q(tags__type=TagType.SOURCE), distinct=True)
    )
    datasets = datasets.annotate(
        topic_tag_ids=ArrayAgg("tags", filter=Q(tags__type=TagType.TOPIC), distinct=True)
    )

    # data_type

    if datasets.model is ReferenceDataset:
        datasets = datasets.annotate(data_type=Value(DataSetType.REFERENCE, IntegerField()))

    if datasets.model is DataSet:
        datasets = datasets.annotate(data_type=F("type"))

    if datasets.model is VisualisationCatalogueItem:
        datasets = datasets.annotate(data_type=Value(DataSetType.VISUALISATION, IntegerField()))

    # is_open_data

    if datasets.model is ReferenceDataset:
        datasets = datasets.annotate(is_open_data=Value(False, BooleanField()))

    if datasets.model is DataSet or datasets.model is VisualisationCatalogueItem:
        datasets = datasets.annotate(
            is_open_data=Case(
                When(user_access_type=UserAccessType.OPEN, then=True),
                default=False,
                output_field=BooleanField(),
            )
        )

    # has_visuals

    if datasets.model is ReferenceDataset or datasets.model is VisualisationCatalogueItem:
        datasets = datasets.annotate(has_visuals=Value(False, BooleanField()))

    if datasets.model is DataSet:
        datasets = datasets.annotate(
            has_visuals=Case(
                When(
                    Exists(DataSetVisualisation.objects.filter(dataset_id=OuterRef("id"))),
                    then=True,
                ),
                default=False,
                output_field=BooleanField(),
            )
        )

    return datasets.values(
        id_field,
        "name",
        "slug",
        "short_description",
        "search_rank",
        "source_tag_ids",
        "topic_tag_ids",
        "data_type",
        "published",
        "published_at",
        "is_open_data",
        "has_visuals",
        "has_access",
        "is_bookmarked",
        "is_subscribed",
    )


def _sorted_datasets_and_visualisations_matching_query_for_user(query, user, sort_by):
    """
    Retrieves all master datasets, datacuts, reference datasets and visualisations (i.e. searchable items)
    and returns them, sorted by incoming sort field, default is desc(search_rank).
    """
    master_and_datacut_datasets = _get_datasets_data_for_user_matching_query(
        DataSet.objects.live(),
        query,
        id_field="id",
        user=user,
    )

    reference_datasets = _get_datasets_data_for_user_matching_query(
        ReferenceDataset.objects.live(),
        query,
        id_field="uuid",
        user=user,
    )

    visualisations = _get_datasets_data_for_user_matching_query(
        VisualisationCatalogueItem.objects.live(), query, id_field="id", user=user
    )

    # Combine all datasets and visualisations and order them.

    sort_fields = sort_by.split(",")

    all_datasets = (
        master_and_datacut_datasets.union(reference_datasets)
        .union(visualisations)
        .order_by(*sort_fields)
    )

    return all_datasets


def search_for_datasets(user, filters: SearchDatasetsFilters, matcher) -> tuple:
    all_datasets_visible_to_user_matching_query = (
        _sorted_datasets_and_visualisations_matching_query_for_user(
            query=filters.query,
            user=user,
            sort_by=filters.sort_type,
        )
    )

    # Filter out any records that don't match the selected filters. We do this in Python, not the DB, because we need
    # to run varied aggregations on the datasets in order to count how many records will be available if users apply
    # additional filters and this was difficult to do in the DB. This process will slowly degrade over time but should
    # be sufficient while the number of datasets is relatively low (hundreds/thousands).
    datasets_matching_query_and_filters = list(
        filter(
            lambda d: matcher(
                d,
                bool(filters.unpublished),
                bool(filters.open_data),
                bool(filters.with_visuals),
                filters.use,
                filters.data_type,
                filters.source_ids,
                filters.topic_ids,
                filters.user_accessible,
                filters.user_inaccessible,
                filters.my_datasets,
            ),
            all_datasets_visible_to_user_matching_query,
        )
    )

    return all_datasets_visible_to_user_matching_query, datasets_matching_query_and_filters
