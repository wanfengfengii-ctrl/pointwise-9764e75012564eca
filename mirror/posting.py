from ledger import transaction
from mirror.eligibility import check_eligibility
from mirror.facts import get_stream, record_applied_batch, write_current_facts
from mirror.install import install_bootstrap
from mirror.receipts import get_posting_receipt, save_posting_receipt
from receiving.pending import get_postable_delivery, mark_posted
from receiving.validation import validate_delivery


def post(connection, mirror, intake_id):
    with transaction(connection):
        stream = get_stream(connection, mirror)
        delivery = get_postable_delivery(connection, mirror, intake_id)
        existing = get_posting_receipt(connection, mirror, delivery['delivery_id'])
        if existing is not None:
            return {'status': 'posted', 'receipt': existing}

        envelope, document = validate_delivery(delivery['envelope'], stream)
        if envelope.kind == 'bootstrap':
            facts = install_bootstrap(connection, mirror, envelope, document)
        else:
            waiting_for = check_eligibility(connection, mirror, document)
            if waiting_for:
                return {'status': 'pending', 'receipt': None, 'waiting_for': waiting_for}
            facts = [change['after'] for change in document['changes']]
            write_current_facts(connection, mirror, facts)
            record_applied_batch(connection, mirror, document['batch'], document['sequence'],
                                 envelope.delivery_id)

        receipt = save_posting_receipt(connection, mirror, intake_id, envelope, document, facts)
        mark_posted(connection, mirror, intake_id)
        return {'status': 'posted', 'receipt': receipt}
