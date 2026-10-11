"""Raw layer declarations cannot hide behind Compose's resource pruning."""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "maintenance"))
from common import MaintenanceError
from deployment import Deployment
from overlay_sources import validate_source


class SourceLayerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.layer = self.root / "stacks/signoz/maintenance/layer.yaml"
        self.layer.parent.mkdir(parents=True)
        (self.root / "compose.yaml").write_text("name: ops-board\n")

    def test_unused_resources_names_imports_and_indirect_sources_refused(self):
        sources = ["volumes: {unused: {external: true}}",
                   '{"networks": {"unused": {"external": true}}}',
                   "name: ops-board\nservices: {}", "include: [outside.yaml]",
                   "services: {sentinel: {image: unchanged}}",
                   "services: {signoz: {extends: {file: outside.yaml, service: signoz}}}",
                   "services: {signoz: {env_file: outside.env}}",
                   "services: {signoz: {label_file: outside.labels}}",
                   "x-hidden: &hidden {volumes: {unused: {}}}\n<<: *hidden\nservices: {}"]
        for source in sources:
            self.layer.write_text(source)
            with self.subTest(source=source), self.assertRaises(MaintenanceError):
                validate_source(self.layer, ["signoz"])

    def test_duplicate_mapping_keys_refused_before_compose(self):
        for source in ["services: {}\nservices: {}", '{"services": {}, "services": {}}',
                       "services: {signoz: {image: one, image: two}}"]:
            self.layer.write_text(source)
            with self.subTest(source=source), patch("deployment.docker_json") as docker:
                with self.assertRaisesRegex(MaintenanceError, "Duplicate"):
                    Deployment(self.root, "signoz", overlays=[self.layer]).resolve_config()
                docker.assert_not_called()

    def test_safe_tags_and_explicit_merge_overrides_preserved_for_compose_validation(self):
        self.layer.write_text("x-env: &env {A: old, B: same}\nservices:\n  signoz:\n"
                              "    environment: {<<: *env, A: new}\n"
                              "    command: !override [new]\n    profiles: !reset []\n")
        validate_source(self.layer, ["signoz"])

    def test_missing_yaml_fails_closed_only_for_overlays(self):
        self.layer.write_text("services: {}")
        with patch.dict(sys.modules, {"yaml": None}), patch("deployment.docker_json") as docker:
            with self.assertRaisesRegex(MaintenanceError, "require PyYAML"):
                Deployment(self.root, "signoz", overlays=[self.layer]).resolve_config()
            docker.assert_not_called()
            docker.return_value = {"name": "ops-board", "services": {}}
            self.assertEqual(Deployment(self.root, "signoz").resolve_config()["name"], "ops-board")
            self.assertEqual(docker.call_count, 1)


if __name__ == "__main__":
    unittest.main()
