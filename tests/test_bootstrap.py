from demo import issue_sample, load_sample
from mirror.facts import initialize_mirror_schema
from mirror.posting import post
from publication.bootstrap import bootstrap
from receiving.pending import list_pending
from source.corrections import amend
from source.intake import record
from tests.support import MIRROR, STREAM, ProjectCase, correction


class BaselineTests(ProjectCase):
    def test_open_day(self):
        source = self.source()
        material = issue_sample(source, load_sample('open_day.json'))
        source.close()
        target = self.mirror()
        self.install_start(target, material)
        self.assert_book(target, [7, 0, None], ['晨班尺', '零量仪', '未到表'], 7)
        book = self.book(target)
        self.assertEqual(book['start']['batch'], 'S')
        self.assertEqual([row['key'][2] for row in book['rows']], ['Z', 'A', 'M'])
        self.assertEqual([row['order'] for row in book['rows']], [1, 2, 3])
        self.assertEqual([row['missing'] for row in book['rows']], [False, False, True])
        self.assertEqual([row['provenance']['batch'] for row in book['rows']], ['S', 'S', 'S'])
        self.assertEqual(list_pending(target, MIRROR), [])

    def test_historical_start(self):
        source = self.source()
        sample = load_sample('open_day.json')
        record(source, STREAM, 'S', sample['rows'])
        amend(source, STREAM, 'LATE', [correction(source, 'Z', 11, '后来尺')])
        original = bootstrap(source, STREAM, 'S')
        newer = bootstrap(source, STREAM, 'LATE')
        source.close()
        old_target = self.mirror('old')
        new_target = self.mirror('new')
        self.install_start(old_target, {'S': original})
        self.assertEqual(self.book(old_target)['start']['batch'], 'S')
        self.assert_book(old_target, [7, 0, None], ['晨班尺', '零量仪', '未到表'], 7)
        self.deliver(new_target, {'LATE': newer}, 'LATE')
        self.assert_book(new_target, [11, 0, None], ['后来尺', '零量仪', '未到表'], 11)
        self.assertEqual(self.book(new_target)['rows'][0]['provenance']['batch'], 'LATE')

    def test_unknown_start_same_bootstrap_and_wrong_start(self):
        source = self.source()
        material = issue_sample(source, load_sample('open_day.json'))
        with self.assertRaises(ValueError):
            bootstrap(source, STREAM, 'UNKNOWN')
        with self.assertRaises(ValueError):
            bootstrap(source, 'another-stream', 'S')
        amend(source, STREAM, 'LATE', [correction(source, 'Z', 11, '后来尺')])
        self.assertEqual(bootstrap(source, STREAM, 'S'), material['S'])
        material['LATE'] = bootstrap(source, STREAM, 'LATE')
        target = self.mirror()
        first = self.install_start(target, material)
        self.assertEqual(self.install_start(target, material), first)
        with self.assertRaisesRegex(ValueError, 'fixed start'):
            self.deliver(target, material, 'LATE')
        self.assertEqual(self.book(target)['start']['batch'], 'S')
        self.assert_book(target, [7, 0, None], ['晨班尺', '零量仪', '未到表'], 7)

    def test_empty_and_uninstalled_day(self):
        target = self.mirror()
        with self.assertRaisesRegex(ValueError, 'not installed'):
            self.book(target)
        self.install_start(target, self.make_material())
        book = self.book(target, '2025-05-18')
        self.assertEqual((book['rows'], book['row_count'], book['total_litres']), ([], 0, 0))
        with self.assertRaises(ValueError):
            self.book(target, '2025-02-30')
        with self.assertRaises(ValueError):
            initialize_mirror_schema(target, MIRROR, 'another-stream')
        self.assertEqual(self.book(target)['start']['stream'], STREAM)

    def test_exact_integer_day_total(self):
        source = self.source()
        sample = load_sample('open_day.json')
        sample['rows'][0]['reading']['litres'] = 2 ** 80
        sample['rows'][1]['reading']['litres'] = 3
        material = issue_sample(source, sample)
        target = self.mirror()
        self.install_start(target, material)
        total = self.book(target)['total_litres']
        self.assertIs(type(total), int)
        self.assertEqual(total, 1208925819614629174706179)

    def test_change_requires_compatible_start(self):
        source = self.source()
        material = issue_sample(source, load_sample('corrections.json'))
        material['new'] = bootstrap(source, STREAM, 'T2')
        target = self.mirror()
        staged = self.receive_batch(target, material, 'T2')
        with self.assertRaisesRegex(ValueError, 'install a bootstrap'):
            post(target, MIRROR, staged['intake_id'])
        self.deliver(target, material, 'new')
        with self.assertRaisesRegex(ValueError, 'covered by the mirror start'):
            post(target, MIRROR, staged['intake_id'])
        self.assert_book(target, [7, 8], ['A复测', 'B复测'], 15)
        self.assertEqual(self.deliver(target, material, 'T3')['status'], 'posted')
        self.assert_book(target, [13, 9], ['A联核', 'B联核'], 22)

    def test_later_original_fact_needs_a_covering_start(self):
        source = self.source()
        sample = load_sample('corrections.json')
        first = record(source, STREAM, 'S', sample['rows'][:1])
        old = bootstrap(source, STREAM, 'S')
        record(source, STREAM, 'MORE', sample['rows'][1:])
        amend(source, STREAM, 'T2', [correction(source, 'B', 8, 'B复测')])
        from publication.changes import issue
        material = {'S': old, 'MORE': bootstrap(source, STREAM, 'MORE'), 'T2': issue(source, 'T2')}
        old_target = self.mirror('old')
        self.install_start(old_target, material)
        with self.assertRaisesRegex(ValueError, 'required original fact'):
            self.deliver(old_target, material, 'T2')
        self.assertEqual(self.book(old_target)['start']['sequence'], first['sequence'])
        self.assert_book(old_target, [7], ['A初测'], 7)
        new_target = self.mirror('new')
        self.deliver(new_target, material, 'MORE')
        self.assertEqual(self.deliver(new_target, material, 'T2')['status'], 'posted')
        self.assert_book(new_target, [7, 8], ['A初测', 'B复测'], 15)
