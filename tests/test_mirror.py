import sqlite3

from audit.history import receipt
from mirror.posting import post
from publication.envelope import decode_envelope
from receiving.pending import list_pending
from tests.support import MIRROR, ProjectCase, install_post_failure


class MirrorTests(ProjectCase):
    def test_independent_later_batch(self):
        material = self.make_material()
        target = self.mirror()
        self.install_start(target, material)
        result = self.deliver(target, material, 'T2')
        self.assertEqual(result['status'], 'posted')
        self.assertEqual(result['receipt']['batch'], 'T2')
        self.assert_book(target, [7, 8], ['A初测', 'B复测'], 15)
        with self.assertRaises(LookupError):
            receipt(target, MIRROR, self.delivery_number(material, 'T1'))

    def test_equal_value_predecessor(self):
        material = self.make_material()
        target = self.mirror()
        self.install_start(target, material)
        self.assertEqual(self.deliver(target, material, 'T2')['status'], 'posted')
        accepted = self.receive_batch(target, material, 'T3')
        outcome = post(target, MIRROR, accepted['intake_id'])
        book = self.book(target)
        self.assertEqual((outcome['status'], book['total_litres']), ('pending', 15),
                         f"T3 before T1: status={outcome['status']} litres={book['total_litres']}")
        self.assertIsNone(outcome['receipt'])
        self.assert_book(target, [7, 8], ['A初测', 'B复测'], 15)
        self.assertEqual([row['provenance']['batch'] for row in book['rows']], ['S', 'T2'])
        self.assertEqual(list_pending(target, MIRROR), [accepted])
        with self.assertRaises(LookupError):
            receipt(target, MIRROR, self.delivery_number(material, 'T3'))

    def test_unrelated_history(self):
        material = self.make_material(unrelated=True)
        target = self.mirror()
        self.install_start(target, material)
        self.assertEqual(self.deliver(target, material, 'T2')['status'], 'posted')
        self.assertEqual(self.deliver(target, material, 'T3')['status'], 'posted')
        self.assert_book(target, [13, 9], ['A联核', 'B联核'], 22)
        self.assertEqual(self.book(target, '2025-05-17')['total_litres'], 4)
        with self.assertRaises(LookupError):
            receipt(target, MIRROR, self.delivery_number(material, 'T1'))

    def test_reverse_delivery(self):
        material = self.make_material(unrelated=True)
        target = self.mirror()
        self.install_start(target, material)
        accepted = self.receive_batch(target, material, 'T3')
        self.assertEqual(post(target, MIRROR, accepted['intake_id'])['status'], 'pending')
        self.assert_book(target, [7, 5], ['A初测', 'B初测'], 12)
        self.assertEqual(self.deliver(target, material, 'T2')['status'], 'posted')
        self.assert_book(target, [7, 8], ['A初测', 'B复测'], 15)
        self.assertEqual(post(target, MIRROR, accepted['intake_id'])['status'], 'posted')
        self.assert_book(target, [13, 9], ['A联核', 'B联核'], 22)

    def test_issue_predecessor(self):
        same_key = self.make_material(name='intersecting')
        different_key = self.make_material(name='disjoint', unrelated=True)
        self.assertEqual(same_key['S'], different_key['S'])
        left = decode_envelope(same_key['T3']['envelope'])
        right = decode_envelope(different_key['T3']['envelope'])
        self.assertEqual(left.delivery_id, right.delivery_id)
        self.assertNotEqual(left.body, right.body)
        for name, material, expected_status, expected_litres in (
            ('left', same_key, 'pending', 15), ('right', different_key, 'posted', 22),
        ):
            with self.subTest(history=name):
                target = self.mirror(name)
                self.install_start(target, material)
                self.assertEqual(self.deliver(target, material, 'T2')['status'], 'posted')
                self.assertEqual(self.deliver(target, material, 'T3')['status'], expected_status)
                self.assertEqual(self.book(target)['total_litres'], expected_litres)

    def test_received_predecessor_failed(self):
        material = self.make_material()
        target = self.mirror()
        self.install_start(target, material)
        self.deliver(target, material, 'T2')
        first = self.receive_batch(target, material, 'T1')
        last = self.receive_batch(target, material, 'T3')
        self.assertEqual(post(target, MIRROR, last['intake_id'])['status'], 'pending')
        install_post_failure(target, first['intake_id'])
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'fixture posting failure'):
            post(target, MIRROR, first['intake_id'])
        with self.assertRaises(LookupError):
            receipt(target, MIRROR, self.delivery_number(material, 'T1'))
        self.assertEqual(post(target, MIRROR, last['intake_id'])['status'], 'pending')
        with self.assertRaises(LookupError):
            receipt(target, MIRROR, self.delivery_number(material, 'T3'))
        self.assert_book(target, [7, 8], ['A初测', 'B复测'], 15)
        target.close()
        target = self.mirror()
        self.assertEqual(post(target, MIRROR, first['intake_id'])['status'], 'posted')
        self.assertEqual(post(target, MIRROR, last['intake_id'])['status'], 'posted')
        self.assert_book(target, [13, 9], ['A联核', 'B联核'], 22)
