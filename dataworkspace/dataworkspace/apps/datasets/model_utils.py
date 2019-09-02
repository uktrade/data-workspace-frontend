from contextlib import contextmanager


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
        return [
            field for field in fields if field.name != 'reference_dataset'
        ]

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
            x.linked_reference_dataset for x in
            linked.fields.exclude(linked_reference_dataset=None)
            if x.linked_reference_dataset not in checked
        )
    return False
