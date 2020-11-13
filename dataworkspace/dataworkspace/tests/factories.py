import uuid
from datetime import datetime, timedelta

import factory.fuzzy

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from dataworkspace.apps.datasets.constants import TagType
from dataworkspace.apps.datasets.models import DataSet
from dataworkspace.apps.eventlog.models import EventLog


class UserProfileFactory(factory.django.DjangoModelFactory):
    sso_id = '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2'

    class Meta:
        model = 'accounts.Profile'


class UserFactory(factory.django.DjangoModelFactory):
    username = factory.LazyAttribute(lambda _: f'test.user+{uuid.uuid4()}@example.com')
    email = factory.LazyAttribute(lambda o: o.username)
    password = '12345'

    class Meta:
        model = get_user_model()


class DatabaseFactory(factory.django.DjangoModelFactory):
    id = factory.LazyAttribute(lambda _: uuid.uuid4())
    memorable_name = 'test_external_db'

    class Meta:
        model = 'core.Database'
        django_get_or_create = ('memorable_name',)


class DataGroupingFactory(factory.django.DjangoModelFactory):
    id = factory.LazyAttribute(lambda _: uuid.uuid4())
    name = factory.fuzzy.FuzzyText()
    slug = factory.fuzzy.FuzzyText(length=10)

    class Meta:
        model = 'datasets.DataGrouping'


class TagFactory(factory.django.DjangoModelFactory):
    id = factory.LazyAttribute(lambda _: uuid.uuid4())
    name = factory.fuzzy.FuzzyText()

    class Meta:
        model = 'datasets.Tag'


class SourceTagFactory(TagFactory):
    type = TagType.SOURCE.value


class TopicTagFactory(TagFactory):
    type = TagType.TOPIC.value


class DataSetFactory(factory.django.DjangoModelFactory):
    grouping = factory.SubFactory(DataGroupingFactory)
    name = factory.fuzzy.FuzzyText()
    slug = factory.fuzzy.FuzzyText(length=10)
    published = True
    deleted = False
    type = DataSet.TYPE_DATA_CUT

    class Meta:
        model = 'datasets.DataSet'


class DatacutDataSetFactory(DataSetFactory):
    type = DataSet.TYPE_DATA_CUT


class MasterDataSetFactory(DataSetFactory):
    type = DataSet.TYPE_MASTER_DATASET


class DataSetUserPermissionFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    dataset = factory.SubFactory(DataSetFactory)

    class Meta:
        model = 'datasets.DataSetUserPermission'


class SourceLinkFactory(factory.django.DjangoModelFactory):
    id = factory.LazyAttribute(lambda _: uuid.uuid4())
    dataset = factory.SubFactory(DataSetFactory)
    name = factory.fuzzy.FuzzyText()
    format = factory.fuzzy.FuzzyText(length=5)
    frequency = factory.fuzzy.FuzzyText(length=5)
    url = 'http://example.com'

    class Meta:
        model = 'datasets.SourceLink'


class SourceTableFactory(factory.django.DjangoModelFactory):
    id = factory.LazyAttribute(lambda _: uuid.uuid4())
    dataset = factory.SubFactory(DataSetFactory)
    database = factory.SubFactory(DatabaseFactory)

    class Meta:
        model = 'datasets.SourceTable'


class SourceViewFactory(factory.django.DjangoModelFactory):
    id = factory.LazyAttribute(lambda _: uuid.uuid4())
    dataset = factory.SubFactory(DataSetFactory)
    database = factory.SubFactory(DatabaseFactory)

    class Meta:
        model = 'datasets.SourceView'


class CustomDatasetQueryFactory(factory.django.DjangoModelFactory):
    id = factory.Sequence(lambda n: n)
    name = factory.fuzzy.FuzzyText()
    dataset = factory.SubFactory(DataSetFactory)
    database = factory.SubFactory(DatabaseFactory)
    reviewed = True
    frequency = 1

    class Meta:
        model = 'datasets.CustomDatasetQuery'


class CustomDatasetQueryTableFactory(factory.django.DjangoModelFactory):
    query = factory.SubFactory(CustomDatasetQueryFactory)
    table = factory.fuzzy.FuzzyText()
    schema = factory.fuzzy.FuzzyText()

    class Meta:
        model = 'datasets.CustomDatasetQueryTable'


