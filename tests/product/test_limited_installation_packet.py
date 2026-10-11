"""Offline definitions preparation is never an installed root or credential."""
from types import SimpleNamespace

from bdb_audit.history.limited_protocol import LimitedProtocol
from tools.nf02_p0_installation_packet import root_objects
from tests.product.test_limited_p0 import corpus as p0_corpus

corpus = p0_corpus


def test_offline_root_packet_has_all_six_objects_and_exact_eight_pins(corpus):
    namespace = "d" * 64  # Shape only, not installed authority.
    roots = root_objects(corpus, namespace)
    context = SimpleNamespace(corpus=corpus, roots=roots, root={"namespace_authority_digest": namespace},
                              pins={k: o.ref.as_dict() for k, o in roots.items()}, schema_ref=corpus.schema_ref,
                              check_profiles=lambda value: LimitedProtocol.check_profiles(context, value))
    LimitedProtocol.validate_roots(context)
    assert len(roots) == 6
    assert {o.version for o in roots.values()} == {"2", "3"}
