from mirror.facts import get_applied_batch, get_start, load_current_facts


def check_eligibility(connection, mirror, document):
    start = get_start(connection, mirror)
    if start is None:
        raise ValueError('install a bootstrap before posting changes')
    if document['sequence'] <= start['sequence']:
        raise ValueError('the correction is already covered by the mirror start')
    if get_applied_batch(connection, mirror, document['sequence']) is not None:
        raise ValueError('formal sequence already bound to an application')
    keys = [tuple(change['after']['key']) for change in document['changes']]
    facts = load_current_facts(connection, mirror, keys)
    waiting_for = []
    for key, change in zip(keys, document['changes'], strict=True):
        current = facts.get(key)
        if current is None or current['order'] != change['after']['order']:
            raise ValueError('the mirror start does not supply the required original fact')
        if current['sequence'] >= document['sequence']:
            raise ValueError('the correction precedes the current fact')
        reading = current['reading']
        before = change['before']
        if (reading['litres'], reading['missing']) != (before['litres'], before['missing']):
            waiting_for.append({'key': list(key)})
    return waiting_for
