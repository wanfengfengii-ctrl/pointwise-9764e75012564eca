import json
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from audit.daybook import read_day
from audit.history import receipt
from mirror.facts import initialize_mirror_schema
from mirror.posting import post
from publication.bootstrap import bootstrap
from publication.changes import issue
from publication.register import initialize_publication_schema
from receiving.inbox import receive
from receiving.pending import list_pending
from receiving.store import initialize_inbox_schema
from source.corrections import amend
from source.intake import record
from source.revisions import get_current_facts, initialize_source_schema


SAMPLE_DIRECTORY = Path(__file__).resolve().parent / 'samples'
MIRROR = '夜班'


def load_sample(filename):
    with (SAMPLE_DIRECTORY / filename).open(encoding='utf-8') as file:
        return json.load(file)


def issue_sample(source, sample):
    stream = sample['stream']
    start = sample['start_batch']
    record(source, stream, start, sample['rows'])
    material = {start: bootstrap(source, stream, start)}
    for amendment in sample['amendments']:
        current = {tuple(fact['key']): fact for fact in get_current_facts(source, stream)}
        changes = [{**update, 'before': current[tuple(update['key'])]} for update in amendment['updates']]
        batch = amendment['batch']
        amend(source, stream, batch, changes)
        material[batch] = issue(source, batch)
    return material


def show_scenario(case_id, scenario_input, expected, actual, downstream_expected,
                  downstream_actual, code_paths, oracle):
    if expected != actual or downstream_expected != downstream_actual:
        raise AssertionError(f'{case_id} mismatch: expected {expected, downstream_expected}, '
                             f'got {actual, downstream_actual}')
    result = dict(case_id=case_id, input=scenario_input, expected=expected, actual=actual,
                  downstream_expected=downstream_expected, downstream_actual=downstream_actual,
                  code_paths=code_paths, oracle=oracle)
    print('POINTWISE_SCENARIO ' + json.dumps(result, ensure_ascii=False, sort_keys=True))


def _read_book(connection, sample):
    return read_day(connection, MIRROR, sample['station'], sample['day'])


def _receive(connection, material):
    return receive(connection, MIRROR, material['envelope'])['intake_id']


def _open_day(connection, sample):
    book = _read_book(connection, sample)
    rows = [[row['key'][2], row['litres'], row['missing'], row['provenance']['origin']]
            for row in book['rows']]
    show_scenario('V1', sample['rows'], [['Z', 7, False, '晨班尺'], ['A', 0, False, '零量仪'],
                                       ['M', None, True, '未到表']], rows,
                  {'start': 'S', 'rows': 3, 'litres': 7},
                  {'start': book['start']['batch'], 'rows': book['row_count'], 'litres': book['total_litres']},
                  ['source/intake.py', 'publication/snapshots.py', 'mirror/install.py', 'audit/daybook.py',
                   'audit/totals.py'], '按输入顺序逐行抄核，实测 7 加 0，缺测只计行')


def _first_delivery(connection, sample, material):
    t2 = post(connection, MIRROR, _receive(connection, material['T2']))
    intake = _receive(connection, material['T3'])
    t3 = post(connection, MIRROR, intake)
    book = _read_book(connection, sample)
    try:
        t3_receipt = receipt(connection, MIRROR, material['T3']['receipt']['delivery_id'])
    except LookupError:
        t3_receipt = None
    actual = {
        'T2': t2['status'], 'T3': t3['status'], 'T3_has_receipt': t3_receipt is not None,
        'T3_in_pending': intake in {item['intake_id'] for item in list_pending(connection, MIRROR)},
    }
    show_scenario('V5', {'opening_rows': sample['rows'], 'amendments': sample['amendments'],
                         'arrivals': ['T2', 'T3']},
                  {'T2': 'posted', 'T3': 'pending', 'T3_has_receipt': False, 'T3_in_pending': True},
                  actual, {'litres': 15, 'origins': ['A初测', 'B复测']},
                  {'litres': book['total_litres'], 'origins': [r['provenance']['origin'] for r in book['rows']]},
                  ['publication/changes.py', 'receiving/inbox.py', 'mirror/eligibility.py',
                   'mirror/posting.py', 'audit/daybook.py', 'audit/history.py'],
                  'T2 只改 B，A 的前序 T1 尚未正式入账，手算 7 加 8')
    return intake


def _resume(connection, sample, material, intake):
    first = post(connection, MIRROR, _receive(connection, material['T1']))['receipt']
    result = post(connection, MIRROR, intake)
    book = _read_book(connection, sample)
    saved = receipt(connection, MIRROR, material['T1']['receipt']['delivery_id'])
    replay = post(connection, MIRROR, _receive(connection, material['T1']))['receipt']
    show_scenario('V6', {'reopened': True, 'new_arrival': 'T1', 'retry': 'T3'},
                  {'status': 'posted', 'original_receipt': True},
                  {'status': result['status'], 'original_receipt': first == saved == replay},
                  {'litres': 22, 'values': [13, 9], 'historical_origin': 'A复测'},
                  {'litres': book['total_litres'], 'values': [row['litres'] for row in book['rows']],
                   'historical_origin': saved['sources'][0]['origin']},
                  ['receiving/pending.py', 'mirror/posting.py', 'mirror/receipts.py',
                   'audit/daybook.py', 'audit/history.py'],
                  '前序正式入账后使用 T3 的两项后像，手算 13 加 9 并核对 T1 复测来源')


def _run_sample(directory, name):
    sample = load_sample(name)
    source_path = directory / 'source.sqlite'
    mirror_path = directory / 'mirror.sqlite'
    with closing(sqlite3.connect(source_path)) as source:
        initialize_source_schema(source)
        initialize_publication_schema(source)
        material = issue_sample(source, sample)
    with closing(sqlite3.connect(mirror_path)) as target:
        initialize_mirror_schema(target, MIRROR, sample['stream'])
        initialize_inbox_schema(target)
        start = post(target, MIRROR, _receive(target, material[sample['start_batch']]))
        if start['status'] != 'posted':
            raise AssertionError('the bootstrap did not install')
        if not sample['amendments']:
            _open_day(target, sample)
            return
        pending = _first_delivery(target, sample, material)
    with closing(sqlite3.connect(mirror_path)) as target:
        _resume(target, sample, material, pending)


def main():
    for filename in ('open_day.json', 'corrections.json'):
        with TemporaryDirectory(prefix='chenghe-daybook-') as directory:
            _run_sample(Path(directory), filename)


if __name__ == '__main__':
    main()