class DatasetReferenceCodeFactory(factory.django.DjangoModelFactory):
    id = factory.Sequence(lambda n: n)
    code = factory.fuzzy.FuzzyText(length=3)
    counter = 0

    class Meta:
        model = 'datasets.DatasetReferenceCode'


class ReferenceDatasetFactory(factory.django.DjangoModelFactory):
    group = factory.SubFactory(DataGroupingFactory)
    name = factory.fuzzy.FuzzyText()
    slug = factory.fuzzy.FuzzyText(length=10)
    published = True
    schema_version = factory.Sequence(lambda n: n)
    table_name = factory.fuzzy.FuzzyText(length=20, prefix='ref_')

    class Meta:
        model = 'datasets.ReferenceDataset'


class ReferenceDatasetFieldFactory(factory.django.DjangoModelFactory):
    reference_dataset = factory.SubFactory(ReferenceDatasetFactory)
    name = factory.fuzzy.FuzzyText()
    column_name = factory.fuzzy.FuzzyText(length=65)
    data_type = 1

    class Meta:
        model = 'datasets.ReferenceDatasetField'


class EventLogFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    event_type = 1

    class Meta:
        model = 'eventlog.EventLog'


class RelatedObjectEventFactory(factory.django.DjangoModelFactory):
    id = factory.Sequence(lambda n: n)
    user = factory.SubFactory(UserFactory)
    timestamp = datetime.now()
    object_id = factory.SelfAttribute('content_object.id')
    content_type = factory.LazyAttribute(
        lambda o: ContentType.objects.get_for_model(o.content_object)
    )

    class Meta:
        model = 'eventlog.EventLog'
        exclude = ['content_object']
        abstract = True


class DatasetLinkDownloadEventFactory(RelatedObjectEventFactory):
    event_type = EventLog.TYPE_DATASET_CUSTOM_QUERY_DOWNLOAD
    content_object = factory.SubFactory(DataSetFactory)
    extra = {
        'url': 'http://google.com',
        'name': 'a link',
        'path': '/datasets/download/link',
        'format': 'test',
        'link_type': 1,
    }


class DatasetQueryDownloadEventFactory(RelatedObjectEventFactory):
    event_type = EventLog.TYPE_DATASET_CUSTOM_QUERY_DOWNLOAD
    content_object = factory.SubFactory(DataSetFactory)
    extra = {
        'id': 1,
        'name': 'A test query',
        'path': '/datasets/0102d134-2d2e-48b5-b8c2-061a6a649fee/query/1/download',
        'query': 'select * from a_table',
    }


class ReferenceDatasetDownloadEventFactory(RelatedObjectEventFactory):
    event_type = EventLog.TYPE_REFERENCE_DATASET_DOWNLOAD
    content_object = factory.SubFactory(ReferenceDatasetFactory)
    extra = {
        'path': '/datasets/5ccc3c6a-9f4b-48fa-bba3-89de9b2bc3f0/reference/csv/download',
        'download_format': 'csv',
        'reference_dataset_version': '1.1',
    }


class DatasetAccessRequestEventFactory(RelatedObjectEventFactory):
    event_type = EventLog.TYPE_DATASET_ACCESS_REQUEST
    content_object = factory.SubFactory(DatacutDataSetFactory)
    extra = {
        'contact_email': 'test@test.com',
        'goal': 'Access data',
        'ticket_reference': 999,
    }


class DatasetAccessGrantedEventFactory(RelatedObjectEventFactory):
    event_type = EventLog.TYPE_GRANTED_DATASET_PERMISSION
    content_object = factory.SubFactory(DatacutDataSetFactory)
    extra = {
        'created_by': 1,
        'updated_by': 1,
        'deleted': False,
        'type': 2,
        'name': 'A dataset',
        'slug': 'a-dataset',
        'short_description': 'test',
        'user_access_type': 'REQUIRES_AUTHORIZATION',
    }


