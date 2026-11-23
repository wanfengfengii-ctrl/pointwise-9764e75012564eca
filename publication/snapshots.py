from source.revisions import get_formal_batch, read_formal_history


def build_snapshot(connection, stream, start_batch):
    anchor = get_formal_batch(connection, start_batch)
    if anchor is None or anchor['stream'] != stream:
        raise ValueError('unknown formal start for this source stream')
    facts = {}
    for batch in read_formal_history(connection, stream, through=anchor['sequence']):
        for revision in batch['changes']:
            fact = revision['after']
            facts[tuple(fact['key'])] = fact
    return {
        'batch': start_batch, 'sequence': anchor['sequence'],
        'rows': sorted(facts.values(), key=lambda fact: fact['order']),
    }
