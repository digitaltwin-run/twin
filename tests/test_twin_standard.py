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

    def test_every_operation_has_a_canonical_uri_matching_cqrs(self):
        document = self._document()
        self.assertTrue(document["operations"])
        for operation in document["operations"]:
            match = twin_standard.URI_ROUTE_PATTERN.fullmatch(operation["uri"])
            self.assertIsNotNone(match, operation["uri"])
            self.assertEqual(operation["kind"], match.group("effect"))

    def test_uri_query_string_and_embedded_identity_are_rejected(self):
        profile = self._fixture(
            lambda value: value["operations"][0].__setitem__(
                "uri", "twin://user@generic/aggregate/command/reconcile?token=no"
            )
        )
        self.assertIn("TWIN-URI-001", self._codes(profile))

    def test_uri_effect_must_match_operation_kind(self):
        profile = self._fixture(
            lambda value: value["operations"][0].__setitem__(
                "uri", "twin://generic/aggregate/query/reconcile"
            )
        )
        self.assertIn("TWIN-URI-001", self._codes(profile))

    def test_operation_uris_and_capabilities_are_unique(self):
        def mutate(value):
            value["operations"][1]["uri"] = value["operations"][0]["uri"]
            value["operations"][1]["capability"] = value["operations"][0]["capability"]

        profile = self._fixture(mutate)
        self.assertIn("TWIN-URI-001", self._codes(profile))
        self.assertIn("TWIN-CAPABILITY-001", self._codes(profile))

    def test_capability_requires_provider_and_risk(self):
        def mutate(value):
            value["operations"][0]["providerRef"] = ""
            value["operations"][0]["risk"] = "HIGH"

        profile = self._fixture(mutate)
        self.assertIn("TWIN-CAPABILITY-001", self._codes(profile))

    def test_uri_policy_and_optional_requirements_are_not_ambiguous(self):
        def mutate(value):
            value["uriCapabilities"]["routePattern"] = "any-uri"
            value["operations"][0]["preconditions"] = []

        profile = self._fixture(mutate)
        diagnostics = twin_standard.validate_profile(profile)
        self.assertIn("TWIN-URI-001", {item.code for item in diagnostics})
        self.assertIn("TWIN-CAPABILITY-001", {item.code for item in diagnostics})

    def test_resolution_policy_requires_every_typed_gap(self):
        profile = self._fixture(
            lambda value: value["uriCapabilities"]["typedGaps"].remove("provider_not_implemented")
        )
        self.assertIn("TWIN-CAPABILITY-001", self._codes(profile))

    def test_uri_routing_authority_is_not_authorization(self):
        profile = self._fixture(
            lambda value: value["uriCapabilities"].__setitem__("uriAuthorityIsAuthorization", True)
        )
        self.assertIn("TWIN-AUTH-001", self._codes(profile))

    def test_process_definition_is_immutable_and_versioned(self):
        def mutate(value):
            value["processes"][0]["immutable"] = False
            value["processes"][0]["version"] = 0

        profile = self._fixture(mutate)
        self.assertIn("TWIN-PROCESS-001", self._codes(profile))

    def test_multiple_immutable_process_versions_can_coexist(self):
        def mutate(value):
            revision = copy.deepcopy(value["processes"][0])
            revision["version"] = 2
            revision["uri"] = "twin://generic/process-v2/query/observe-reconcile-notify"
            value["processes"].append(revision)

        profile = self._fixture(mutate)
        self.assertEqual([], twin_standard.validate_profile(profile))

    def test_process_step_must_reference_a_declared_operation_and_uri(self):
        def mutate(value):
            value["processes"][0]["steps"][0]["operation"] = "uri.unknown"
            value["processes"][0]["steps"][1]["uri"] = "twin://generic/wrong/command/route"

        profile = self._fixture(mutate)
        diagnostics = twin_standard.validate_profile(profile)
        self.assertTrue(any(item.code == "TWIN-PROCESS-001" and "unknown operation" in item.message for item in diagnostics))
        self.assertIn("TWIN-URI-001", {item.code for item in diagnostics})

    def test_process_step_capability_and_provider_match_operation(self):
        def mutate(value):
            value["processes"][0]["steps"][0]["capability"] = "wrong.capability"
            value["processes"][0]["steps"][0]["providerRef"] = "effect-outbox"

        profile = self._fixture(mutate)
        self.assertIn("TWIN-CAPABILITY-001", self._codes(profile))

    def test_process_dependency_must_exist(self):
        profile = self._fixture(
            lambda value: value["processes"][0]["steps"][1]["dependsOn"].append("missing")
        )
        diagnostics = twin_standard.validate_profile(profile)
        self.assertTrue(any("unknown step missing" in item.message for item in diagnostics))
        self.assertFalse(any("acyclic" in item.message for item in diagnostics))

    def test_process_dependency_graph_must_be_acyclic(self):
        profile = self._fixture(
            lambda value: value["processes"][0]["steps"][0].__setitem__("dependsOn", ["notify"])
        )
        diagnostics = twin_standard.validate_profile(profile)
        self.assertTrue(any(item.code == "TWIN-PROCESS-001" and "acyclic" in item.message for item in diagnostics))

    def test_process_step_timeout_and_retry_are_bounded(self):
        def mutate(value):
            step = value["processes"][0]["steps"][0]
            step["timeoutMs"] = 0
            step["retry"]["maxAttempts"] = 11

        profile = self._fixture(mutate)
        self.assertIn("TWIN-PROCESS-001", self._codes(profile))

    def test_command_process_step_requires_external_authority_scope(self):
        profile = self._fixture(
            lambda value: value["processes"][0]["steps"][0].__setitem__("authorityScope", "")
        )
        self.assertIn("TWIN-AUTH-001", self._codes(profile))

    def test_compensation_requires_declared_inverse_command(self):
        profile = self._fixture(
            lambda value: value["processes"][0]["steps"][1].__setitem__("onFailure", "compensate")
        )
        self.assertIn("TWIN-PROCESS-001", self._codes(profile))

    def test_process_replay_never_dispatches_steps(self):
        profile = self._fixture(
            lambda value: value["processRuntime"].__setitem__("replayExecutesSteps", True)
        )
        self.assertIn("TWIN-REPLAY-001", self._codes(profile))

    def test_actor_twin_and_llm_cannot_grant_authority(self):
        def mutate(value):
            value["processRuntime"]["humanTaskCannotGrantAuthority"] = False
            value["processRuntime"]["llmVerdictCannotGrantAuthority"] = False

        profile = self._fixture(mutate)
        self.assertIn("TWIN-PROCESS-001", self._codes(profile))

    def test_lifecycle_modularity_and_twinstudio_sources_are_immutable(self):
        sources = {item["id"]: item for item in self._document()["contractSources"]}
        self.assertEqual(set(twin_standard.REQUIRED_CONTRACT_SOURCES), set(sources))
        self.assertEqual(
            "f3b8e13eb17128fd0f3ff05ac45fc99c99c470c4",
            sources["lifecycle-dsl"]["revision"],
        )
        self.assertEqual(
            "sha256:98db51af5b17e9a480f587f462da52aafd70d8b40ae87d873d7a42fdd4fd5a68",
            sources["modularity-workspace"]["digest"],
        )
        twinstudio = [source for source in sources.values() if source["id"].startswith("twinstudio-")]
        self.assertEqual({"4183807d9be0bb2a39149ddea494a224286f5dbb"}, {item["revision"] for item in twinstudio})

    def test_source_contract_rejects_moving_or_unhashed_provenance(self):
        def mutate(value):
            value["contractSources"][0]["revision"] = "main"
            value["contractSources"][1]["digest"] = "98db51af"

        profile = self._fixture(mutate)
        self.assertIn("TWIN-SOURCE-001", self._codes(profile))

    def test_additional_immutable_source_contract_is_portable(self):
        def mutate(value):
            value["contractSources"].append(
                {
                    "id": "language-adapter",
                    "role": "informative",
                    "repository": "https://example.invalid/twin-adapter",
                    "revision": "b" * 40,
                    "artifact": "contracts/adapter.json",
                    "digest": "sha256:" + "c" * 64,
                }
            )

        self.assertEqual([], twin_standard.validate_profile(self._fixture(mutate)))

    def test_twinstudio_evidence_must_use_one_coherent_revision(self):
        profile = self._fixture(
            lambda value: value["contractSources"][2].__setitem__(
                "revision", "a" * 40
            )
        )
        diagnostics = twin_standard.validate_profile(profile)
        self.assertTrue(
            any(item.code == "TWIN-SOURCE-001" and "coherent" in item.message for item in diagnostics)
        )

    def test_lifecycle_requires_evidence_fail_closed_states_and_authority_separation(self):
        def mutate(value):
            value["lifecycle"]["transitionEvidenceRequired"] = False
            value["lifecycle"]["approvalDoesNotGrantAuthority"] = False
            value["lifecycle"]["transitionStatuses"].remove("BLOCKED")

        codes = self._codes(self._fixture(mutate))
        self.assertIn("TWIN-LIFECYCLE-001", codes)
        self.assertIn("TWIN-AUTH-001", codes)

    def test_lifecycle_and_evolution_replay_are_observe_only(self):
        def mutate(value):
            value["lifecycle"]["replayExecutesTransitions"] = True
            value["evolution"]["replayExecutesChanges"] = True

        self.assertIn("TWIN-REPLAY-001", self._codes(self._fixture(mutate)))

    def test_lifecycle_and_evolution_state_sets_fail_closed_on_non_strings(self):
        def mutate(value):
            value["lifecycle"]["transitionStatuses"][0] = {"unknown": True}
            value["evolution"]["modes"][0] = ["analysis-only"]

        codes = self._codes(self._fixture(mutate))
        self.assertIn("TWIN-LIFECYCLE-001", codes)
        self.assertIn("TWIN-EVOLUTION-001", codes)

    def test_modularity_preserves_pins_dag_single_writer_and_scope(self):
        def mutate(value):
            value["modularity"]["moduleRevisionPinned"] = False
            value["modularity"]["dependencyGraphAcyclic"] = False
            value["modularity"]["singleWriterState"] = False
            value["modularity"]["analysisScopeBounded"] = False

        self.assertIn("TWIN-MODULARITY-001", self._codes(self._fixture(mutate)))

    def test_evolution_keeps_proposals_scores_and_verification_distinct(self):
        def mutate(value):
            value["evolution"]["candidateLineageRequired"] = False
            value["evolution"]["proposalIsEvidence"] = True
            value["evolution"]["evaluationScoreIsEvidence"] = True
            value["evolution"]["candidateStatuses"].remove("REALIZED")
            value["evolution"]["runStatuses"].remove("AWAITING_APPROVAL")
            value["evolution"]["changeQueueStates"].remove("VERIFYING")

        self.assertIn("TWIN-EVOLUTION-001", self._codes(self._fixture(mutate)))

    def test_auto_apply_safe_is_allowlisted_reversible_compatible_gated_and_authorized(self):
        def mutate(value):
            policy = value["evolution"]["autoApplySafe"]
            for field in list(policy):
                policy[field] = False

        self.assertIn("TWIN-EVOLUTION-001", self._codes(self._fixture(mutate)))

    def test_apply_revert_require_new_history_and_observed_artifacts(self):
        def mutate(value):
            value["evolution"]["newRevisionPerAppliedChange"] = False
            value["evolution"]["revertIsCompensatingEvent"] = False
            value["evolution"]["historyRewriteAllowed"] = True
            value["evolution"]["regenerationAfterApplyOrRevert"] = False
            value["evolution"]["readbackVerificationRequired"] = False

        self.assertIn("TWIN-EVOLUTION-001", self._codes(self._fixture(mutate)))

    def test_lifecycle_and_evolution_operations_are_portable_and_protobuf_backed(self):
        expected = {
            "twin.lifecycle.transition",
            "twin.lifecycle.get",
            "twin.evolution.plan",
            "twin.evolution.apply",
            "twin.evolution.revert",
            "twin.evolution.get",
        }
        document = self._document()
        self.assertTrue(expected.issubset({operation["id"] for operation in document["operations"]}))
        for surface in twin_standard.REQUIRED_SURFACES:
            bound = {item["operation"] for item in document["transports"][surface]["bindings"]}
            self.assertTrue(expected.issubset(bound), surface)

    def test_evolution_proto_carries_module_graph_lineage_and_readback(self):
        def remove_required_fields(text):
            return text.replace("  string modularity_graph_digest_sha256 = 4;\n", "", 1).replace(
                "  string readback_digest_sha256 = 8;\n", "", 1
            )

        self.assertIn("TWIN-PROTO-001", self._codes(self._fixture(proto_mutate=remove_required_fields)))

    def test_evolution_apply_requires_a_typed_rpc(self):
        profile = self._fixture(
            proto_mutate=lambda text: text.replace(
                "  rpc ApplyEvolution(ApplyEvolutionCommand) returns (CommandReceipt);\n", "", 1
            )
        )
        self.assertIn("TWIN-PROTO-001", self._codes(profile))

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

    def test_uri_process_proto_messages_are_required(self):
        profile = self._fixture(
            proto_mutate=lambda text: text.replace("message UriRoute {", "message RemovedUriRoute {", 1)
        )
        self.assertIn("TWIN-PROTO-001", self._codes(profile))

    def test_uri_process_proto_carries_capability_and_safety_flags(self):
        profile = self._fixture(
            proto_mutate=lambda text: text.replace("  string provider_ref = 12;\n", "", 1)
        )
        self.assertIn("TWIN-PROTO-001", self._codes(profile))

    def test_uri_process_operations_require_specialized_rpc(self):
        profile = self._fixture(
            proto_mutate=lambda text: text.replace(
                "  rpc Start(StartUriProcessCommand) returns (CommandReceipt);\n", "", 1
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

    def test_nested_proto_message_does_not_hide_outer_fields_or_share_numbers(self):
        profile = self._fixture(
            proto_mutate=lambda text: text.replace(
                "message ActorRef {",
                "message ActorRef {\n  message Annotation {\n    string value = 1;\n  }",
                1,
            )
        )
        self.assertEqual([], twin_standard.validate_profile(profile))

    def test_nested_proto_secret_field_fails_independently(self):
        profile = self._fixture(
            proto_mutate=lambda text: text.replace(
                "message ActorRef {",
                "message ActorRef {\n  message Credentials {\n    string Token = 1;\n  }",
                1,
            )
        )
        self.assertIn("TWIN-SECRET-001", self._codes(profile))

    def test_camel_case_proto_secret_field_fails(self):
        profile = self._fixture(
            proto_mutate=lambda text: text.replace(
                "message ActorRef {", "message ActorRef {\n  string credentialValue = 99;", 1
            )
        )
        self.assertIn("TWIN-SECRET-001", self._codes(profile))

    def test_unbalanced_proto_braces_fail(self):
        profile = self._fixture(proto_mutate=lambda text: text + "\nmessage Broken {\n")
        diagnostics = twin_standard.validate_profile(profile)
        self.assertTrue(
            any(item.code == "TWIN-PROTO-001" and "balanced" in item.message for item in diagnostics)
        )

    def test_proto_keywords_and_braces_inside_strings_are_not_declarations(self):
        profile = self._fixture(
            proto_mutate=lambda text: text.replace(
                "package subactor.twin.v1;",
                'package subactor.twin.v1;\noption java_package = "message Fake { string Token = 99;";',
                1,
            )
        )
        self.assertEqual([], twin_standard.validate_profile(profile))

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

    def test_generated_bundle_contains_uri_process_contracts(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        destination = Path(temporary.name) / "bundle"
        twin_standard.generate_bundle(PROFILE, destination, "rust")
        transport = json.loads((destination / "transport-map.json").read_text(encoding="utf-8"))
        conformance = json.loads((destination / "conformance.json").read_text(encoding="utf-8"))
        manifest = json.loads((destination / "twin.manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(self._document()["processes"], transport["processes"])
        self.assertEqual(1, manifest["uriProcessDefinitions"])
        process_cases = [item for item in conformance["cases"] if item["kind"] == "uri-process-step"]
        self.assertEqual(3, len(process_cases))

    def test_generated_bundle_contains_lifecycle_and_modular_evolution_contracts(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        destination = Path(temporary.name) / "bundle"
        twin_standard.generate_bundle(PROFILE, destination, "typescript")
        transport = json.loads((destination / "transport-map.json").read_text(encoding="utf-8"))
        conformance = json.loads((destination / "conformance.json").read_text(encoding="utf-8"))
        manifest = json.loads((destination / "twin.manifest.json").read_text(encoding="utf-8"))
        document = self._document()
        for field in ("contractSources", "lifecycle", "modularity", "evolution"):
            self.assertEqual(document[field], transport[field])
        source_cases = [item for item in conformance["cases"] if item["kind"] == "immutable-source-contract"]
        self.assertEqual(len(document["contractSources"]), len(source_cases))
        invariant_ids = {item["id"] for item in conformance["cases"] if item["kind"] == "semantic-invariant"}
        self.assertIn("invariant.lifecycle-approval-is-not-authority", invariant_ids)
        self.assertIn("invariant.module-contract-revisions-pinned", invariant_ids)
        self.assertIn("invariant.apply-revert-regenerate-and-readback", invariant_ids)
        self.assertEqual("1.1.0", manifest["standardVersion"])
        self.assertEqual(5, manifest["contractSources"])
        self.assertEqual(4, manifest["evolutionOperations"])

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
