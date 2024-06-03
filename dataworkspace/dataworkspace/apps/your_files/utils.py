import csv
import logging
from io import StringIO

from django.conf import settings
from tableschema import Schema

from dataworkspace.apps.core.boto3_client import get_s3_client
from dataworkspace.apps.core.constants import (
    PostgresDataTypes,
    SCHEMA_POSTGRES_DATA_TYPE_MAP,
    TABLESCHEMA_FIELD_TYPE_MAP,
)
from dataworkspace.apps.core.utils import (
    USER_SCHEMA_STEM,
    clean_db_column_name,
    db_role_schema_suffix_for_user,
)

logger = logging.getLogger("app")


def get_s3_csv_file_info(path):
    client = get_s3_client()

    logger.debug(path)

    file = client.get_object(Bucket=settings.NOTEBOOKS_BUCKET, Key=path, Range="bytes=0-102400")
    raw = file["Body"].read()

    encoding, decoded = _get_encoding_and_decoded_bytes(raw)

    fh = StringIO(decoded, newline="")
    rows = list(csv.reader(fh, delimiter='|', text_qualifier='"'))

    return {"encoding": encoding, "column_definitions": _get_csv_column_types(rows)}


def _get_encoding_and_decoded_bytes(raw: bytes):
    encoding = "utf-8-sig"

    try:
        decoded = raw.decode(encoding)
        return encoding, decoded
    except UnicodeDecodeError:
        pass

    try:
        encoding = "cp1252"
        decoded = raw.decode(encoding)
        return encoding, decoded
    except UnicodeDecodeError:
        pass

    # fall back of last resort will decode most things
    # https://docs.python.org/3/library/codecs.html#error-handlers
    encoding = "latin1"
    decoded = raw.decode(encoding, errors="replace")

    return encoding, decoded


def _get_csv_column_types(rows):
    if len(rows) <= 2:
        raise ValueError("Unable to read enough lines of data from file")

    # Drop the last line, which might be incomplete
    del rows[-1]

    # Pare down to a max of 10 lines so that inferring datatypes is quicker
    del rows[10:]

    schema = Schema()
    schema.infer(rows, confidence=1, headers=1)

    fields = []
    for idx, field in enumerate(schema.descriptor["fields"]):
        fields.append(
            {
                "header_name": field["name"],
                "column_name": clean_db_column_name(field["name"]),
                "data_type": SCHEMA_POSTGRES_DATA_TYPE_MAP.get(
                    TABLESCHEMA_FIELD_TYPE_MAP.get(field["type"], field["type"]),
                    PostgresDataTypes.TEXT,
                ),
                "sample_data": [row[idx] for row in rows][:6],
            }
        )

    return fields


def get_user_schema(request):
    return f"{USER_SCHEMA_STEM}{db_role_schema_suffix_for_user(request.user)}"


def get_schema_for_user(user):
    return f"{USER_SCHEMA_STEM}{db_role_schema_suffix_for_user(user)}"
