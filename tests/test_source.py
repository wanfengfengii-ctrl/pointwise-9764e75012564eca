import copy
import sqlite3

from demo import load_sample
from publication.changes import issue
from source.corrections import amend
from source.intake import record
from source.observations import Observation
from source.receipts import get_source_receipt
from source.revisions import get_current_facts, get_formal_batch, read_formal_history
from tests.support import DAY, STATION, STREAM, ProjectCase, correction


class SourceTests(ProjectCase):
    def _start(self):
        source = self.source()
        initial = record(source, STREAM, 'S', load_sample('corrections.json')['rows'])
        return source, initial

    def test_reject_partial_amendment(self):
        source, initial = self._start()
        before = get_current_facts(source, STREAM)
        history = read_formal_history(source, STREAM)
        good = correction(source, 'A', 13, 'A联核')
        bad = correction(source, 'B', 9, 'B联核')
        bad['before']['reading']['litres'] = 99
        with self.assertRaisesRegex(ValueError, 'before image'):
            amend(source, STREAM, 'BAD', [good, bad])
        self.assertEqual(get_current_facts(source, STREAM), before)
        self.assertEqual(read_formal_history(source, STREAM), history)
        self.assertEqual(get_source_receipt(source, 'S'), initial)
        self.assertIsNone(get_source_receipt(source, 'BAD'))
        with self.assertRaisesRegex(ValueError, 'formally committed correction'):
            issue(source, 'BAD')

    def test_equal_value_commit(self):
        source, initial = self._start()
        old = get_current_facts(source, STREAM)[0]
        result = amend(source, STREAM, 'T1', [correction(source, 'A', 7, 'A复测')])
        transaction = get_formal_batch(source, 'T1')
        new = get_current_facts(source, STREAM)[0]
        self.assertEqual([batch['batch'] for batch in read_formal_history(source, STREAM)], ['S', 'T1'])
        self.assertEqual(result['sequence'], initial['sequence'] + 1)
        self.assertEqual(transaction['changes'][0]['before'], old['reading'])
        self.assertEqual(transaction['changes'][0]['after'], new)
        self.assertEqual((old['order'], new['order']), (1, 1))
        self.assertEqual((old['reading']['litres'], new['reading']['litres']), (7, 7))
        self.assertEqual((old['reading']['origin'], new['reading']['origin']), ('A初测', 'A复测'))
        self.assertEqual(get_source_receipt(source, 'T1'), result)
        self.assertNotEqual(initial['receipt_id'], result['receipt_id'])

    def test_duplicate_key_and_stale_equal_value(self):
        source, _ = self._start()
        change = correction(source, 'A', 7, 'A复测')
        with self.assertRaisesRegex(ValueError, 'duplicate correction key'):
            amend(source, STREAM, 'DUP', [change, change])
        self.assertIsNone(get_formal_batch(source, 'DUP'))
        amend(source, STREAM, 'T1', [change])
        with self.assertRaisesRegex(ValueError, 'before image'):
            amend(source, STREAM, 'STALE', [change])
        self.assertIsNone(get_source_receipt(source, 'STALE'))

    def test_bad_record_and_source_initialization(self):
        source, initial = self._start()
        amend(source, STREAM, 'T1', [correction(source, 'A', 7, 'A复测')])
        original = get_current_facts(source, STREAM)
        source.close()
        source = self.source()
        self.assertEqual(get_current_facts(source, STREAM), original)
        self.assertEqual(get_source_receipt(source, 'S'), initial)
        self.assertEqual(get_source_receipt(source, 'T1')['sequence'], 2)
        base = {'key': [STATION, DAY, 'D'], 'reading': {'litres': 0, 'missing': False, 'origin': '增测'}}
        for litres, missing in ((True, False), (-1, False), (0, True), (None, False), (1.0, False)):
            with self.subTest(litres=litres, missing=missing):
                invalid = copy.deepcopy(base)
                invalid['reading'].update(litres=litres, missing=missing)
                with self.assertRaises(ValueError):
                    record(source, STREAM, 'BAD', [base, invalid | {'key': [STATION, DAY, 'E']}])
        with self.assertRaisesRegex(ValueError, 'duplicate observation key'):
            record(source, STREAM, 'BAD', [base, base])
        with self.assertRaisesRegex(ValueError, 'already recorded'):
            record(source, STREAM, 'BAD', [load_sample('corrections.json')['rows'][0]])
        self.assertIsNone(get_formal_batch(source, 'BAD'))
        self.assertEqual(get_current_facts(source, STREAM), original)
        next_receipt = record(source, STREAM, 'NEW', [{**base, 'reading': Observation(0, False, '增测')}])
        self.assertEqual(next_receipt['sequence'], 3)
        self.assertEqual(get_current_facts(source, STREAM)[-1]['order'], 4)

    def test_issue_rejected_or_aborted_batches(self):
        source, _ = self._start()
        original = get_current_facts(source, STREAM)
        source.execute('''CREATE TEMP TRIGGER reject_source_receipt
            BEFORE INSERT ON source_receipts WHEN NEW.batch = 'ABORT'
            BEGIN SELECT RAISE(ABORT, 'fixture source failure'); END''')
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'fixture source failure'):
            amend(source, STREAM, 'ABORT', [correction(source, 'A', 8, '新尺')])
        self.assertEqual(get_current_facts(source, STREAM), original)
        self.assertIsNone(get_formal_batch(source, 'ABORT'))
        self.assertIsNone(get_source_receipt(source, 'ABORT'))
        for number in ('S', 'ABORT', 'UNKNOWN'):
            with self.subTest(batch=number), self.assertRaises(ValueError):
                issue(source, number)
