import json

from ledger import canonical_json, create_tables, text_id, transaction


_MIRROR_TABLES = (
    '''CREATE TABLE IF NOT EXISTS mirror_targets (
        mirror TEXT PRIMARY KEY, stream TEXT NOT NULL
    )''',
    '''CREATE TABLE IF NOT EXISTS mirror_starts (
        mirror TEXT PRIMARY KEY, batch TEXT NOT NULL, sequence INTEGER NOT NULL,
        delivery_id TEXT NOT NULL
    )''',
    '''CREATE TABLE IF NOT EXISTS mirror_facts (
        mirror TEXT NOT NULL, station TEXT NOT NULL, day TEXT NOT NULL, reading_id TEXT NOT NULL,
        row_order INTEGER NOT NULL, fact TEXT NOT NULL,
        PRIMARY KEY(mirror, station, day, reading_id), UNIQUE(mirror, row_order)
    )''',
    '''CREATE INDEX IF NOT EXISTS mirror_station_day_order
       ON mirror_facts (mirror, station, day, row_order)''',
    '''CREATE TABLE IF NOT EXISTS applied_batches (
        mirror TEXT NOT NULL, sequence INTEGER NOT NULL, batch TEXT NOT NULL, delivery_id TEXT NOT NULL,
        PRIMARY KEY(mirror, sequence), UNIQUE(mirror, batch), UNIQUE(mirror, delivery_id)
    )''',
    '''CREATE TABLE IF NOT EXISTS posting_receipts (
        mirror TEXT NOT NULL, delivery_id TEXT NOT NULL, receipt TEXT NOT NULL,
        PRIMARY KEY(mirror, delivery_id)
    )''',
)


def initialize_mirror_schema(connection, mirror, stream):
    text_id(mirror, 'mirror')
    text_id(stream, 'source stream')
    with transaction(connection):
        create_tables(connection, _MIRROR_TABLES)
        connection.execute('INSERT OR IGNORE INTO mirror_targets (mirror, stream) VALUES (?, ?)',
                           (mirror, stream))
        if get_stream(connection, mirror) != stream:
            raise ValueError('mirror is already configured for another source stream')


def get_stream(connection, mirror):
    text_id(mirror, 'mirror')
    row = connection.execute('SELECT stream FROM mirror_targets WHERE mirror = ?', (mirror,)).fetchone()
    if row is None:
        raise ValueError('mirror has not been configured')
    return row[0]


def get_start(connection, mirror):
    row = connection.execute(
        '''SELECT targets.stream, starts.batch, starts.sequence, starts.delivery_id
           FROM mirror_starts AS starts JOIN mirror_targets AS targets USING (mirror)
           WHERE starts.mirror = ?''', (mirror,),
    ).fetchone()
    if row is None:
        return None
    stream, batch, sequence, delivery_id = row
    return {'stream': stream, 'batch': batch, 'sequence': sequence, 'delivery_id': delivery_id}


def write_start(connection, mirror, batch, sequence, delivery_id):
    connection.execute(
        'INSERT INTO mirror_starts (mirror, batch, sequence, delivery_id) VALUES (?, ?, ?, ?)',
        (mirror, batch, sequence, delivery_id),
    )


def load_current_facts(connection, mirror, keys):
    current = {}
    for key in keys:
        row = connection.execute(
            '''SELECT fact FROM mirror_facts
               WHERE mirror = ? AND station = ? AND day = ? AND reading_id = ?''', (mirror, *key),
        ).fetchone()
        if row is not None:
            current[tuple(key)] = json.loads(row[0])
    return current


def read_day_facts(connection, mirror, station, day):
    rows = connection.execute(
        '''SELECT fact FROM mirror_facts WHERE mirror = ? AND station = ? AND day = ?
           ORDER BY row_order''', (mirror, station, day),
    )
    return [json.loads(fact) for fact, in rows]


def write_current_facts(connection, mirror, facts):
    connection.executemany(
        '''INSERT INTO mirror_facts (mirror, station, day, reading_id, row_order, fact)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(mirror, station, day, reading_id) DO UPDATE SET fact = excluded.fact''',
        ((mirror, *fact['key'], fact['order'], canonical_json(fact)) for fact in facts),
    )


def get_applied_batch(connection, mirror, sequence):
    row = connection.execute(
        'SELECT batch, delivery_id FROM applied_batches WHERE mirror = ? AND sequence = ?',
        (mirror, sequence),
    ).fetchone()
    if row is None:
        return None
    batch, delivery_id = row
    return {'batch': batch, 'delivery_id': delivery_id, 'sequence': sequence}


def record_applied_batch(connection, mirror, batch, sequence, delivery_id):
    connection.execute(
        'INSERT INTO applied_batches (mirror, sequence, batch, delivery_id) VALUES (?, ?, ?, ?)',
        (mirror, sequence, batch, delivery_id),
    )
