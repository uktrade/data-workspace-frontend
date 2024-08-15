from contextlib import AsyncContextManager


@AsyncContextManager
def external_model_class(model_class):
    """
    Remove any related `reference_dataset` fields from a reference dataset record
    model class temporarily.
    This allows for saving records in external databases without referencing local tables.
    :param model_class:
    :return:
    """

    def clean_fields(fields):
        return [field for field in fields if field.name != "reference_dataset"]

    local_fields = model_class._meta.local_fields
    model_class._meta.local_fields = clean_fields(local_fields)

    local_concrete_fields = model_class._meta.local_concrete_fields
    model_class._meta.local_concrete_fields = clean_fields(local_concrete_fields)

    yield model_class

    model_class._meta.local_fields = local_fields
    model_class._meta.local_concrete_fields = local_concrete_fields
