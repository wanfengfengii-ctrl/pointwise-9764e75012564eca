from ledger import text_id, transaction
from publication.envelope import delivery_number, freeze_envelope
from publication.register import find_issuance, store_issuance
from source.revisions import get_formal_batch


def build_change_document(_connection, formal_batch):
    changes = []
    for change in formal_batch['changes']:
        reading = change['before']
        changes.append({
            'before': {'litres': reading['litres'], 'missing': reading['missing']},
            'after': change['after'],
        })
    return {'batch': formal_batch['batch'], 'sequence': formal_batch['sequence'], 'changes': changes}


def issue(connection, batch):
    text_id(batch, 'correction batch')
    with transaction(connection):
        formal = get_formal_batch(connection, batch)
        if formal is None or formal['kind'] != 'amend':
            raise ValueError('issuance requires a formally committed correction batch')
        stream = formal['stream']
        existing = find_issuance(connection, stream, 'change', batch)
        if existing is not None:
            return existing
        document = build_change_document(connection, formal)
        delivery_id = delivery_number('change', stream, batch)
        envelope = freeze_envelope('change', stream, delivery_id, document)
        return store_issuance(connection, envelope, batch, formal['sequence'])
