import string
import uuid
from datetime import datetime, timedelta

import factory.fuzzy
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from freezegun import freeze_time

from dataworkspace.apps.datasets.constants import DataSetType, TagType
from dataworkspace.apps.eventlog.models import EventLog


class UserProfileFactory(factory.django.DjangoModelFactory):
    sso_id = "7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2"

    class Meta:
        model = "accounts.Profile"


class UserFactory(factory.django.DjangoModelFactory):
    username = factory.LazyAttribute(lambda _: str(uuid.uuid4()))
    email = factory.LazyAttribute(lambda o: f"test.user+{o.username}@example.com")
    password = "12345"

    class Meta:
        model = get_user_model()


class DatabaseFactory(factory.django.DjangoModelFactory):
    memorable_name = "test_external_db"

    class Meta:
        model = "core.Database"
        django_get_or_create = ("memorable_name",)


class DataGroupingFactory(factory.django.DjangoModelFactory):
    name = factory.fuzzy.FuzzyText()
    slug = factory.fuzzy.FuzzyText(length=10)

    class Meta:
        model = "datasets.DataGrouping"


class TagFactory(factory.django.DjangoModelFactory):
    name = factory.fuzzy.FuzzyText()

    class Meta:
        model = "datasets.Tag"


class SourceTagFactory(TagFactory):
    type = TagType.SOURCE


class TopicTagFactory(TagFactory):
    type = TagType.TOPIC


class PublisherTagFactory(TagFactory):
    type = TagType.PUBLISHER


class DataSetFactory(factory.django.DjangoModelFactory):
    grouping = factory.SubFactory(DataGroupingFactory)
    name = factory.fuzzy.FuzzyText()
    slug = factory.fuzzy.FuzzyText(length=10)
    published = True
    deleted = False
    type = DataSetType.DATACUT
    information_asset_owner = factory.SubFactory(UserFactory)
    information_asset_manager = factory.SubFactory(UserFactory)
    enquiries_contact = factory.SubFactory(UserFactory)

    class Meta:
        model = "datasets.DataSet"


class DatacutDataSetFactory(DataSetFactory):
    type = DataSetType.DATACUT


class MasterDataSetFactory(DataSetFactory):
    type = DataSetType.MASTER


class RequestingDataSetFactory(factory.django.DjangoModelFactory):
    # grouping = factory.SubFactory(DataGroupingFactory)
    name = factory.fuzzy.FuzzyText()
    slug = factory.fuzzy.FuzzyText(length=10)
    user = "1"
    short_description = factory.fuzzy.FuzzyText(length=10)
    description = factory.fuzzy.FuzzyText(length=30)
    published = False
    deleted = False
    type = DataSetType.MASTER
    information_asset_owner = factory.SubFactory(UserFactory)
    information_asset_manager = factory.SubFactory(UserFactory)
    enquiries_contact = factory.SubFactory(UserFactory)

    class Meta:
        model = "datasets.RequestingDataset"


class DataSetUserPermissionFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    dataset = factory.SubFactory(DataSetFactory)

    class Meta:
        model = "datasets.DataSetUserPermission"


class DataSetBookmarkFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    dataset = factory.SubFactory(DataSetFactory)

    class Meta:
        model = "datasets.DataSetBookmark"


class SourceLinkFactory(factory.django.DjangoModelFactory):
    dataset = factory.SubFactory(DataSetFactory)
    name = factory.fuzzy.FuzzyText()
    format = factory.fuzzy.FuzzyText(length=5)
    frequency = factory.fuzzy.FuzzyText(length=5)
    url = "http://example.com"

    class Meta:
        model = "datasets.SourceLink"


class SourceTableFactory(factory.django.DjangoModelFactory):
    dataset = factory.SubFactory(DataSetFactory)
    database = factory.SubFactory(DatabaseFactory)

    class Meta:
        model = "datasets.SourceTable"


class SourceViewFactory(factory.django.DjangoModelFactory):
    dataset = factory.SubFactory(DataSetFactory)
    database = factory.SubFactory(DatabaseFactory)

    class Meta:
        model = "datasets.SourceView"


