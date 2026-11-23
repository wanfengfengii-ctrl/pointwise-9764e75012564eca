import json

from ledger import canonical_json, positive_index, require_fields, require_items, text_id
from publication.envelope import decode_envelope, delivery_number
from source.observations import validate_fact


def _validate_unique(facts):
    keys = set()
    orders = set()
    for fact in facts:
        key = tuple(fact['key'])
        order = fact['order']
        if key in keys or order in orders:
            raise ValueError('duplicate fact key or source order in delivery')
        keys.add(key)
        orders.add(order)


def _validate_snapshot(rows, batch, sequence):
    facts = [validate_fact(row) for row in require_items(rows, 'bootstrap rows')]
    _validate_unique(facts)
    orders = [fact['order'] for fact in facts]
    if orders != sorted(orders):
        raise ValueError('bootstrap rows must be in source order')
    for fact in facts:
        if fact['sequence'] > sequence or (fact['sequence'] == sequence) != (fact['batch'] == batch):
            raise ValueError('bootstrap row is outside the stated formal start')


def _validate_changes(rows, batch, sequence):
    facts = []
    for change in require_items(rows, 'change rows'):
        require_fields(change, ('before', 'after'), 'transport correction')
        before = validate_fact(change['before'])
        fact = validate_fact(change['after'])
        if fact['batch'] != batch or fact['sequence'] != sequence:
            raise ValueError('after image does not belong to the stated formal batch')
        if before['key'] != fact['key'] or before['order'] != fact['order']:
            raise ValueError('before image does not match the corrected fact')
        if before['sequence'] >= sequence:
            raise ValueError('before image is outside the stated formal history')
        facts.append(fact)
    _validate_unique(facts)


def validate_document(kind, document):
    if kind == 'bootstrap':
        require_fields(document, ('batch', 'sequence', 'rows'), 'bootstrap body')
    elif kind == 'change':
        require_fields(document, ('batch', 'sequence', 'changes'), 'change body')
    else:
        raise ValueError('unknown delivery kind')
    batch = text_id(document['batch'], 'document batch')
    sequence = positive_index(document['sequence'], 'document sequence')
    if kind == 'bootstrap':
        _validate_snapshot(document['rows'], batch, sequence)
    else:
        _validate_changes(document['changes'], batch, sequence)
    return document


def validate_delivery(payload, expected_stream):
    envelope = decode_envelope(payload)
    if envelope.stream != expected_stream:
        raise ValueError('delivery belongs to another source stream')
    try:
        document = json.loads(envelope.body)
        if envelope.body != canonical_json(document):
            raise ValueError('body is not in frozen form')
    except (ValueError, RecursionError) as error:
        raise ValueError('invalid frozen body JSON') from error
    validate_document(envelope.kind, document)
    if envelope.delivery_id != delivery_number(envelope.kind, envelope.stream, document['batch']):
        raise ValueError('delivery number does not bind this formal batch')
    return envelope, document
