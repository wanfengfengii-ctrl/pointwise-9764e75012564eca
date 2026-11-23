from ledger import create_tables, transaction


_INBOX_TABLES = (
    '''CREATE TABLE IF NOT EXISTS inbox (
        intake_id INTEGER PRIMARY KEY, mirror TEXT NOT NULL, delivery_id TEXT NOT NULL,
        envelope BLOB NOT NULL, pending INTEGER NOT NULL CHECK(pending IN (0, 1)),
        UNIQUE(mirror, delivery_id)
    )''',
    'CREATE INDEX IF NOT EXISTS inbox_pending ON inbox (mirror, pending, intake_id)',
)


def initialize_inbox_schema(connection):
    with transaction(connection):
        create_tables(connection, _INBOX_TABLES)


def _decode_row(row):
    if row is None:
        return None
    intake_id, mirror, delivery_id, envelope, pending = row
    return {'intake_id': intake_id, 'mirror': mirror, 'delivery_id': delivery_id,
            'envelope': envelope, 'pending': bool(pending)}


def intake_result(record):
    return {name: record[name] for name in ('intake_id', 'mirror', 'delivery_id', 'pending')}


def find_delivery(connection, mirror, delivery_id):
    row = connection.execute(
        '''SELECT intake_id, mirror, delivery_id, envelope, pending FROM inbox
           WHERE mirror = ? AND delivery_id = ?''', (mirror, delivery_id),
    ).fetchone()
    return _decode_row(row)


def get_delivery(connection, mirror, intake_id):
    row = connection.execute(
        '''SELECT intake_id, mirror, delivery_id, envelope, pending FROM inbox
           WHERE mirror = ? AND intake_id = ?''', (mirror, intake_id),
    ).fetchone()
    return _decode_row(row)


def insert_delivery(connection, mirror, envelope):
    cursor = connection.execute(
        'INSERT INTO inbox (mirror, delivery_id, envelope, pending) VALUES (?, ?, ?, 1)',
        (mirror, envelope.delivery_id, envelope.to_bytes()),
    )
    return {'intake_id': cursor.lastrowid, 'mirror': mirror,
            'delivery_id': envelope.delivery_id, 'pending': True}


def fetch_pending(connection, mirror):
    rows = connection.execute(
        '''SELECT intake_id, mirror, delivery_id, envelope, pending FROM inbox
           WHERE mirror = ? AND pending = 1 ORDER BY intake_id''', (mirror,),
    )
    return [intake_result(_decode_row(row)) for row in rows]


def close_delivery(connection, mirror, intake_id):
    cursor = connection.execute(
        'UPDATE inbox SET pending = 0 WHERE mirror = ? AND intake_id = ? AND pending = 1',
        (mirror, intake_id),
    )
    if cursor.rowcount != 1:
        raise ValueError('only pending deliveries can be marked posted')
