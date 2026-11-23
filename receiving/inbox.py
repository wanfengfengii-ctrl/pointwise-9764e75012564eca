from ledger import transaction
from mirror.facts import get_stream
from receiving.duplicates import resolve_redelivery
from receiving.store import insert_delivery
from receiving.validation import validate_delivery


def receive(connection, mirror, payload):
    with transaction(connection):
        expected_stream = get_stream(connection, mirror)
        envelope, _ = validate_delivery(payload, expected_stream)
        existing = resolve_redelivery(connection, mirror, envelope)
        if existing is not None:
            return existing
        return insert_delivery(connection, mirror, envelope)
