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


def get_s3_csv_file_info(
        path,
        custom_delimiter=None,
        custom_quote_char=None,
        custom_line_terminator=None
):
    client = get_s3_client()

    logger.debug(path)

    file = client.get_object(
        Bucket=settings.NOTEBOOKS_BUCKET, Key=path, Range="bytes=0-102400"
    )
    raw = file["Body"].read()

    def csv_reader_alt(source, delimiter, quote_char, line_terminator):
        reserved_delimiter = chr(255)
        reserved_quote_char = chr(128207)
        return csv.reader((
            line.replace(
                delimiter, reserved_delimiter
            ).replace(
                quote_char, reserved_quote_char
            ) for line in source
        ), delimiter=reserved_delimiter, quotechar=reserved_quote_char)

    encoding, decoded = _get_encoding_and_decoded_bytes(raw)

    delimiter = custom_delimiter if custom_delimiter else ','
    quote_char = custom_quote_char if custom_quote_char else '"'
    line_terminator = bytes(
        "".join(custom_line_terminator), "utf-8"
    ).decode("unicode_escape") if custom_line_terminator else ''

    logger.info(line_terminator)
    logger.info(delimiter)
    logger.info(quote_char)

    fh = StringIO(
        decoded.replace(
            '\r\n', ''
        ).replace(
            '\r', ''
        ).replace(
            '\n', ''
        ).replace(
            custom_line_terminator, '\n'
        ), newline='\n'
    ) if custom_line_terminator else StringIO(decoded, newline='')

    rows = list(csv_reader_alt(fh, delimiter, quote_char, line_terminator))
    return {
        "encoding": encoding,
        "column_definitions": _get_csv_column_types(rows)
    }


def _get_encoding_and_decoded_bytes(raw: bytes):

    try:
        encoding = "utf-8-sig"
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
