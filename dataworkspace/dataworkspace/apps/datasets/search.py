import logging
from datetime import datetime, time, timedelta

import waffle

from django.conf import settings
from django.contrib.postgres.aggregates.general import ArrayAgg, BoolOr
from django.contrib.postgres.search import SearchRank, SearchQuery
from django.core.cache import cache
from django.db.models import (
    Count,
    Exists,
    F,
    CharField,
    IntegerField,
    FloatField,
    Q,
    Sum,
    Value,
    Case,
    When,
    BooleanField,
    OuterRef,
    FilteredRelation,
)
from django.db.models import QuerySet
from django.db.models.functions import Lower
from django.db.models.fields.json import KeyTextTransform
from django.http import JsonResponse
from pytz import utc
import redis

from dataworkspace.apps.core.utils import close_all_connections_if_not_in_atomic_block
from dataworkspace.apps.datasets.constants import DataSetType, UserAccessType, TagType
from dataworkspace.apps.datasets.models import (
    ReferenceDataset,
    DataSet,
    DataSetVisualisation,
    VisualisationCatalogueItem,
    ToolQueryAuditLog,
)
from dataworkspace.apps.datasets.utils import (
    dataset_type_to_manage_unpublished_permission_codename,
)
from dataworkspace.apps.eventlog.models import EventLog

from dataworkspace.cel import celery_app

logger = logging.getLogger("app")


SORT_FIELD_MAP = {
    "relevance": {
        "display_name": "Relevance",
        "fields": (
            "-is_bookmarked",
            "-table_match",
            "-search_rank_name",
            "-search_rank_short_description",
            "-search_rank_tags",
            "-search_rank_description",
            "-search_rank",
            "-published_date",
            "name",
        ),
    },
    "-published": {
        "display_name": "Date published: newest",
        "fields": ("-published_date", "-search_rank", "name"),
    },
    "published": {
        "display_name": "Date published: oldest",
        "fields": ("published_date", "-search_rank", "name"),
    },
    "alphabetical": {
        "display_name": "Alphabetical (A-Z)",
        "fields": ("name",),
    },
    "popularity": {
        "display_name": "Popularity",
        "fields": ("-average_unique_users_daily", "-published_date", "name"),
    },
}


class SearchDatasetsFilters:
    unpublished: bool
    open_data: bool
    with_visuals: bool
    use: set
    data_type: set
    sort_type: str
    source_ids: set
    topic_ids: set
    publisher_ids: set
    user_accessible: set
    user_inaccessible: set
    query: str

    my_datasets: set

    def has_filters(self):
        return (
            len(self.my_datasets)
            or self.unpublished
            or self.open_data
            or self.with_visuals
            or bool(self.use)
            or bool(self.data_type)
            or bool(self.source_ids)
            or bool(self.topic_ids)
            or bool(self.publisher_ids)
            or bool(self.user_accessible)
            or bool(self.user_inaccessible)
        )