class CustomDatasetQueryFactory(factory.django.DjangoModelFactory):
    name = factory.fuzzy.FuzzyText()
    dataset = factory.SubFactory(DataSetFactory)
    database = factory.SubFactory(DatabaseFactory)
    reviewed = True
    frequency = 1

    class Meta:
        model = "datasets.CustomDatasetQuery"


class CustomDatasetQueryTableFactory(factory.django.DjangoModelFactory):
    query = factory.SubFactory(CustomDatasetQueryFactory)
    table = factory.fuzzy.FuzzyText()
    schema = factory.fuzzy.FuzzyText()

    class Meta:
        model = "datasets.CustomDatasetQueryTable"


class DatasetReferenceCodeFactory(factory.django.DjangoModelFactory):
    code = factory.fuzzy.FuzzyText(length=3)
    counter = 0

    class Meta:
        model = "datasets.DatasetReferenceCode"


class ReferenceDatasetFactory(factory.django.DjangoModelFactory):
    group = factory.SubFactory(DataGroupingFactory)
    name = factory.fuzzy.FuzzyText()
    slug = factory.fuzzy.FuzzyText(length=10)
    published = True
    schema_version = factory.Sequence(lambda n: n)
    table_name = factory.fuzzy.FuzzyText(length=20, prefix="ref_")

    class Meta:
        model = "datasets.ReferenceDataset"


class ReferenceDataSetBookmarkFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    reference_dataset = factory.SubFactory(ReferenceDatasetFactory)

    class Meta:
        model = "datasets.ReferenceDataSetBookmark"


class ReferenceDatasetFieldFactory(factory.django.DjangoModelFactory):
    reference_dataset = factory.SubFactory(ReferenceDatasetFactory)
    name = factory.fuzzy.FuzzyText()
    column_name = factory.fuzzy.FuzzyText(length=65, chars=string.ascii_lowercase)
    data_type = 1

    class Meta:
        model = "datasets.ReferenceDatasetField"


class EventLogFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    event_type = 1

    class Meta:
        model = "eventlog.EventLog"


@freeze_time("2020-01-01 00:00:00")
class RelatedObjectEventFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    timestamp = datetime.now()
    object_id = factory.SelfAttribute("content_object.id")
    content_type = factory.LazyAttribute(
        lambda o: ContentType.objects.get_for_model(o.content_object)
    )

    class Meta:
        model = "eventlog.EventLog"
        exclude = ["content_object"]
        abstract = True


class DatasetLinkDownloadEventFactory(RelatedObjectEventFactory):
    event_type = EventLog.TYPE_DATASET_SOURCE_LINK_DOWNLOAD
    content_object = factory.SubFactory(DataSetFactory)
    extra = {
        "url": "http://google.com",
        "name": "a link",
        "path": "/datasets/download/link",
        "format": "test",
        "link_type": 1,
    }


class DatasetQueryDownloadEventFactory(RelatedObjectEventFactory):
    event_type = EventLog.TYPE_DATASET_CUSTOM_QUERY_DOWNLOAD
    content_object = factory.SubFactory(DataSetFactory)
    extra = {
        "id": 1,
        "name": "A test query",
        "path": "/datasets/0102d134-2d2e-48b5-b8c2-061a6a649fee/query/1/download",
        "query": "select * from a_table",
    }


class ReferenceDatasetDownloadEventFactory(RelatedObjectEventFactory):
    event_type = EventLog.TYPE_REFERENCE_DATASET_DOWNLOAD
    content_object = factory.SubFactory(ReferenceDatasetFactory)
    extra = {
        "path": "/datasets/5ccc3c6a-9f4b-48fa-bba3-89de9b2bc3f0/reference/csv/download",
        "download_format": "csv",
        "reference_dataset_version": "1.1",
    }


class DatasetAccessRequestEventFactory(RelatedObjectEventFactory):
    event_type = EventLog.TYPE_DATASET_ACCESS_REQUEST
    content_object = factory.SubFactory(DatacutDataSetFactory)
    extra = {
        "contact_email": "test@test.com",
        "goal": "Access data",
        "ticket_reference": 999,
    }


