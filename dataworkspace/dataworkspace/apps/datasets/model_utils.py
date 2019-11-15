from contextlib import contextmanager

from dataworkspace.apps.datasets.constants import (
    LINKED_FIELD_DISPLAY_NAME,
    LINKED_FIELD_IDENTIFIER,
)


@contextmanager
def external_model_class(model_class):
    """
    Remove any related `reference_dataset` fields from a reference dataset record
    model class temporarily.
    This allows for saving records in external databases without referencing local tables.
    :param model_class:
    :return:
    """

    def clean_fields(fields):
        return [field for field in fields if field.name != 'reference_dataset']

    local_fields = model_class._meta.local_fields
    model_class._meta.local_fields = clean_fields(local_fields)

    local_concrete_fields = model_class._meta.local_concrete_fields
    model_class._meta.local_concrete_fields = clean_fields(local_concrete_fields)

    yield model_class

    model_class._meta.local_fields = local_fields
    model_class._meta.local_concrete_fields = local_concrete_fields


def has_circular_link(target_dataset, linked_dataset):
    """
    Determine if a reference dataset `linked_dataset` links back to `target_dataset` via
    linked reference dataset fields
    :param target_dataset:
    :param linked_dataset:
    :return:
    """
    links = [linked_dataset]
    checked = []
    while links:
        linked = links.pop()
        if linked == target_dataset:
            return True
        checked.append(linked)
        links = set(
            x.linked_reference_dataset
            for x in linked.fields.exclude(linked_reference_dataset=None)
            if x.linked_reference_dataset not in checked
        )
    return False


def get_linked_field_name(field, field_type):
    linked_reference_dataset = field.linked_reference_dataset
    if not linked_reference_dataset:
        return field.name
    if field_type == LINKED_FIELD_IDENTIFIER:
        if linked_reference_dataset.identifier_field:
            return f'{field.name}: {linked_reference_dataset.identifier_field.name}'
    elif field_type == LINKED_FIELD_DISPLAY_NAME:
        if linked_reference_dataset.display_name_field:
            return f'{field.name}: {linked_reference_dataset.display_name_field.name}'
    return field.name


def get_linked_field_identifier_name(field):
    return get_linked_field_name(field, LINKED_FIELD_IDENTIFIER)


def get_linked_field_display_name(field):
    return get_linked_field_name(field, LINKED_FIELD_DISPLAY_NAME)