def _get_datasets_data_for_user_matching_query(
    datasets: QuerySet,
    query: str,
    id_field,
    user,
):
    datasets = _filter_datasets_by_permissions(datasets, user)
    datasets = _filter_by_query(datasets, query)

    # Annotate with ranks for name, short_description, tags and description, as well as the
    # concatenation of these to support sorting by relevance. Normalization for tags is set
    # to 0 which ignores the document length. This is to prevent datasets that have multiple
    # tags ranking lower than those that have fewer tags.
    #
    # On ranking name: if we used a plain SearchRank, this would prioritise duplicate words
    # too much, e.g. when searching for "data workspace" results that have an unrelated
    # "data" term in the name would be above those without, even if using normalisation.
    #
    # A rank of
    #
    # 0                   - if no query match on the name
    # 1/(document length) - if a query match on the name
    #
    # seems to work better in this respect. However, this is tricky to do directly in Django,
    # since "there being a match" via tha match operator @@ is abstracted away, and since
    # finding the document length of a search vector is not directly exposed. However, we can
    # extract the above by two different calls to SearchRank, each with a different
    # normalization value, and dividing them.
    datasets = datasets.annotate(
        search_rank=SearchRank(F("search_vector_english"), SearchQuery(query, config="english")),
        search_rank_name=Case(
            When(
                search_vector_english_name=SearchQuery(query, config="english"),
                then=SearchRank(
                    F("search_vector_english_name"),
                    SearchQuery(query, config="english"),
                    normalization=Value(2),
                )
                / SearchRank(
                    F("search_vector_english_name"),
                    SearchQuery(query, config="english"),
                    normalization=Value(0),
                ),
            ),
            default=0.0,
            output_field=FloatField(),
        ),
        search_rank_short_description=SearchRank(
            F("search_vector_english_short_description"),
            SearchQuery(query, config="english"),
            cover_density=True,
            normalization=Value(1),
        ),
        search_rank_tags=SearchRank(
            F("search_vector_english_tags"),
            SearchQuery(query, config="english"),
            cover_density=True,
            normalization=Value(0),
        ),
        search_rank_description=SearchRank(
            F("search_vector_english_description"),
            SearchQuery(query, config="english"),
            cover_density=True,
            normalization=Value(1),
        ),
    )

    datasets = _annotate_has_access(datasets, user)
    datasets = _annotate_is_bookmarked(datasets, user)
    datasets = _annotate_source_table_match(datasets, query)

    datasets = _annotate_is_subscribed(datasets, user)
    datasets = _annotate_tags(datasets)

    datasets = _annotate_data_type(datasets)
    datasets = _annotate_is_open_data(datasets)

    datasets = _annotate_has_visuals(datasets)

    datasets = _annotate_combined_published_date(datasets)

    datasets = _annotate_is_owner(datasets, user)

    datasets = _annotate_is_contact(datasets, user)

    return datasets.values(
        id_field,
        "name",
        "slug",
        "short_description",
        "search_rank",
        "search_rank_name",
        "search_rank_short_description",
        "search_rank_tags",
        "search_rank_description",
        "source_tag_ids",
        "topic_tag_ids",
        "publisher_tag_ids",
        "data_type",
        "published",
        "is_open_data",
        "has_visuals",
        "has_access",
        "is_bookmarked",
        "table_match",
        "is_subscribed",
        "published_date",
        "average_unique_users_daily",
        "is_owner",
        "is_contact",
    )


def _schema_table_from_search_term(search_term):
    # If a search term contains dots we take everything after the last `.` as
    # the table name and everything before the last `.` as the schema
    table = search_term
    schema = None
    split_term = search_term.split(".")
    if len(split_term) > 1:
        schema = "".join(split_term[:-1])
        table = split_term[-1]
    return schema, table


def _filter_by_query(datasets, query):
    """
    Filter out datasets that don't match the search terms
    @param datasets: django queryset
    @param query: query text from web
    @return:
    """
    search_filter = Q()
    if query:
        schema, table = _schema_table_from_search_term(query)
        if datasets.model is DataSet:
            table_match = Q(sourcetable__table=table)
            if schema:
                table_match &= Q(sourcetable__schema=schema)
            search_filter |= table_match
        if datasets.model is ReferenceDataset:
            search_filter |= Q(table_name=table)
        search_filter |= Q(search_vector_english=SearchQuery(query, config="english"))
    return datasets.filter(search_filter)


def _filter_datasets_by_permissions(datasets, user):
    """
    Filter out datasets that the user is not allowed to even know about
    @param datasets: django queryset
    @param user: request.user
    @return: queryset with filter applied
    """
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
    return datasets


def _annotate_combined_published_date(datasets: QuerySet) -> tuple:
    if datasets.model is ReferenceDataset:
        return datasets.annotate(published_date=F("initial_published_at"))

    return datasets.annotate(published_date=F("published_at"))


def _annotate_has_visuals(datasets):
    """
    Adds a bool annotation to queryset if the dataset has visuals
    @param datasets: django queryset
    @return: the annotated dataset
    """
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
    return datasets


def _annotate_is_open_data(datasets):
    """
    Adds boolean annotation which is True if the dataset is opendata.
    All reference datasets are open otherwise they are open when the user access type is OPEN
    @param datasets: django queryset
    @return:
    """
    if datasets.model is ReferenceDataset:
        return datasets.annotate(is_open_data=Value(False, BooleanField()))

    if datasets.model is DataSet or datasets.model is VisualisationCatalogueItem:
        datasets = datasets.annotate(
            is_open_data=Case(
                When(user_access_type=UserAccessType.OPEN, then=True),
                default=False,
                output_field=BooleanField(),
            )
        )
    return datasets