class DatasetAccessGrantedEventFactory(RelatedObjectEventFactory):
    event_type = EventLog.TYPE_GRANTED_DATASET_PERMISSION
    content_object = factory.SubFactory(UserFactory)
    extra = {
        "created_by": 1,
        "updated_by": 1,
        "deleted": False,
        "type": 2,
        "name": "A dataset",
        "slug": "a-dataset",
        "short_description": "test",
        "user_access_type": "REQUIRES_AUTHORIZATION",
    }


class DatasetAccessRevokedEventFactory(RelatedObjectEventFactory):
    event_type = EventLog.TYPE_GRANTED_DATASET_PERMISSION
    content_object = factory.SubFactory(UserFactory)
    extra = {
        "created_by": 1,
        "updated_by": 1,
        "deleted": False,
        "type": 2,
        "name": "A dataset",
        "slug": "a-dataset",
        "short_description": "test",
        "user_access_type": "REQUIRES_AUTHORIZATION",
    }


class VisualisationViewedEventFactory(RelatedObjectEventFactory):
    event_type = EventLog.TYPE_VIEW_VISUALISATION_TEMPLATE
    content_object = factory.SubFactory(DataSetFactory)
    extra = {
        "id": 1,
        "name": "A test visualisation",
    }


class SupersetVisualisationViewedEventFactory(RelatedObjectEventFactory):
    event_type = EventLog.TYPE_VIEW_SUPERSET_VISUALISATION
    content_object = factory.SubFactory(DataSetFactory)
    extra = {
        "id": 1,
        "name": "A test superset visualisation",
    }


@freeze_time("2020-01-01 00:00:00")
class ApplicationTemplateFactory(factory.django.DjangoModelFactory):
    name = factory.fuzzy.FuzzyText()
    visible = True
    host_basename = factory.fuzzy.FuzzyText()
    nice_name = factory.fuzzy.FuzzyText()
    spawner = "PROCESS"
    spawner_time = int(datetime.timestamp(datetime.now()))
    spawner_options = "{}"
    application_type = "TOOL"

    class Meta:
        model = "applications.ApplicationTemplate"


class DataSetApplicationTemplatePermissionFactory(factory.django.DjangoModelFactory):
    application_template = factory.SubFactory(ApplicationTemplateFactory)
    dataset = factory.SubFactory(DataSetFactory)

    class Meta:
        model = "datasets.DataSetApplicationTemplatePermission"


class VisualisationTemplateFactory(ApplicationTemplateFactory):
    application_type = "VISUALISATION"

    class Meta:
        model = "applications.VisualisationTemplate"


class VisualisationApprovalFactory(factory.django.DjangoModelFactory):
    id = factory.LazyAttribute(lambda _: uuid.uuid4())
    approved = True
    approver = factory.SubFactory(UserFactory)
    visualisation = factory.SubFactory(VisualisationTemplateFactory)

    class Meta:
        model = "applications.VisualisationApproval"


class VisualisationCatalogueItemFactory(factory.django.DjangoModelFactory):
    id = factory.LazyAttribute(lambda _: uuid.uuid4())
    visualisation_template = factory.SubFactory(VisualisationTemplateFactory)
    name = factory.LazyAttribute(
        lambda o: (
            o.visualisation_template.name
            if o.visualisation_template
            else factory.fuzzy.FuzzyText().fuzz()
        )
    )
    slug = factory.LazyAttribute(lambda o: o.name.lower())
    published = True
    deleted = False

    class Meta:
        model = "datasets.VisualisationCatalogueItem"


class VisualisationUserPermissionFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    visualisation = factory.SubFactory(VisualisationCatalogueItemFactory)

    class Meta:
        model = "datasets.VisualisationUserPermission"


class VisualisationBookmarkFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    visualisation = factory.SubFactory(VisualisationCatalogueItemFactory)

    class Meta:
        model = "datasets.VisualisationBookmark"


class VisualisationLinkFactory(factory.django.DjangoModelFactory):
    id = factory.LazyAttribute(lambda _: uuid.uuid4())
    visualisation_catalogue_item = factory.SubFactory(VisualisationCatalogueItemFactory)

    class Meta:
        model = "datasets.VisualisationLink"


