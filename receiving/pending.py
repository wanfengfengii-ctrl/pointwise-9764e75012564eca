from ledger import positive_index
from mirror.facts import get_stream
from receiving.store import close_delivery, fetch_pending, get_delivery


def list_pending(connection, mirror):
    get_stream(connection, mirror)
    return fetch_pending(connection, mirror)


def get_postable_delivery(connection, mirror, intake_id):
    positive_index(intake_id, 'intake ID')
    delivery = get_delivery(connection, mirror, intake_id)
    if delivery is None:
        raise LookupError(f'unknown intake ID for mirror: {intake_id}')
    return delivery


def mark_posted(connection, mirror, intake_id):
    close_delivery(connection, mirror, intake_id)
