from ledger import require_fields, require_items, text_id, transaction
from source.observations import validate_fact, validate_fact_key, validate_observation
from source.receipts import write_source_receipt
from source.revisions import (
    append_revision_batch, ensure_unused_batch, get_current_facts, make_fact, next_sequence,
)


def check_before_images(current_facts, changes):
    current_by_key = {tuple(fact['key']): fact for fact in current_facts}
    seen = set()
    checked = []
    for change in require_items(changes, 'correction rows'):
        require_fields(change, ('key', 'before', 'after'), 'correction row')
        key = validate_fact_key(change['key'])
        if key in seen:
            raise ValueError(f'duplicate correction key: {key}')
        seen.add(key)
        before = validate_fact(change['before'])
        current = current_by_key.get(key)
        if current is None or current != before:
            raise ValueError(f'before image does not match the formal fact: {key}')
        checked.append((key, current, validate_observation(change['after'])))
    return checked


def amend(connection, stream, batch, changes):
    text_id(stream, 'source stream')
    text_id(batch, 'correction batch')
    with transaction(connection):
        ensure_unused_batch(connection, batch)
        current = get_current_facts(connection, stream)
        checked = check_before_images(current, changes)
        sequence = next_sequence(connection, stream)
        revisions = [
            {'before': before['reading'],
             'after': make_fact(key, before['order'], batch, sequence, reading)}
            for key, before, reading in checked
        ]
        append_revision_batch(connection, stream, batch, sequence, 'amend', revisions)
        return write_source_receipt(connection, stream, batch, sequence, 'amend')