class ApplicationInstanceFactory(factory.django.DjangoModelFactory):
    id = factory.LazyAttribute(lambda _: uuid.uuid4())
    application_template = factory.SubFactory(ApplicationTemplateFactory)
    owner = factory.SubFactory(UserFactory)
    public_host = "https://analysisworkspace.dev.uktrade.io/"
    spawner = factory.fuzzy.FuzzyText()
    spawner_application_template_options = "{}"
    spawner_application_instance_id = factory.LazyAttribute(lambda _: uuid.uuid4())
    spawner_created_at = datetime.now() - timedelta(minutes=5)
    spawner_stopped_at = datetime.now()
    spawner_cpu = factory.fuzzy.FuzzyChoice(["256", "1024", "2048", "4096"])
    spawner_memory = factory.fuzzy.FuzzyChoice(["512", "8192", "16384", "30720"])
    state = factory.fuzzy.FuzzyChoice(["SPAWNING", "RUNNING", "STOPPED"])
    proxy_url = "https://analysisworkspace.dev.uktrade.io/"
    cpu = factory.fuzzy.FuzzyChoice(["256", "1024", "2048", "4096"])
    memory = factory.fuzzy.FuzzyChoice(["512", "8192", "16384", "30720"])
    single_running_or_spawning_integrity = factory.fuzzy.FuzzyText()
    commit_id = factory.fuzzy.FuzzyText(length=8)

    class Meta:
        model = "applications.ApplicationInstance"


class DatabaseUserFactory(factory.django.DjangoModelFactory):
    owner = factory.SubFactory(UserFactory)
    username = factory.fuzzy.FuzzyText(length=8)

    class Meta:
        model = "core.DatabaseUser"


class ToolQueryAuditLogFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    database = factory.SubFactory(DatabaseFactory)
    rolename = factory.fuzzy.FuzzyText(length=10)
    query_sql = "select * from a_table"
    timestamp = datetime.now()

    class Meta:
        model = "datasets.ToolQueryAuditLog"


class ToolQueryAuditLogTableFactory(factory.django.DjangoModelFactory):
    audit_log = factory.SubFactory(ToolQueryAuditLogFactory)
    schema = factory.fuzzy.FuzzyText(length=10)
    table = factory.fuzzy.FuzzyText(length=10)

    class Meta:
        model = "datasets.ToolQueryAuditLogTable"


class DataSetSubscriptionFactory(factory.django.DjangoModelFactory):
    notify_on_schema_change = True

    class Meta:
        model = "datasets.DataSetSubscription"


class PipelineFactory(factory.django.DjangoModelFactory):
    type = "sql"
    table_name = factory.fuzzy.FuzzyText(length=20, prefix="schema.")
    config = {}
    notes = ""

    class Meta:
        model = "datasets.Pipeline"


class CollectionFactory(factory.django.DjangoModelFactory):
    name = factory.fuzzy.FuzzyText()
    description = factory.fuzzy.FuzzyText()

    class Meta:
        model = "data_collections.Collection"


class CollectionUserMembershipFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    collection = factory.SubFactory(CollectionFactory)

    class Meta:
        model = "data_collections.CollectionUserMembership"


class UserDataTableViewFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)

    class Meta:
        model = "accounts.UserDataTableView"


class InlineFeedbackFactory(factory.django.DjangoModelFactory):
    was_this_page_helpful = True
    location = factory.fuzzy.FuzzyText()
    inline_feedback_choices = ""
    more_detail = ""

    class Meta:
        model = "core.UserInlineFeedbackSurvey"


class PendingAuthorizedUsersFactory(factory.django.DjangoModelFactory):
    users = factory.SubFactory(UserFactory)

    class Meta:
        model = "datasets.PendingAuthorizedUsers"


class AccessRequestFactory(factory.django.DjangoModelFactory):
    requester = factory.SubFactory(UserFactory)
    catalogue_item_id = factory.LazyAttribute(lambda _: uuid.uuid4())
    contact_email = "frank@example.com"
    eligibility_criteria_met = True
    reason_for_access = "I want it"
    zendesk_reference_number = "ref123"

    data_access_status = "waiting"

    class Meta:
        model = "request_access.AccessRequest"
