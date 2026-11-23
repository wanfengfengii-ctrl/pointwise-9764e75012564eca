import json

from ledger import canonical_json, create_tables, positive_index, transaction


_SOURCE_TABLES = (
    '''CREATE TABLE IF NOT EXISTS source_batches (
        batch TEXT PRIMARY KEY, stream TEXT NOT NULL, sequence INTEGER NOT NULL,
        kind TEXT NOT NULL CHECK(kind IN ('record', 'amend')), changes TEXT NOT NULL,
        UNIQUE(stream, sequence)
    )''',
    '''CREATE TABLE IF NOT EXISTS source_facts (
        stream TEXT NOT NULL, station TEXT NOT NULL, day TEXT NOT NULL,
        reading_id TEXT NOT NULL, row_order INTEGER NOT NULL, fact TEXT NOT NULL,
        PRIMARY KEY(stream, station, day, reading_id), UNIQUE(stream, row_order)
    )''',
    '''CREATE TABLE IF NOT EXISTS source_receipts (
        batch TEXT PRIMARY KEY, body TEXT NOT NULL
    )''',
)


def initialize_source_schema(connection):
    with transaction(connection):
        create_tables(connection, _SOURCE_TABLES)


def allocate_source_order(connection, stream, row_count):
    last_order, = connection.execute(
        'SELECT COALESCE(MAX(row_order), 0) FROM source_facts WHERE stream = ?', (stream,)
    ).fetchone()
    positive_index(last_order + row_count, 'last source row order')
    return range(last_order + 1, last_order + row_count + 1)


def next_sequence(connection, stream):
    latest, = connection.execute(
        'SELECT COALESCE(MAX(sequence), 0) FROM source_batches WHERE stream = ?', (stream,)
    ).fetchone()
    return positive_index(latest + 1, 'formal sequence')


def ensure_unused_batch(connection, batch):
    if get_formal_batch(connection, batch) is not None:
        raise ValueError(f'source batch already exists: {batch}')


def make_fact(key, order, batch, sequence, reading):
    return {'key': list(key), 'order': order, 'batch': batch, 'sequence': sequence, 'reading': reading}


def append_revision_batch(connection, stream, batch, sequence, kind, changes):
    connection.execute(
        'INSERT INTO source_batches (batch, stream, sequence, kind, changes) VALUES (?, ?, ?, ?, ?)',
        (batch, stream, sequence, kind, canonical_json(changes)),
    )
    facts = [change['after'] for change in changes]
    connection.executemany(
        '''INSERT INTO source_facts (stream, station, day, reading_id, row_order, fact)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(stream, station, day, reading_id) DO UPDATE SET fact = excluded.fact''',
        ((stream, *fact['key'], fact['order'], canonical_json(fact)) for fact in facts),
    )


def _decode_batch(row):
    batch, stream, sequence, kind, changes = row
    return {'batch': batch, 'stream': stream, 'sequence': sequence,
            'kind': kind, 'changes': json.loads(changes)}


def get_formal_batch(connection, batch):
    row = connection.execute(
        'SELECT batch, stream, sequence, kind, changes FROM source_batches WHERE batch = ?', (batch,)
    ).fetchone()
    return _decode_batch(row) if row is not None else None


def read_formal_history(connection, stream, through=None):
    rows = connection.execute(
        '''SELECT batch, stream, sequence, kind, changes FROM source_batches
           WHERE stream = ? AND (? IS NULL OR sequence <= ?) ORDER BY sequence''',
        (stream, through, through),
    )
    return [_decode_batch(row) for row in rows]


def get_current_facts(connection, stream):
    rows = connection.execute(
        'SELECT fact FROM source_facts WHERE stream = ? ORDER BY row_order', (stream,)
    )
    return [json.loads(fact) for fact, in rows]
