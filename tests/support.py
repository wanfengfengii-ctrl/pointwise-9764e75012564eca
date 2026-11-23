import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from audit.daybook import read_day
from demo import issue_sample, load_sample
from mirror.facts import initialize_mirror_schema
from mirror.posting import post
from publication.register import initialize_publication_schema
from receiving.inbox import receive
from receiving.store import initialize_inbox_schema
from source.revisions import get_current_facts, initialize_source_schema


STREAM = '澄河-日流'
MIRROR = '夜班'
STATION = '南闸'
DAY = '2025-05-16'


def measurement(litres, origin):
    return {'litres': litres, 'missing': litres is None, 'origin': origin}


def correction(db, observation_id, litres, origin):
    key = [STATION, DAY, observation_id]
    before = next(fact for fact in get_current_facts(db, STREAM) if fact['key'] == key)
    return {'key': key, 'before': before, 'after': measurement(litres, origin)}


def install_post_failure(connection, intake_id):
    connection.execute(f'''CREATE TEMP TRIGGER reject_test_post
        AFTER UPDATE OF pending ON inbox
        WHEN NEW.intake_id = {intake_id:d} AND NEW.pending = 0
        BEGIN SELECT RAISE(ABORT, 'fixture posting failure'); END''')


class ProjectCase(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory(prefix='daybook-test-')
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)

    def connect(self, name):
        connection = sqlite3.connect(self.directory / f'{name}.sqlite')
        self.addCleanup(connection.close)
        return connection

    def source(self, name='source'):
        connection = self.connect(name)
        initialize_source_schema(connection)
        initialize_publication_schema(connection)
        return connection

    def mirror(self, name='mirror'):
        connection = self.connect(name)
        initialize_mirror_schema(connection, MIRROR, STREAM)
        initialize_inbox_schema(connection)
        return connection

    def make_material(self, *, unrelated=False, name='source'):
        sample = load_sample('corrections.json')
        if unrelated:
            sample['amendments'][0]['updates'] = [
                {'key': [STATION, '2025-05-17', 'C'], 'after': measurement(11, 'C复测')}
            ]
        source = self.source(name)
        try:
            return issue_sample(source, sample)
        finally:
            source.close()

    def receive_batch(self, connection, material, batch):
        return receive(connection, MIRROR, material[batch]['envelope'])

    def deliver(self, connection, material, batch):
        accepted = self.receive_batch(connection, material, batch)
        return post(connection, MIRROR, accepted['intake_id'])

    def install_start(self, connection, material):
        return self.deliver(connection, material, 'S')['receipt']

    def book(self, connection, day=DAY):
        return read_day(connection, MIRROR, STATION, day)

    def assert_book(self, connection, litres, origins, total):
        book = self.book(connection)
        self.assertEqual([row['litres'] for row in book['rows']], litres)
        self.assertEqual([row['provenance']['origin'] for row in book['rows']], origins)
        self.assertEqual(book['row_count'], len(litres))
        self.assertEqual(book['total_litres'], total)

    def delivery_number(self, material, batch):
        return material[batch]['receipt']['delivery_id']
