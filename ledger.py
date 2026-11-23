import json
from contextlib import contextmanager


MAX_INDEX = (1 << 63) - 1


def text_id(value, label):
    if not isinstance(value, str) or not value.strip() or '\x00' in value:
        raise ValueError(f'{label} must be nonempty text')
    try:
        value.encode('utf-8')
    except UnicodeEncodeError as error:
        raise ValueError(f'{label} must be valid Unicode') from error
    return value


def positive_index(value, label):
    if type(value) is not int or not 1 <= value <= MAX_INDEX:
        raise ValueError(f'{label} must be a positive SQLite integer')
    return value


def require_fields(value, fields, label):
    if not isinstance(value, dict) or value.keys() != set(fields):
        raise ValueError(f'invalid fields for {label}')
    return value


def require_items(value, label):
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError(f'{label} must be a nonempty sequence')
    return value


def canonical_json(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False)


@contextmanager
def transaction(connection, *, write=True):
    if connection.in_transaction:
        raise RuntimeError('a ledger operation requires a connection outside a transaction')
    connection.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
    try:
        yield
        connection.commit()
    except BaseException:
        connection.rollback()
        raise


def create_tables(connection, definitions):
    for definition in definitions:
        connection.execute(definition)
