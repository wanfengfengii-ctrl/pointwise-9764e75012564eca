from receiving.store import find_delivery, intake_result


def resolve_redelivery(connection, mirror, envelope):
    existing = find_delivery(connection, mirror, envelope.delivery_id)
    if existing is None:
        return None
    if existing['envelope'] != envelope.to_bytes():
        raise ValueError('same delivery number is already bound to different material')
    return intake_result(existing)
