from django.contrib.postgres.aggregates.general import ArrayAgg, BoolOr
from django.contrib.postgres.fields import ArrayField
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
    CharField,
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


def _get_visualisations_data_for_user_matching_query(visualisations: QuerySet, query, user=None):
    """
    Filters the visualisation queryset for:
        1) visibility (whether the user can know if the visualisation exists)
        2) matches the search terms

    Annotates the visualisation queryset with:
        1) `has_access`, if the user can use the visualisation.
    """
    # Filter out visualisations that the user is not allowed to even know about.
    if not (
        user
        and user.has_perm(
            dataset_type_to_manage_unpublished_permission_codename(DataSetType.VISUALISATION)
        )
    ):
        visualisations = visualisations.filter(published=True)

    # Filter out visualisations that don't match the search terms

    visualisations = visualisations.annotate(search_rank=SearchRank(F("search_vector"), query))

    if query:
        visualisations = visualisations.filter(search_vector=query)

    # Mark up whether the user can access the visualisation.
    if user:
        user_email_domain = user.email.split("@")[1]
        access_filter = (
            (
                (
                    Q(
                        user_access_type__in=[
                            UserAccessType.REQUIRES_AUTHENTICATION,
                            UserAccessType.OPEN,
                        ]
                    )
                )
                & (
                    Q(visualisationuserpermission__user=user)
                    | Q(visualisationuserpermission__isnull=True)
                )
            )
            | Q(
                user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
                visualisationuserpermission__user=user,
            )
            | Q(authorized_email_domains__contains=[user_email_domain])
        )

    else:
        access_filter = Q()

    visualisations = visualisations.annotate(
        _has_access=Case(
            When(access_filter, then=True),
            default=False,
            output_field=BooleanField(),
        )
        if access_filter
        else Value(True, BooleanField()),
    )

    bookmark_filter = Q(visualisationbookmark__user=user)
    visualisations = visualisations.annotate(
        _is_bookmarked=Case(
            When(bookmark_filter, then=True),
            default=False,
            output_field=BooleanField(),
        )
        if bookmark_filter
        else Value(False, BooleanField()),
    )

    # can't currently subscribe to visualisations
    visualisations = visualisations.annotate(_is_subscribed=Value(False, BooleanField()))

    # Pull in the source tag IDs for the dataset
    visualisations = visualisations.annotate(
        source_tag_ids=ArrayAgg("tags", filter=Q(tags__type=TagType.SOURCE), distinct=True)
    )

    visualisations = visualisations.annotate(
        source_tag_names=ArrayAgg("tags__name", filter=Q(tags__type=TagType.SOURCE), distinct=True)
    )

    # Pull in the topic tag IDs for the dataset
    visualisations = visualisations.annotate(
        topic_tag_ids=ArrayAgg("tags", filter=Q(tags__type=TagType.TOPIC), distinct=True)
    )

    visualisations = visualisations.annotate(
        topic_tag_names=ArrayAgg("tags__name", filter=Q(tags__type=TagType.TOPIC), distinct=True)
    )

    visualisations = visualisations.annotate(
        # Define a `purpose` column denoting the dataset type
        purpose=Value(DataSetType.VISUALISATION, IntegerField()),
        data_type=Value(DataSetType.VISUALISATION, IntegerField()),
        is_open_data=Case(
            When(user_access_type=UserAccessType.OPEN, then=True),
            default=False,
            output_field=BooleanField(),
        ),
        has_visuals=Value(False, BooleanField()),
    )

    # We are joining on the user permissions table to determine `_has_access`` to the visualisation, so we need to
    # group them and remove duplicates. We aggregate all the `_has_access` fields together and return true if any
    # of the records say that access is available.
    visualisations = (
        visualisations.values(
            "id",
            "name",
            "slug",
            "short_description",
            "search_rank",
            "source_tag_names",
            "source_tag_ids",
            "topic_tag_names",
            "topic_tag_ids",
            "purpose",
            "data_type",
            "published",
            "published_at",
            "is_open_data",
            "has_visuals",
            "eligibility_criteria",
        )
        .annotate(has_access=BoolOr("_has_access"))
        .annotate(is_bookmarked=BoolOr("_is_bookmarked"))
        .annotate(is_subscribed=BoolOr("_is_subscribed"))
    )

    return visualisations.values(
        "id",
        "name",
        "slug",
        "short_description",
        "search_rank",
        "source_tag_names",
        "source_tag_ids",
        "topic_tag_names",
        "topic_tag_ids",
        "purpose",
        "data_type",
        "published",
        "published_at",
        "is_open_data",
        "has_visuals",
        "eligibility_criteria",
        "has_access",
        "is_bookmarked",
        "is_subscribed",
    )


