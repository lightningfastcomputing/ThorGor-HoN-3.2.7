import struct
import unittest

from thorgor.patches.builders.complete_registry_guard import (
    SNAPSHOT_CREATE_CAVE_RVA,
    SNAPSHOT_SKIP_RVA,
    snapshot_create_stub,
)


class CgameSnapshotGuardTests(unittest.TestCase):
    def test_null_factory_result_skips_to_existing_snapshot_loop_path(self):
        stub = snapshot_create_stub()
        self.assertEqual(stub[:10], bytes.fromhex("8bd88b475c85db7401c3"))
        self.assertEqual(stub[10:14], bytes.fromhex("83c404e9"))
        displacement = struct.unpack_from("<i", stub, 14)[0]
        destination = SNAPSHOT_CREATE_CAVE_RVA + len(stub) + displacement
        self.assertEqual(destination, SNAPSHOT_SKIP_RVA)


if __name__ == "__main__":
    unittest.main()
