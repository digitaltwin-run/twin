from __future__ import annotations

import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest

import twin_standard


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profiles" / "generic-twin.json"
PROTO = ROOT / "proto" / "twin" / "v1" / "twin.proto"


class TwinStandardTests(unittest.TestCase):
    maxDiff = None

    def _document(self) -> dict:
        return json.loads(PROFILE.read_text(encoding="utf-8"))

    def _fixture(self, mutate=None, proto_mutate=None, raw_profile: str | None = None) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        profile_path = root / "profiles" / "generic-twin.json"
        proto_path = root / "proto" / "twin" / "v1" / "twin.proto"
        profile_path.parent.mkdir(parents=True)
        proto_path.parent.mkdir(parents=True)
        if raw_profile is None:
            document = copy.deepcopy(self._document())
            if mutate:
                mutate(document)
            profile_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        else:
            profile_path.write_text(raw_profile, encoding="utf-8")
        proto_text = PROTO.read_text(encoding="utf-8")
        if proto_mutate:
            proto_text = proto_mutate(proto_text)
        proto_path.write_text(proto_text, encoding="utf-8")
        return profile_path

    def _codes(self, profile_path: Path) -> set[str]:
        return {item.code for item in twin_standard.validate_profile(profile_path)}

    @staticmethod
    def _tree_bytes(path: Path) -> dict[str, bytes]:
        return {
            str(item.relative_to(path)): item.read_bytes()
            for item in sorted(path.rglob("*"))
            if item.is_file()
        }

    def test_reference_profile_is_valid(self):
        self.assertEqual([], twin_standard.validate_profile(PROFILE))

    def test_validation_report_is_stable_and_sorted(self):
        profile = self._fixture(
            lambda value: (
                value["eventSourcing"].__setitem__("appendOnly", False),
                value["authority"].__setitem__("receiptsRequired", False),
            )
        )
        first = twin_standard.validation_report(twin_standard.validate_profile(profile))
        second = twin_standard.validation_report(twin_standard.validate_profile(profile))
        self.assertEqual(first, second)
        self.assertFalse(first["valid"])
        self.assertEqual(
            first["diagnostics"],
            sorted(first["diagnostics"], key=lambda item: (item["code"], item["path"], item["message"])),
        )

    def test_missing_required_trait_fails(self):
        profile = self._fixture(lambda value: value["traits"].pop())
        self.assertIn("TWIN-TRAIT-001", self._codes(profile))

    def test_unknown_trait_operation_fails(self):
        profile = self._fixture(lambda value: value["traits"][0]["operations"].append("twin.unknown"))
        self.assertIn("TWIN-TRAIT-001", self._codes(profile))

    def test_command_without_events_fails_cqrs(self):
        profile = self._fixture(lambda value: value["operations"][0].__setitem__("emits", []))
        self.assertIn("TWIN-CQRS-001", self._codes(profile))

    def test_query_that_emits_fails_cqrs(self):
        profile = self._fixture(
            lambda value: value["operations"][-1].__setitem__(
                "emits", ["subactor.twin.v1.ObservationPublished"]
            )
        )
        self.assertIn("TWIN-CQRS-001", self._codes(profile))

    def test_command_event_must_be_a_protobuf_type(self):
        profile = self._fixture(lambda value: value["operations"][0].__setitem__("emits", [42]))
        self.assertIn("TWIN-OPERATION-001", self._codes(profile))

    def test_missing_event_metadata_fails(self):
        profile = self._fixture(lambda value: value["eventSourcing"]["requiredMetadata"].remove("causation_id"))
        self.assertIn("TWIN-EVENT-001", self._codes(profile))

    def test_replay_cannot_execute_effects(self):
        profile = self._fixture(lambda value: value["eventSourcing"].__setitem__("replayExecutesEffects", True))
        self.assertIn("TWIN-REPLAY-001", self._codes(profile))

    def test_connector_cannot_own_domain_rules(self):
        profile = self._fixture(lambda value: value["connectors"][0].__setitem__("domainRules", True))
        self.assertIn("TWIN-CONNECTOR-001", self._codes(profile))

    def test_secret_values_must_be_forbidden(self):
        profile = self._fixture(lambda value: value["authority"]["secrets"].__setitem__("valuesForbidden", False))
        self.assertIn("TWIN-SECRET-001", self._codes(profile))

    def test_unevaluable_cannot_be_healthy(self):
        profile = self._fixture(lambda value: value["observability"]["healthyStates"].append("UNEVALUABLE"))
        self.assertIn("TWIN-EVIDENCE-001", self._codes(profile))

    def test_each_surface_must_bind_every_operation_once(self):
        profile = self._fixture(lambda value: value["transports"]["cli"]["bindings"].pop())
        diagnostics = twin_standard.validate_profile(profile)
        self.assertTrue(
            any(item.code == "TWIN-TRANSPORT-001" and "found 0" in item.message for item in diagnostics)
        )

    def test_shell_safety_flags_are_mandatory(self):
        profile = self._fixture(lambda value: value["transports"]["shell"].__setitem__("noEval", False))
        self.assertIn("TWIN-SHELL-001", self._codes(profile))

    def test_shell_metacharacters_are_rejected_as_data(self):
        profile = self._fixture(
            lambda value: value["transports"]["shell"]["bindings"][0]["argv"].append("$(id)")
        )
        self.assertIn("TWIN-SHELL-001", self._codes(profile))

    def test_rest_query_must_use_get(self):
        def mutate(value):
            binding = next(
                item for item in value["transports"]["rest"]["bindings"] if item["operation"] == "twin.get"
            )
            binding["method"] = "POST"

        profile = self._fixture(mutate)
        self.assertIn("TWIN-REST-001", self._codes(profile))

    def test_mcp_is_json_rpc_with_protojson(self):
        profile = self._fixture(lambda value: value["transports"]["mcp"].__setitem__("encoding", "protobuf"))
        self.assertIn("TWIN-MCP-001", self._codes(profile))

    def test_mutating_mcp_tool_requires_authority(self):
        profile = self._fixture(
            lambda value: value["transports"]["mcp"]["bindings"][0].__setitem__("requiresAuthority", False)
        )
        self.assertIn("TWIN-MCP-001", self._codes(profile))

    def test_missing_referenced_proto_message_fails(self):
        profile = self._fixture(
            lambda value: value["operations"][0].__setitem__("request", "subactor.twin.v1.DoesNotExist")
        )
        self.assertIn("TWIN-PROTO-001", self._codes(profile))

    def test_duplicate_proto_field_number_fails(self):
        profile = self._fixture(
            proto_mutate=lambda text: text.replace("string aggregate_type = 3;", "string aggregate_type = 2;", 1)
        )
        self.assertIn("TWIN-PROTO-001", self._codes(profile))

    def test_command_envelope_authority_field_is_required(self):
        profile = self._fixture(
            proto_mutate=lambda text: text.replace("  AuthorityRef authority_ref = 8;\n", "", 1)
        )
        self.assertIn("TWIN-PROTO-001", self._codes(profile))

    def test_each_operation_requires_a_service_rpc(self):
        profile = self._fixture(
            proto_mutate=lambda text: text.replace(
                "  rpc Reconcile(ReconcileCommand) returns (CommandReceipt);\n", "", 1
            )
        )
        self.assertIn("TWIN-PROTO-001", self._codes(profile))

    def test_proto_secret_value_field_fails(self):
        profile = self._fixture(
            proto_mutate=lambda text: text.replace(
                "message ActorRef {", "message ActorRef {\n  string secret = 99;", 1
            )
        )
        self.assertIn("TWIN-SECRET-001", self._codes(profile))

    def test_duplicate_json_key_fails_closed(self):
        profile = self._fixture(raw_profile='{"schema":"twin.profile/v1","schema":"other"}\n')
        self.assertEqual({"TWIN-JSON-001"}, self._codes(profile))

    def test_generation_emits_only_declared_contract_files(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        destination = Path(temporary.name) / "bundle"
        outputs = twin_standard.generate_bundle(PROFILE, destination, "rust")
        self.assertEqual(twin_standard.EXPECTED_OUTPUTS, outputs)
        self.assertEqual(
            set(outputs),
            set(self._tree_bytes(destination)),
        )
        manifest = json.loads((destination / "twin.manifest.json").read_text(encoding="utf-8"))
        self.assertEqual("rust", manifest["language"])
        self.assertFalse(manifest["executableCode"])

    def test_generation_is_byte_deterministic_for_arbitrary_language(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        first = Path(temporary.name) / "first"
        second = Path(temporary.name) / "second"
        twin_standard.generate_bundle(PROFILE, first, "c++23")
        twin_standard.generate_bundle(PROFILE, second, "c++23")
        self.assertEqual(self._tree_bytes(first), self._tree_bytes(second))

    def test_conformance_covers_every_operation_and_surface(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        destination = Path(temporary.name) / "bundle"
        twin_standard.generate_bundle(PROFILE, destination, "go")
        conformance = json.loads((destination / "conformance.json").read_text(encoding="utf-8"))
        operations = self._document()["operations"]
        transport_cases = [item for item in conformance["cases"] if item["kind"] == "transport-binding"]
        self.assertEqual(len(operations) * len(twin_standard.REQUIRED_SURFACES), len(transport_cases))

    def test_existing_destination_is_never_overwritten(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        destination = Path(temporary.name) / "bundle"
        destination.mkdir()
        marker = destination / "owned.txt"
        marker.write_text("keep\n", encoding="utf-8")
        with self.assertRaises(twin_standard.GenerationError) as raised:
            twin_standard.generate_bundle(PROFILE, destination, "python")
        self.assertEqual("TWIN-OUTPUT-001", raised.exception.code)
        self.assertEqual("keep\n", marker.read_text(encoding="utf-8"))

    def test_unsafe_language_identifier_fails(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        with self.assertRaises(twin_standard.GenerationError) as raised:
            twin_standard.generate_bundle(PROFILE, Path(temporary.name) / "bundle", "python;touch")
        self.assertEqual("TWIN-GENERATION-001", raised.exception.code)

    def test_cli_validate_json_contract(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = twin_standard.main(["validate", str(PROFILE), "--format", "json"])
        report = json.loads(output.getvalue())
        self.assertEqual(0, status)
        self.assertEqual({"schema": "twin.validation/v1", "valid": True, "diagnostics": []}, report)


if __name__ == "__main__":
    unittest.main()