def _get_datasets_data_for_user_matching_query(
    datasets: QuerySet,
    query,
    data_type=None,
    user=None,
    id_field="id",
):
    is_reference_query = datasets.model is ReferenceDataset

    visibility_filter = Q(published=True)

    if user:
        if is_reference_query:
            reference_type = DataSetType.REFERENCE
            reference_perm = dataset_type_to_manage_unpublished_permission_codename(reference_type)

            if user.has_perm(reference_perm):
                visibility_filter |= Q(published=False)

            datasets = datasets.annotate(
                eligibility_criteria=Value(None, ArrayField(CharField(max_length=20)))
            )

        if datasets.model is DataSet:
            master_type, datacut_type = (
                DataSetType.MASTER,
                DataSetType.DATACUT,
            )
            master_perm = dataset_type_to_manage_unpublished_permission_codename(master_type)
            datacut_perm = dataset_type_to_manage_unpublished_permission_codename(datacut_type)

            if user.has_perm(master_perm):
                visibility_filter |= Q(published=False, type=master_type)

            if user.has_perm(datacut_perm):
                visibility_filter |= Q(published=False, type=datacut_type)

    datasets = datasets.filter(visibility_filter)

    # Filter out datasets that don't match the search terms
    datasets = datasets.annotate(search_rank=SearchRank(F("search_vector"), query))

    if query:
        source_table_match = Q()
        if datasets.model is DataSet:
            source_table_match = Q(sourcetable__table=query)
        datasets = datasets.filter(source_table_match | Q(search_vector=query))

    # Mark up whether the user can access the data in the dataset.
    access_filter = Q()
    bookmark_filter = Q(referencedatasetbookmark__user=user)

    if user and datasets.model is not ReferenceDataset:
        user_email_domain = user.email.split("@")[1]
        access_filter &= (
            Q(
                user_access_type__in=[
                    UserAccessType.REQUIRES_AUTHENTICATION,
                    UserAccessType.OPEN,
                ]
            )
            | Q(
                user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
                datasetuserpermission__user=user,
            )
            | Q(authorized_email_domains__contains=[user_email_domain])
        )

        bookmark_filter = Q(datasetbookmark__user=user)

    datasets = datasets.annotate(
        _has_access=Case(
            When(access_filter, then=True),
            default=False,
            output_field=BooleanField(),
        )
        if access_filter
        else Value(True, BooleanField()),
    )

    datasets = datasets.annotate(
        _is_bookmarked=Case(
            When(bookmark_filter, then=True),
            default=False,
            output_field=BooleanField(),
        )
        if bookmark_filter
        else Value(False, BooleanField()),
    )

    subscription_filter = Q(subscriptions__user=user)

    datasets = datasets.annotate(
        _is_subscribed=Case(
            When(subscription_filter, then=True), default=False, output_field=BooleanField()
        )
        if subscription_filter and datasets.model is not ReferenceDataset
        else Value(False, BooleanField())
    )

    # Pull in the source tag IDs for the dataset
    datasets = datasets.annotate(
        source_tag_ids=ArrayAgg("tags", filter=Q(tags__type=TagType.SOURCE), distinct=True)
    )
    datasets = datasets.annotate(
        source_tag_names=ArrayAgg("tags__name", filter=Q(tags__type=TagType.SOURCE), distinct=True)
    )

    # Pull in the topic tag IDs for the dataset
    datasets = datasets.annotate(
        topic_tag_ids=ArrayAgg("tags", filter=Q(tags__type=TagType.TOPIC), distinct=True)
    )
    datasets = datasets.annotate(
        topic_tag_names=ArrayAgg("tags__name", filter=Q(tags__type=TagType.TOPIC), distinct=True)
    )

    # Define a `purpose` column denoting the dataset type.
    if is_reference_query:
        datasets = datasets.annotate(
            purpose=Value(DataSetType.DATACUT, IntegerField()),
            data_type=Value(DataSetType.REFERENCE, IntegerField()),
            is_open_data=Value(False, BooleanField()),
            has_visuals=Value(False, BooleanField()),
        )
    else:
        dataset_visual_filter = DataSetVisualisation.objects.filter(dataset_id=OuterRef("id"))
        datasets = datasets.annotate(
            purpose=F("type"),
            data_type=F("type"),
            is_open_data=Case(
                When(user_access_type=UserAccessType.OPEN, then=True),
                default=False,
                output_field=BooleanField(),
            ),
            has_visuals=Case(
                When(Exists(dataset_visual_filter), then=True),
                default=False,
                output_field=BooleanField(),
            ),
        )

    # We are joining on the user permissions table to determine `_has_access`` to the dataset, so we need to
    # group them and remove duplicates. We aggregate all the `_has_access` fields together and return true if any
    # of the records say that access is available.
    datasets = (
        datasets.values(
            id_field,
            "name",
            "slug",
            "short_description",
            "search_rank",
            "source_tag_names",
            "source_tag_ids",
            "topic_tag_names",
            "topic_tag_ids",
            "purpose",
            "data_type",
            "published",
            "published_at",
            "is_open_data",
            "has_visuals",
            "eligibility_criteria",
        )
        .annotate(has_access=BoolOr("_has_access"))
        .annotate(is_bookmarked=BoolOr("_is_bookmarked"))
        .annotate(is_subscribed=BoolOr("_is_subscribed"))
    )

    return datasets.values(
        id_field,
        "name",
        "slug",
        "short_description",
        "search_rank",
        "source_tag_names",
        "source_tag_ids",
        "topic_tag_names",
        "topic_tag_ids",
        "purpose",
        "data_type",
        "published",
        "published_at",
        "is_open_data",
        "has_visuals",
        "eligibility_criteria",
        "has_access",
        "is_bookmarked",
        "is_subscribed",
    )


def _sorted_datasets_and_visualisations_matching_query_for_user(query, data_type, user, sort_by):
    """
    Retrieves all master datasets, datacuts, reference datasets and visualisations (i.e. searchable items)
    and returns them, sorted by incoming sort field, default is desc(search_rank).
    """
    master_and_datacut_datasets = _get_datasets_data_for_user_matching_query(
        DataSet.objects.live(), query, data_type, user=user, id_field="id"
    )

    reference_datasets = _get_datasets_data_for_user_matching_query(
        ReferenceDataset.objects.live(),
        query,
        user=user,
        id_field="uuid",
    )

    visualisations = _get_visualisations_data_for_user_matching_query(
        VisualisationCatalogueItem.objects.live(), query, user=user
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
            data_type=filters.data_type,
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
