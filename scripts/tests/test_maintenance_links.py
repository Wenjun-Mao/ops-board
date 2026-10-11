"""ClickHouse-shaped contained links and hostile link-chain regression fixtures."""

import io
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "maintenance"))
from archives import safe_tar
from common import MaintenanceError


class ArchiveLinkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "clickhouse.tar"

    def archive(self, entries):
        with tarfile.open(self.path, "w") as archive:
            for name, kind, value in entries:
                member = tarfile.TarInfo(name)
                member.type = kind
                member.mode = 0o755 if kind == tarfile.DIRTYPE else 0o644
                if kind in {tarfile.SYMTYPE, tarfile.LNKTYPE}:
                    member.linkname = value
                    archive.addfile(member)
                elif kind == tarfile.REGTYPE:
                    member.size = len(value)
                    archive.addfile(member, io.BytesIO(value))
                else:
                    archive.addfile(member)

    def test_clickhouse_atomic_metadata_and_data_relative_links_roundtrip(self):
        self.archive([
            ("store/abc/db-uuid", tarfile.DIRTYPE, ""),
            ("store/def/table-uuid", tarfile.DIRTYPE, ""),
            ("store/abc/db-uuid/table.sql", tarfile.REGTYPE, b"CREATE TABLE"),
            ("store/def/table-uuid/part.bin", tarfile.REGTYPE, b"retained part"),
            ("metadata/signoz_traces", tarfile.SYMTYPE, "../store/abc/db-uuid"),
            ("data/signoz_traces/signoz_index_v3", tarfile.SYMTYPE, "../../store/def/table-uuid"),
        ])
        members = safe_tar(self.path)
        target = self.root / "restore"
        with tarfile.open(self.path) as archive:
            archive.extractall(target, members=members)
        self.assertEqual((target / "metadata/signoz_traces/table.sql").read_bytes(), b"CREATE TABLE")
        self.assertEqual((target / "data/signoz_traces/signoz_index_v3/part.bin").read_bytes(), b"retained part")

    def test_contained_link_chain(self):
        self.archive([("store/blob", tarfile.REGTYPE, b"value"),
                      ("metadata/db", tarfile.SYMTYPE, "../alias"),
                      ("alias", tarfile.SYMTYPE, "store")])
        safe_tar(self.path)

    def test_hardlinks_are_root_relative_and_chains_are_validated(self):
        self.archive([("store/blob", tarfile.REGTYPE, b"value"),
                      ("metadata/blob", tarfile.LNKTYPE, "store/blob"),
                      ("copy", tarfile.LNKTYPE, "metadata/blob")])
        safe_tar(self.path)

    def test_lexically_contained_target_cannot_escape_through_a_link(self):
        self.archive([("alias", tarfile.SYMTYPE, "."),
                      ("metadata/db", tarfile.SYMTYPE, "../alias/../escape")])
        with self.assertRaisesRegex(MaintenanceError, "escapes"):
            safe_tar(self.path)

    def test_link_cycles_refused(self):
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
            self.archive([("a", kind, "b"), ("b", kind, "a")])
            with self.assertRaisesRegex(MaintenanceError, "Cyclic"):
                safe_tar(self.path)

    def test_contained_link_still_cannot_be_an_archive_write_parent(self):
        self.archive([("metadata/db", tarfile.SYMTYPE, "../store/abc"),
                      ("metadata/db/evil", tarfile.REGTYPE, b"overwrite")])
        with self.assertRaisesRegex(MaintenanceError, "writes through"):
            safe_tar(self.path)

    def test_duplicate_link_cannot_hide_an_earlier_escape(self):
        self.archive([("metadata/db", tarfile.SYMTYPE, "../../escape"),
                      ("./metadata/db", tarfile.SYMTYPE, "../store/safe")])
        with self.assertRaisesRegex(MaintenanceError, "Duplicate"):
            safe_tar(self.path)


if __name__ == "__main__":
    unittest.main()