def _annotate_data_type(datasets):
    """
    Adds an integer field annotation to queryset corresponding to the dataset type
    @param datasets:
    @return:
    """
    if datasets.model is ReferenceDataset:
        return datasets.annotate(data_type=Value(DataSetType.REFERENCE, IntegerField()))

    if datasets.model is DataSet:
        return datasets.annotate(data_type=F("type"))

    if datasets.model is VisualisationCatalogueItem:
        return datasets.annotate(data_type=Value(DataSetType.VISUALISATION, IntegerField()))

    return datasets


def _annotate_tags(datasets):
    """
    Adds annotation for source, publisher and topic tags
    @param datasets: django queryset
    @return:
    """
    datasets = datasets.annotate(
        source_tag_ids=ArrayAgg("tags", filter=Q(tags__type=TagType.SOURCE), distinct=True)
    )
    datasets = datasets.annotate(
        topic_tag_ids=ArrayAgg("tags", filter=Q(tags__type=TagType.TOPIC), distinct=True)
    )
    datasets = datasets.annotate(
        publisher_tag_ids=ArrayAgg("tags", filter=Q(tags__type=TagType.PUBLISHER), distinct=True)
    )
    return datasets


def _annotate_is_subscribed(datasets, user):
    """
    Adds a bool annotation which is True if the user has a subscription to the dataset
    @param datasets: django queryset
    @param user: request.user
    @return:
    """
    if datasets.model is ReferenceDataset or datasets.model is VisualisationCatalogueItem:
        return datasets.annotate(is_subscribed=Value(False, BooleanField()))

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
    return datasets


