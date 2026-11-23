from ledger import text_id, transaction
from publication.envelope import delivery_number, freeze_envelope
from publication.register import find_issuance, store_issuance
from publication.snapshots import build_snapshot


def bootstrap(connection, stream, start_batch):
    text_id(stream, 'source stream')
    text_id(start_batch, 'start batch')
    with transaction(connection):
        existing = find_issuance(connection, stream, 'bootstrap', start_batch)
        if existing is not None:
            return existing
        document = build_snapshot(connection, stream, start_batch)
        delivery_id = delivery_number('bootstrap', stream, start_batch)
        envelope = freeze_envelope('bootstrap', stream, delivery_id, document)
        return store_issuance(connection, envelope, start_batch, document['sequence'])
