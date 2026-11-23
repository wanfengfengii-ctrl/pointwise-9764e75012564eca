import hashlib
import hmac
import json
from dataclasses import asdict, dataclass

from ledger import canonical_json, require_fields, text_id


@dataclass(frozen=True)
class FrozenEnvelope:
    version: int
    kind: str
    stream: str
    delivery_id: str
    body: str
    digest: str

    def to_bytes(self):
        return canonical_json(asdict(self)).encode('ascii')


def delivery_number(kind, stream, batch):
    identity = canonical_json([kind, stream, batch]).encode('ascii')
    return f'{kind}-{hashlib.sha256(identity).hexdigest()}'


def _body_digest(version, kind, stream, delivery_id, body):
    frozen = canonical_json([version, kind, stream, delivery_id, body]).encode('ascii')
    return hashlib.sha256(frozen).hexdigest()


def freeze_envelope(kind, stream, delivery_id, document):
    body = canonical_json(document)
    digest = _body_digest(1, kind, stream, delivery_id, body)
    return FrozenEnvelope(1, kind, stream, delivery_id, body, digest)


def check_body_digest(envelope):
    expected = _body_digest(envelope.version, envelope.kind, envelope.stream,
                            envelope.delivery_id, envelope.body)
    if not envelope.digest.isascii() or not hmac.compare_digest(envelope.digest, expected):
        raise ValueError('envelope digest does not match the received body and binding')


def decode_envelope(payload):
    if not isinstance(payload, bytes):
        raise ValueError('a frozen envelope must be bytes')
    try:
        fields = json.loads(payload)
    except (ValueError, RecursionError) as error:
        raise ValueError('invalid frozen envelope JSON') from error
    require_fields(fields, ('version', 'kind', 'stream', 'delivery_id', 'body', 'digest'), 'envelope')
    if type(fields['version']) is not int or fields['version'] != 1:
        raise ValueError('unsupported envelope version')
    if fields['kind'] not in ('bootstrap', 'change'):
        raise ValueError('unsupported envelope kind')
    for name in ('stream', 'delivery_id', 'body', 'digest'):
        text_id(fields[name], name)
    envelope = FrozenEnvelope(**fields)
    check_body_digest(envelope)
    if payload != envelope.to_bytes():
        raise ValueError('envelope bytes are not in frozen form')
    return envelope
