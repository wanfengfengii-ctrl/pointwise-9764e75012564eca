import json

from ledger import canonical_json


def write_source_receipt(connection, stream, batch, sequence, kind):
    receipt = {
        'receipt_id': f'source:{batch}', 'stream': stream, 'batch': batch,
        'sequence': sequence, 'kind': kind,
    }
    connection.execute('INSERT INTO source_receipts (batch, body) VALUES (?, ?)',
                       (batch, canonical_json(receipt)))
    return receipt


def get_source_receipt(connection, batch):
    row = connection.execute('SELECT body FROM source_receipts WHERE batch = ?', (batch,)).fetchone()
    return json.loads(row[0]) if row is not None else None
