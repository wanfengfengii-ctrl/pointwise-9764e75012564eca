from audit.provenance import receipt_provenance
from ledger import text_id
from mirror.receipts import get_posting_receipt


def receipt(connection, mirror, delivery_id):
    text_id(mirror, 'mirror')
    text_id(delivery_id, 'delivery number')
    saved = get_posting_receipt(connection, mirror, delivery_id)
    if saved is None:
        raise LookupError(f'no successful posting receipt for delivery: {delivery_id}')
    return {**saved, 'sources': receipt_provenance(saved)}
