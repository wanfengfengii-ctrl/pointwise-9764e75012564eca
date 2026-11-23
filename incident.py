import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from audit.daybook import read_day
from audit.history import receipt
from demo import MIRROR, issue_sample, load_sample
from mirror.facts import initialize_mirror_schema
from mirror.posting import post
from publication.register import initialize_publication_schema
from receiving.inbox import receive
from receiving.pending import list_pending
from receiving.store import initialize_inbox_schema
from source.revisions import initialize_source_schema


def issue_material(source, sample, *, unrelated):
    if unrelated:
        row = sample['rows'][2]
        sample['amendments'][0]['updates'] = [
            {'key': row['key'], 'after': {'litres': 11, 'missing': False, 'origin': 'C复测'}}
        ]
    initialize_source_schema(source)
    initialize_publication_schema(source)
    return issue_sample(source, sample)


def observe(target, sample, material):
    initialize_mirror_schema(target, MIRROR, sample['stream'])
    initialize_inbox_schema(target)
    results = {}
    for batch in ('S', 'T2', 'T3'):
        accepted = receive(target, MIRROR, material[batch]['envelope'])
        results[batch] = post(target, MIRROR, accepted['intake_id'])['status']
    delivery = material['T3']['receipt']['delivery_id']
    try:
        receipt(target, MIRROR, delivery)
    except LookupError:
        has_receipt = False
    else:
        has_receipt = True
    daybook = read_day(target, MIRROR, sample['station'], sample['day'])
    return {'S': results['S'], 'T2': results['T2'], 'T3': results['T3'],
            'rows': [row['litres'] for row in daybook['rows']], 'total': daybook['total_litres'],
            'receipt': has_receipt,
            'pending': any(item['delivery_id'] == delivery for item in list_pending(target, MIRROR))}


def check_issued(materials):
    same = materials['A']['T3']['envelope'] == materials['C']['T3']['envelope']
    print(f'T3 transport bytes identical for the two histories: {same}')
    if same:
        print('CHENGHE_HISTORY_COLLISION: T3 is indistinguishable when the missing batch changes A or C')
    return not same


def check_posted(results):
    waiting = {'S': 'posted', 'T2': 'posted', 'T3': 'pending', 'rows': [7, 8],
               'total': 15, 'receipt': False, 'pending': True}
    done = {'S': 'posted', 'T2': 'posted', 'T3': 'posted', 'rows': [13, 9],
            'total': 22, 'receipt': True, 'pending': False}
    print(json.dumps({'actual': results, 'expected': {'A': waiting, 'C': done}}, sort_keys=True))
    if results['A'] == done:
        print('CHENGHE_T3_PREMATURE_POST: missing A batch T1, T3 receipt issued, total=22 L; expected pending, 15 L')
    return results == {'A': waiting, 'C': done}


def main():
    parser = argparse.ArgumentParser(description='Compare two offline daybook histories')
    parser.add_argument('case', nargs='?', default='all', choices=('all', 'issue', 'post'))
    case = parser.parse_args().case
    with TemporaryDirectory(prefix='chenghe-incident-') as work:
        directory = Path(work)
        samples = {key: load_sample('corrections.json') for key in ('A', 'C')}
        materials = {}
        for key, sample in samples.items():
            with closing(sqlite3.connect(directory / f'source-{key}.sqlite')) as source:
                materials[key] = issue_material(source, sample, unrelated=key == 'C')
        issue_ok = case == 'post' or check_issued(materials)
        if case == 'issue':
            return int(not issue_ok)
        results = {}
        for key, sample in samples.items():
            with closing(sqlite3.connect(directory / f'mirror-{key}.sqlite')) as target:
                results[key] = observe(target, sample, materials[key])
        post_ok = check_posted(results)
        return int(not (issue_ok and post_ok))


if __name__ == '__main__':
    raise SystemExit(main())
