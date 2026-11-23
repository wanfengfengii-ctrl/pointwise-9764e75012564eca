def row_provenance(fact):
    return {'key': list(fact['key']), 'batch': fact['batch'], 'sequence': fact['sequence'],
            'origin': fact['reading']['origin']}


def receipt_provenance(posting_receipt):
    return [{**source, 'key': list(source['key'])} for source in posting_receipt['sources']]
