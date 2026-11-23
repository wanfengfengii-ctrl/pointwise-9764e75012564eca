import sqlite3

from audit.history import receipt
from mirror.facts import get_applied_batch
from mirror.posting import post
from receiving.pending import list_pending
from tests.support import MIRROR, ProjectCase, install_post_failure


class AuditTests(ProjectCase):
    def test_offline_resume_and_receipt(self):
        material = self.make_material()
        target = self.mirror()
        self.install_start(target, material)
        old_b = self.deliver(target, material, 'T2')['receipt']
        pending = self.receive_batch(target, material, 'T3')
        outcome = post(target, MIRROR, pending['intake_id'])
        self.assertEqual(outcome['status'], 'pending')
        with self.assertRaises(LookupError):
            receipt(target, MIRROR, pending['delivery_id'])
        target.close()
        target = self.mirror()
        self.assertEqual(list_pending(target, MIRROR), [pending])
        self.assertEqual(self.receive_batch(target, material, 'T3'), pending)
        self.assert_book(target, [7, 8], ['A初测', 'B复测'], 15)
        old_a = self.deliver(target, material, 'T1')['receipt']
        self.assertEqual(old_a['sources'][0]['origin'], 'A复测')
        self.assertEqual(old_a['sources'][0]['batch'], 'T1')
        self.assertEqual(old_a['sources'][0]['sequence'], 2)
        done = post(target, MIRROR, pending['intake_id'])['receipt']
        target.close()
        target = self.mirror()
        self.assertEqual(list_pending(target, MIRROR), [])
        self.assert_book(target, [13, 9], ['A联核', 'B联核'], 22)
        self.assertEqual(receipt(target, MIRROR, old_a['delivery_id']), old_a)
        self.assertEqual(receipt(target, MIRROR, old_b['delivery_id']), old_b)
        self.assertEqual(receipt(target, MIRROR, pending['delivery_id']), done)
        self.assertEqual(self.receive_batch(target, material, 'T1')['intake_id'], old_a['intake_id'])
        self.assertEqual(self.deliver(target, material, 'T1')['receipt'], old_a)
        self.assertEqual([row['provenance']['batch'] for row in self.book(target)['rows']], ['T3', 'T3'])

    def test_failed_post_and_restart(self):
        material = self.make_material()
        target = self.mirror()
        self.install_start(target, material)
        old_a = self.deliver(target, material, 'T1')['receipt']
        old_b = self.deliver(target, material, 'T2')['receipt']
        pending = self.receive_batch(target, material, 'T3')
        install_post_failure(target, pending['intake_id'])
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'fixture posting failure'):
            post(target, MIRROR, pending['intake_id'])
        target.close()
        target = self.mirror()
        self.assert_book(target, [7, 8], ['A复测', 'B复测'], 15)
        self.assertEqual(list_pending(target, MIRROR), [pending])
        self.assertIsNone(get_applied_batch(target, MIRROR, 4))
        with self.assertRaises(LookupError):
            receipt(target, MIRROR, pending['delivery_id'])
        self.assertEqual(receipt(target, MIRROR, old_a['delivery_id']), old_a)
        self.assertEqual(receipt(target, MIRROR, old_b['delivery_id']), old_b)
        applied = post(target, MIRROR, pending['intake_id'])
        self.assertEqual(applied['status'], 'posted')
        self.assertEqual(receipt(target, MIRROR, pending['delivery_id']), applied['receipt'])
        self.assertEqual(get_applied_batch(target, MIRROR, 4)['batch'], 'T3')
        self.assertEqual(list_pending(target, MIRROR), [])
        self.assert_book(target, [13, 9], ['A联核', 'B联核'], 22)
        self.assertEqual(receipt(target, MIRROR, old_a['delivery_id']), old_a)
        self.assertEqual(receipt(target, MIRROR, old_b['delivery_id']), old_b)

    def test_missing_intake_and_receipt(self):
        target = self.mirror()
        with self.assertRaises(LookupError):
            post(target, MIRROR, 999)
        with self.assertRaises(LookupError):
            receipt(target, MIRROR, 'no-delivery')
        self.assertEqual(list_pending(target, MIRROR), [])
