import json

from ledger import canonical_json, transaction


def initialize_publication_schema(connection):
    with transaction(connection):
        connection.execute('''CREATE TABLE IF NOT EXISTS issuances (
            stream TEXT NOT NULL, kind TEXT NOT NULL, batch TEXT NOT NULL,
            delivery_id TEXT NOT NULL UNIQUE, envelope BLOB NOT NULL, receipt TEXT NOT NULL,
            PRIMARY KEY(stream, kind, batch)
        )''')


def find_issuance(connection, stream, kind, batch):
    row = connection.execute(
        'SELECT envelope, receipt FROM issuances WHERE stream = ? AND kind = ? AND batch = ?',
        (stream, kind, batch),
    ).fetchone()
    if row is None:
        return None
    envelope, receipt = row
    return {'envelope': envelope, 'receipt': json.loads(receipt)}


def store_issuance(connection, envelope, batch, sequence):
    payload = envelope.to_bytes()
    receipt = {
        'receipt_id': f'issue:{envelope.delivery_id}', 'delivery_id': envelope.delivery_id,
        'kind': envelope.kind, 'stream': envelope.stream, 'batch': batch,
        'sequence': sequence, 'digest': envelope.digest,
    }
    connection.execute(
        '''INSERT INTO issuances (stream, kind, batch, delivery_id, envelope, receipt)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (envelope.stream, envelope.kind, batch, envelope.delivery_id, payload, canonical_json(receipt)),
    )
    return {'envelope': payload, 'receipt': receipt}
