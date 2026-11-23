from dataclasses import dataclass
from datetime import date

from ledger import positive_index, require_fields, text_id


@dataclass(frozen=True)
class Observation:
    litres: int | None
    missing: bool
    origin: str

    def __post_init__(self):
        validate_measurement(self.litres, self.missing)
        text_id(self.origin, 'observation origin')

    def as_dict(self):
        return {'litres': self.litres, 'missing': self.missing, 'origin': self.origin}


def validate_measurement(litres, missing):
    if type(missing) is not bool:
        raise ValueError('missing must be a boolean')
    if missing:
        if litres is not None:
            raise ValueError('a missing observation must have null litres')
    elif type(litres) is not int or litres < 0:
        raise ValueError('a measured observation requires nonnegative integer litres')


def validate_observation(value):
    if isinstance(value, Observation):
        return value.as_dict()
    require_fields(value, ('litres', 'missing', 'origin'), 'observation')
    return Observation(**value).as_dict()


def validate_station_day(station, day):
    text_id(station, 'station')
    text_id(day, 'day')
    try:
        normalized = date.fromisoformat(day).isoformat()
    except ValueError as error:
        raise ValueError('day must be an ISO calendar date') from error
    if normalized != day:
        raise ValueError('day must be in YYYY-MM-DD form')
    return station, day


def validate_fact_key(value):
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        raise ValueError('a fact key contains station, day and observation ID')
    station, day, reading_id = value
    validate_station_day(station, day)
    text_id(reading_id, 'observation ID')
    return station, day, reading_id


def validate_fact(value):
    require_fields(value, ('key', 'order', 'sequence', 'batch', 'reading'), 'formal fact')
    return {
        'key': list(validate_fact_key(value['key'])),
        'order': positive_index(value['order'], 'source row order'),
        'sequence': positive_index(value['sequence'], 'formal sequence'),
        'batch': text_id(value['batch'], 'formal batch'),
        'reading': validate_observation(value['reading']),
    }
