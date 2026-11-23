from audit.provenance import row_provenance
from audit.totals import summarize_day
from ledger import text_id, transaction
from mirror.facts import get_start, read_day_facts
from source.observations import validate_station_day


def read_day(connection, mirror, station, day):
    text_id(mirror, 'mirror')
    validate_station_day(station, day)
    with transaction(connection, write=False):
        start = get_start(connection, mirror)
        if start is None:
            raise ValueError('mirror is not installed')
        facts = read_day_facts(connection, mirror, station, day)
    rows = [
        {'key': fact['key'], 'order': fact['order'], 'litres': fact['reading']['litres'],
         'missing': fact['reading']['missing'], 'provenance': row_provenance(fact)}
        for fact in facts
    ]
    return {'start': start, 'station': station, 'day': day, 'rows': rows, **summarize_day(rows)}
