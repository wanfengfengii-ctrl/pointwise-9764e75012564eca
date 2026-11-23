from ledger import require_fields, require_items, text_id, transaction
from source.observations import validate_fact_key, validate_observation
from source.receipts import write_source_receipt
from source.revisions import (
    allocate_source_order, append_revision_batch, ensure_unused_batch,
    get_current_facts, make_fact, next_sequence,
)


def _normalize_rows(rows):
    normalized = {}
    for row in require_items(rows, 'observation rows'):
        require_fields(row, ('key', 'reading'), 'observation row')
        key = validate_fact_key(row['key'])
        if key in normalized:
            raise ValueError(f'duplicate observation key: {key}')
        normalized[key] = validate_observation(row['reading'])
    return normalized


def record(connection, stream, batch, rows):
    text_id(stream, 'source stream')
    text_id(batch, 'source batch')
    normalized = _normalize_rows(rows)
    with transaction(connection):
        ensure_unused_batch(connection, batch)
        existing = {tuple(fact['key']) for fact in get_current_facts(connection, stream)}
        if existing.intersection(normalized):
            raise ValueError('an original observation key is already recorded')
        sequence = next_sequence(connection, stream)
        orders = allocate_source_order(connection, stream, len(normalized))
        changes = [
            {'before': None, 'after': make_fact(key, order, batch, sequence, reading)}
            for (key, reading), order in zip(normalized.items(), orders, strict=True)
        ]
        append_revision_batch(connection, stream, batch, sequence, 'record', changes)
        return write_source_receipt(connection, stream, batch, sequence, 'record')
