from mirror.facts import get_start, write_current_facts, write_start


def install_bootstrap(connection, mirror, envelope, document):
    if get_start(connection, mirror) is not None:
        raise ValueError('the mirror already has a fixed start')
    write_start(connection, mirror, document['batch'], document['sequence'], envelope.delivery_id)
    write_current_facts(connection, mirror, document['rows'])
    return document['rows']
