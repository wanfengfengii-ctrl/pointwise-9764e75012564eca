import json
from dataclasses import replace

from audit.history import receipt
from demo import issue_sample, load_sample
from mirror.facts import initialize_mirror_schema
from publication.changes import issue
from publication.envelope import decode_envelope, freeze_envelope
from receiving.inbox import receive
from receiving.pending import list_pending
from receiving.store import find_delivery
from source.corrections import amend
from tests.support import MIRROR, ProjectCase, correction


class TransportTests(ProjectCase):
    def test_corrupt_envelope(self):
        material = self.make_material()
        target = self.mirror()
        self.install_start(target, material)
        original = decode_envelope(material['T2']['envelope'])
        corrupt = replace(original, body=original.body.replace('"litres":8', '"litres":6'))
        self.assertNotEqual(corrupt.body, original.body)
        with self.assertRaisesRegex(ValueError, 'digest'):
            receive(target, MIRROR, corrupt.to_bytes())
        self.assertIsNone(find_delivery(target, MIRROR, original.delivery_id))
        self.assertEqual(list_pending(target, MIRROR), [])
        self.assert_book(target, [7, 5], ['A初测', 'B初测'], 12)
        self.assertEqual(self.deliver(target, material, 'T2')['status'], 'posted')
        self.assert_book(target, [7, 8], ['A初测', 'B复测'], 15)

    def test_wrong_stream(self):
        material = self.make_material()
        target = self.mirror()
        initialize_mirror_schema(target, '其他班', '另一源流')
        with self.assertRaisesRegex(ValueError, 'another source stream'):
            receive(target, '其他班', material['S']['envelope'])
        self.assertEqual(list_pending(target, '其他班'), [])

    def test_resealed_malformed_observation_and_delivery_binding(self):
        material = self.make_material()
        target = self.mirror()
        original = decode_envelope(material['T2']['envelope'])
        doc = json.loads(original.body)
        doc['changes'][0]['after']['reading']['missing'] = True
        invalid = freeze_envelope(original.kind, original.stream, original.delivery_id, doc)
        with self.assertRaisesRegex(ValueError, 'null litres'):
            receive(target, MIRROR, invalid.to_bytes())
        unbound = freeze_envelope(original.kind, original.stream, 'new-delivery', json.loads(original.body))
        with self.assertRaisesRegex(ValueError, 'does not bind'):
            receive(target, MIRROR, unbound.to_bytes())
        self.assertEqual(list_pending(target, MIRROR), [])

    def test_conflicting_redelivery(self):
        material = self.make_material()
        target = self.mirror()
        self.install_start(target, material)
        original = decode_envelope(material['T2']['envelope'])
        first = self.deliver(target, material, 'T2')['receipt']
        doc = json.loads(original.body)
        doc['changes'][0]['after']['reading']['litres'] = 18
        different = freeze_envelope(original.kind, original.stream, original.delivery_id, doc).to_bytes()
        comparison = self.mirror('comparison')
        self.install_start(comparison, material)
        self.assertTrue(receive(comparison, MIRROR, different)['pending'])
        with self.assertRaisesRegex(ValueError, 'different material'):
            receive(target, MIRROR, different)
        stored = find_delivery(target, MIRROR, original.delivery_id)
        self.assertEqual(stored['envelope'], material['T2']['envelope'])
        self.assertFalse(stored['pending'])
        self.assertEqual(receipt(target, MIRROR, original.delivery_id), first)
        self.assertEqual(self.deliver(target, material, 'T2')['receipt'], first)
        self.assert_book(target, [7, 8], ['A初测', 'B复测'], 15)

    def test_frozen_issue_survives_new_revision_and_reinitialization(self):
        source = self.source()
        original = issue_sample(source, load_sample('corrections.json'))
        amend(source, original['T3']['receipt']['stream'], 'T4', [correction(source, 'A', 14, '迟班复核')])
        changed = issue(source, 'T4')
        source.close()
        source = self.source()
        self.assertEqual(issue(source, 'T3'), original['T3'])
        self.assertEqual(issue(source, 'T2'), original['T2'])
        self.assertNotEqual(changed['receipt']['receipt_id'], original['T3']['receipt']['receipt_id'])