def _annotate_is_bookmarked(datasets, user):
    """
    Adds a boolean annotation to queryset from *dataset bookmarks
    @param datasets: django querysey
    @param user: request.user
    @return:
    """
    if datasets.model is ReferenceDataset:
        datasets = datasets.annotate(
            user_bookmark=FilteredRelation(
                "referencedatasetbookmark",
                condition=Q(referencedatasetbookmark__user=user),
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
    return datasets


def _annotate_source_table_match(datasets, query):
    if datasets.model is DataSet or datasets.model is ReferenceDataset:
        schema, table = _schema_table_from_search_term(query)
        search_filter = Q()
        if datasets.model is ReferenceDataset:
            search_filter |= Q(table_name=table)
        else:
            table_match = Q(sourcetable__table=table)
            if schema:
                table_match &= Q(sourcetable__schema=schema)
            search_filter |= table_match

        return datasets.annotate(
            table_match=BoolOr(
                Case(
                    When(search_filter, then=True),
                    default=False,
                    output_field=BooleanField(),
                ),
            ),
        )

    return datasets.annotate(
        table_match=Value(False, BooleanField()),
    )


def _annotate_has_access(datasets, user):
    """
    Adds a bool annotation to queryset if user has access to the dataset
    @param datasets: django queryset
    @param user: request.user
    @return: queryset
    """
    if datasets.model is ReferenceDataset:
        datasets = datasets.annotate(has_access=Value(True, BooleanField()))

    if datasets.model is DataSet or datasets.model is VisualisationCatalogueItem:
        if datasets.model is DataSet:
            datasets = datasets.annotate(
                user_permission=FilteredRelation(
                    "datasetuserpermission",
                    condition=Q(datasetuserpermission__user=user),
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
    return datasets


def _annotate_is_contact(datasets, user):
    """
    Adds a boolean annotation to queryset which is set to True if the user
    is an IAO, IAM or data catalogue editor of a dataset
    @param datasets: Django queryset
    @param user: request.user
    @return: Annotated queryset
    """

    datasets = datasets.annotate(
        is_contact=BoolOr(
            Case(
                When(
                    Q(enquiries_contact=user),
                    then=True,
                ),
                default=False,
                output_field=BooleanField(),
            ),
        ),
    )
    return datasets


def _annotate_is_owner(datasets, user):
    """
    Adds a boolean annotation to queryset which is set to True if the user
    is an IAO, IAM or data catalogue editor of a dataset
    @param datasets: Django queryset
    @param user: request.user
    @return: Annotated queryset
    """

    datasets = datasets.annotate(
        is_owner=BoolOr(
            Case(
                When(
                    Q(information_asset_owner=user)
                    | Q(information_asset_manager=user)
                    | Q(data_catalogue_editors=user),
                    then=True,
                ),
                default=False,
                output_field=BooleanField(),
            ),
        ),
    )
    return datasets


def _sorted_datasets_and_visualisations_matching_query_for_user(query, user, sort_by):
    """
    Retrieves all master datasets, datacuts, reference datasets and visualisations (i.e. searchable items)
    and returns them, sorted by incoming sort field
    @param query: django queryset
    @param user: request.user
    @param sort_by: str one or many sort fields in django queryset order_by. i.e '-name' or 'name' or '-name,-dob'

    @return:
    """

    master_and_datacut_datasets = _get_datasets_data_for_user_matching_query(
        # Exclude ReferenceDatasetInheritingFromDataSet as
        # ReferenceDatasets are added below.
        DataSet.objects.live().exclude(type=DataSetType.REFERENCE),
        query,
        id_field="id",
        user=user,
    )

    print("result", master_and_datacut_datasets)

    reference_datasets = _get_datasets_data_for_user_matching_query(
        ReferenceDataset.objects.live().annotate(
            data_catalogue_editors=Value(None, output_field=CharField())
        ),
        query,
        id_field="uuid",
        user=user,
    )

    visualisations = _get_datasets_data_for_user_matching_query(
        VisualisationCatalogueItem.objects.live(), query, id_field="id", user=user
    )

    # Combine all datasets and visualisations and order them.
    sort_fields = sort_by["fields"]

    # If there is a query, ignore bookmarks for the purposes of sort, since
    # if someone is searching for something, likely it's not something they
    # bookmarked since that would have already been high on the front page
    if query:
        sort_fields = [
            field for field in sort_fields if field not in ("is_bookmarked", "-is_bookmarked")
        ]

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
                filters.publisher_ids,
                filters.user_accessible,
                filters.user_inaccessible,
                filters.my_datasets,
            ),
            all_datasets_visible_to_user_matching_query,
        )
    )

    return (
        all_datasets_visible_to_user_matching_query,
        datasets_matching_query_and_filters,
    )


def _get_popularity_calculation_period(dataset):
    """
    Returns the start and end datetimes for a valid period to calculate dataset usage on.
    The calculation period is:

    From: Midnight 28 days before the calculation is done
    To: Midnight of the day the calculation is done

    If the dataset was published less than 28 days ago, start the period at midnight the day
    after it was published.
    """
    # The farthest we go back is 00:00 28 days ago
    period_end = datetime.combine(datetime.utcnow(), time.min)
    min_start_date = datetime.combine(datetime.utcnow(), time.min) - timedelta(days=28)

    # If the vis was published < 28 days ago, start the count
    # from the end of the day it was first published
    published_date = (
        datetime.combine(dataset.published_at, time.max)
        if dataset.published_at is not None
        else min_start_date
    )
    period_start = max(min_start_date, published_date)

    return period_start, period_end


def calculate_visualisation_average(visualisation):
    period_start, period_end = _get_popularity_calculation_period(visualisation)
    total_days = (period_end - period_start).days

    logger.info(
        "Calculating average usage for visualisation '%s' for the period %s - %s (%s days)",
        visualisation.name,
        period_start,
        period_end,
        total_days,
    )

    if total_days < 1:
        return 0

    total_users = (
        visualisation.events.filter(
            event_type__in=[
                EventLog.TYPE_VIEW_QUICKSIGHT_VISUALISATION,
                EventLog.TYPE_VIEW_SUPERSET_VISUALISATION,
                EventLog.TYPE_VIEW_VISUALISATION_TEMPLATE,
            ],
            timestamp__gt=period_start.replace(tzinfo=utc),
            timestamp__lt=period_end.replace(tzinfo=utc),
        )
        .values("timestamp__date")
        .annotate(user_count=Count("user", distinct=True))
        .aggregate(total_users=Sum("user_count"))["total_users"]
    )

    if total_users is None:
        return 0

    return total_users / total_days


def calculate_dataset_average(dataset):
    period_start, period_end = _get_popularity_calculation_period(dataset)
    total_days = (period_end - period_start).days

    logger.info(
        "Calculating average usage for dataset '%s' for the period %s - %s (%s days)",
        dataset.name,
        period_start,
        period_end,
        total_days,
    )

    if total_days < 1:
        return 0

    q = Q(pk__in=[])  # If there are no tables, match no ToolQueryAuditLog instances
    for table in dataset.sourcetable_set.all():
        q = q | Q(tables__schema=table.schema, tables__table=table.table)

    query_user_days = (
        ToolQueryAuditLog.objects.filter(
            timestamp__gt=period_start.replace(tzinfo=utc),
            timestamp__lt=period_end.replace(tzinfo=utc),
        )
        .filter(q)
        .values_list("timestamp__date", "user")
        .distinct()
    )

    event_user_days = (
        dataset.events.filter(
            event_type__in=[
                EventLog.TYPE_DATASET_CUSTOM_QUERY_DOWNLOAD,
                EventLog.TYPE_DATASET_CUSTOM_QUERY_DOWNLOAD_COMPLETE,
                EventLog.TYPE_DATASET_SOURCE_VIEW_DOWNLOAD,
                EventLog.TYPE_DATASET_TABLE_DATA_DOWNLOAD,
            ],
            timestamp__gt=period_start.replace(tzinfo=utc),
            timestamp__lt=period_end.replace(tzinfo=utc),
        )
        .values_list("timestamp__date", "user")
        .distinct()
    )

    total_users = set(query_user_days) | set(event_user_days)

    return len(total_users) / total_days


def calculate_ref_dataset_average(ref_dataset):
    period_start, period_end = _get_popularity_calculation_period(ref_dataset)
    total_days = (period_end - period_start).days

    logger.info(
        "Calculating average usage for reference dataset '%s' for the period %s - %s (%s days)",
        ref_dataset.name,
        period_start,
        period_end,
        total_days,
    )

    if total_days < 1:
        return 0

    query_user_days = (
        ToolQueryAuditLog.objects.filter(
            timestamp__gt=period_start.replace(tzinfo=utc),
            timestamp__lt=period_end.replace(tzinfo=utc),
        )
        .filter(tables__schema="public", tables__table=ref_dataset.table_name)
        .values_list("timestamp__date", "user")
        .distinct()
    )

    event_user_days = (
        ref_dataset.events.filter(
            event_type__in=[
                EventLog.TYPE_REFERENCE_DATASET_VIEW,
                EventLog.TYPE_REFERENCE_DATASET_DOWNLOAD,
            ],
            timestamp__gt=period_start.replace(tzinfo=utc),
            timestamp__lt=period_end.replace(tzinfo=utc),
        )
        .values_list("timestamp__date", "user")
        .distinct()
    )

    total_users = set(query_user_days) | set(event_user_days)
    return len(total_users) / total_days


def _update_datasets_average_daily_users():
    def _update_datasets(datasets, calculate_value):
        for dataset in datasets:
            value = calculate_value(dataset)
            logger.info("%s average unique users: %s", dataset, value)
            dataset.average_unique_users_daily = value
            dataset.save()

    _update_datasets(DataSet.objects.live().filter(published=True), calculate_dataset_average)
    _update_datasets(
        ReferenceDataset.objects.live().filter(published=True), calculate_ref_dataset_average
    )
    _update_datasets(
        VisualisationCatalogueItem.objects.live().filter(published=True),
        calculate_visualisation_average,
    )


@celery_app.task()
@close_all_connections_if_not_in_atomic_block
def update_datasets_average_daily_users():
    try:
        with cache.lock(
            "update_datasets_average_daily_users_lock", blocking_timeout=0, timeout=1800
        ):
            _update_datasets_average_daily_users()
    except redis.exceptions.LockError:
        logger.info("Unable to acquire lock to update dataset averages")


def suggested_searches(request):
    if waffle.flag_is_active(request, settings.SUGGESTED_SEARCHES_FLAG):
        query = request.GET.get("query", None)

        # Using Django's standard '__' on JSON fields in keword arguments uses the '->' operator
        # in the resulting SQL query. But we can't pass the result of that to the PostgreSQL
        # function LOWER for a case-insensitive GROUP BY since PostreSQL won't know the result is
        # text. Instead, need to use '->>'. But to do that we have to use KeyTextTransform
        query_as_text = KeyTextTransform("query", "extra")

        recent_searches = (
            EventLog.objects.annotate(lower_query=Lower(query_as_text))
            .filter(
                lower_query__startswith=query.lower().strip(),
                event_type=EventLog.TYPE_DATASET_FIND_FORM_QUERY,
                extra__number_of_results__gt=0,
                timestamp__gt=datetime.today() - timedelta(days=30),
            )
            .values("lower_query")  # So GROUP BY is only on "lower_query", not "id, lower_query"
            .annotate(occurrences=Count("lower_query"))
            .values("lower_query")  # Prevents "occurrences" from being output needlessly
            .order_by("-occurrences")[:5]
        )

        return JsonResponse(
            [{"name": search["lower_query"], "type": "", "url": ""} for search in recent_searches],
            safe=False,
            status=200,
        )

    else:
        return JsonResponse(
            [],
            safe=False,
            status=200,
        )