class DatasetAccessRevokedEventFactory(RelatedObjectEventFactory):
    event_type = EventLog.TYPE_GRANTED_DATASET_PERMISSION
    content_object = factory.SubFactory(DatacutDataSetFactory)
    extra = {
        'created_by': 1,
        'updated_by': 1,
        'deleted': False,
        'type': 2,
        'name': 'A dataset',
        'slug': 'a-dataset',
        'short_description': 'test',
        'user_access_type': 'REQUIRES_AUTHORIZATION',
    }


class ApplicationTemplateFactory(factory.django.DjangoModelFactory):
    name = factory.fuzzy.FuzzyText()
    visible = True
    host_basename = factory.fuzzy.FuzzyText()
    nice_name = factory.fuzzy.FuzzyText()
    spawner = 'PROCESS'
    spawner_time = int(datetime.timestamp(datetime.now()))
    spawner_options = '{}'
    application_type = 'TOOL'

    class Meta:
        model = 'applications.ApplicationTemplate'


class DataSetApplicationTemplatePermissionFactory(factory.django.DjangoModelFactory):
    application_template = factory.SubFactory(ApplicationTemplateFactory)
    dataset = factory.SubFactory(DataSetFactory)

    class Meta:
        model = 'datasets.DataSetApplicationTemplatePermission'


class VisualisationTemplateFactory(ApplicationTemplateFactory):
    application_type = 'VISUALISATION'

    class Meta:
        model = 'applications.VisualisationTemplate'


class VisualisationApprovalFactory(factory.django.DjangoModelFactory):
    id = factory.LazyAttribute(lambda _: uuid.uuid4())
    approved = True
    approver = factory.SubFactory(UserFactory)
    visualisation = factory.SubFactory(VisualisationTemplateFactory)

    class Meta:
        model = 'applications.VisualisationApproval'


class VisualisationCatalogueItemFactory(factory.django.DjangoModelFactory):
    visualisation_template = factory.SubFactory(VisualisationTemplateFactory)
    name = factory.LazyAttribute(
        lambda o: o.visualisation_template.name
        if o.visualisation_template
        else factory.fuzzy.FuzzyText().fuzz()
    )
    slug = factory.LazyAttribute(lambda o: o.name.lower())
    published = True
    deleted = False

    class Meta:
        model = 'datasets.VisualisationCatalogueItem'


class VisualisationUserPermissionFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    visualisation = factory.SubFactory(VisualisationCatalogueItemFactory)

    class Meta:
        model = 'datasets.VisualisationUserPermission'


class VisualisationLinkFactory(factory.django.DjangoModelFactory):
    id = factory.LazyAttribute(lambda _: uuid.uuid4())
    visualisation_catalogue_item = factory.SubFactory(VisualisationCatalogueItemFactory)

    class Meta:
        model = 'datasets.VisualisationLink'


class ApplicationInstanceFactory(factory.django.DjangoModelFactory):
    id = factory.LazyAttribute(lambda _: uuid.uuid4())
    application_template = factory.SubFactory(ApplicationTemplateFactory)
    owner = factory.SubFactory(UserFactory)
    public_host = 'https://analysisworkspace.dev.uktrade.io/'
    spawner = factory.fuzzy.FuzzyText()
    spawner_application_template_options = '{}'
    spawner_application_instance_id = factory.LazyAttribute(lambda _: uuid.uuid4())
    spawner_created_at = datetime.now() - timedelta(minutes=5)
    spawner_stopped_at = datetime.now()
    spawner_cpu = factory.fuzzy.FuzzyChoice(['256', '1024', '2048', '4096'])
    spawner_memory = factory.fuzzy.FuzzyChoice(['512', '8192', '16384', '30720'])
    state = factory.fuzzy.FuzzyChoice(['SPAWNING', 'RUNNING', 'STOPPED'])
    proxy_url = 'https://analysisworkspace.dev.uktrade.io/'
    cpu = factory.fuzzy.FuzzyChoice(['256', '1024', '2048', '4096'])
    memory = factory.fuzzy.FuzzyChoice(['512', '8192', '16384', '30720'])
    single_running_or_spawning_integrity = factory.fuzzy.FuzzyText()
    commit_id = factory.fuzzy.FuzzyText(length=8)

    class Meta:
        model = 'applications.ApplicationInstance'
