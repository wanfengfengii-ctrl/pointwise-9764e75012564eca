import json

from audit.provenance import row_provenance
from ledger import canonical_json


def save_posting_receipt(connection, mirror, intake_id, envelope, document, facts):
    sources = [row_provenance(fact) for fact in sorted(facts, key=lambda row: row['order'])]
    receipt = {
        'receipt_id': f'post:{intake_id}', 'intake_id': intake_id, 'mirror': mirror,
        'delivery_id': envelope.delivery_id, 'kind': envelope.kind, 'stream': envelope.stream,
        'batch': document['batch'], 'sequence': document['sequence'], 'sources': sources,
    }
    connection.execute('INSERT INTO posting_receipts (mirror, delivery_id, receipt) VALUES (?, ?, ?)',
                       (mirror, envelope.delivery_id, canonical_json(receipt)))
    return receipt


def get_posting_receipt(connection, mirror, delivery_id):
    row = connection.execute(
        'SELECT receipt FROM posting_receipts WHERE mirror = ? AND delivery_id = ?',
        (mirror, delivery_id),
    ).fetchone()
    return json.loads(row[0]) if row is not None else None
