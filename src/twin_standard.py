"""Deterministic validator and contract-bundle generator for Twin Standard v1."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from typing import Any, Iterable


STANDARD_VERSION = "1.0.0"
PROFILE_SCHEMA = "twin.profile/v1"
REQUIRED_TRAITS = {
    "reconciliation",
    "mirror",
    "invariant",
    "simulation",
    "preflight-verification",
    "notification",
    "outbox",
    "probe",
    "uri-process",
}
REQUIRED_SURFACES = ("cli", "shell", "rest", "mcp")
REQUIRED_EVENT_METADATA = {
    "event_id",
    "aggregate_id",
    "aggregate_type",
    "aggregate_version",
    "sequence",
    "event_type",
    "schema_version",
    "actor_ref",
    "authority_ref",
    "correlation_id",
    "causation_id",
    "idempotency_key",
    "occurred_at",
    "evidence",
    "payload",
}
REQUIRED_COMMAND_FIELDS = {
    "operation_id",
    "command_id",
    "aggregate_id",
    "aggregate_type",
    "expected_version",
    "idempotency_key",
    "actor_ref",
    "authority_ref",
    "correlation_id",
    "causation_id",
    "occurred_at",
    "payload",
}
REQUIRED_RECEIPT_FIELDS = {
    "receipt_id",
    "command_id",
    "aggregate_id",
    "authority_ref",
    "aggregate_version",
    "event_ids",
    "status",
}
REQUIRED_MESSAGES = {
    "CommandEnvelope",
    "EventEnvelope",
    "QueryEnvelope",
    "CommandReceipt",
    "QueryResult",
    "Observation",
    "EvidenceRef",
    "OutboxMessage",
    "UriRoute",
    "UriCapability",
    "ResolutionGap",
    "CapabilityMap",
    "RetryPolicy",
    "UriProcessStep",
    "UriProcessDefinition",
    "UriProcessPlan",
    "UriProcessRun",
    "UriStepReceipt",
    "HumanTask",
}
REQUIRED_SERVICES = {
    "TwinCommandService",
    "TwinQueryService",
    "TwinEventStore",
    "TwinProjectionService",
    "TwinUriProcessCommandService",
    "TwinUriProcessQueryService",
}
EXPECTED_OUTPUTS = [
    "twin.manifest.json",
    "proto/twin/v1/twin.proto",
    "transport-map.json",
    "conformance.json",
]
LANGUAGE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.+\-]{0,63}$")
OPERATION_PATTERN = re.compile(r"^(?:twin|uri)\.[a-z][a-z0-9.\-]*$")
CAPABILITY_PATTERN = re.compile(r"^[a-z][a-z0-9.\-]*$")
URI_ROUTE_GRAMMAR = "scheme://uri-authority/resource[/subresource...]/query|command/action"
URI_ROUTE_PATTERN = re.compile(
    r"^(?P<scheme>[a-z][a-z0-9+.-]*)://"
    r"(?P<authority>[A-Za-z0-9._~-]+)"
    r"(?P<resources>(?:/[A-Za-z0-9._~-]+)+)/"
    r"(?P<effect>query|command)/(?P<action>[A-Za-z0-9._~-]+)$"
)
REQUIRED_RESOLUTION_GAPS = {
    "connector_unavailable",
    "provider_not_implemented",
    "credential_missing",
    "capability_missing",
    "precondition_failed",
    "authority_missing",
}
REQUIRED_PROCESS_STATES = {
    "PLANNED",
    "WAITING",
    "READY",
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    "CANCELLED",
    "COMPENSATING",
    "COMPENSATED",
}
REQUIRED_TERMINAL_STATES = {"SUCCEEDED", "FAILED", "CANCELLED", "COMPENSATED"}
REQUIRED_HUMAN_TASK_STATES = {"PENDING", "RESOLVED", "DECLINED", "CANCELLED", "EXPIRED"}
UNSAFE_SHELL_PATTERN = re.compile(r"[;&|`$<>\n\r]")


class DuplicateKeyError(ValueError):
    """Raised when JSON contains an ambiguous duplicate object key."""


class ContractInvalid(Exception):
    """Raised when generation receives an invalid profile."""

    def __init__(self, diagnostics: list["Diagnostic"]):
        super().__init__("Twin profile is invalid")
        self.diagnostics = diagnostics


class GenerationError(Exception):
    """Raised when generation cannot safely publish output."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, order=True)
class Diagnostic:
    code: str
    path: str
    message: str


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate key: {key}")
        result[key] = value
    return result


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream, object_pairs_hook=_unique_object)
    if not isinstance(value, dict):
        raise ValueError("top-level JSON value must be an object")
    return value


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _add(
    diagnostics: list[Diagnostic], code: str, path: str, message: str
) -> None:
    diagnostics.append(Diagnostic(code, path, message))


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _validate_profile_shape(profile: dict[str, Any], diagnostics: list[Diagnostic]) -> None:
    if profile.get("schema") != PROFILE_SCHEMA:
        _add(diagnostics, "TWIN-PROFILE-001", "$.schema", f"must equal {PROFILE_SCHEMA}")
    if not isinstance(profile.get("id"), str) or not profile.get("id"):
        _add(diagnostics, "TWIN-PROFILE-001", "$.id", "must be a non-empty string")
    if not isinstance(profile.get("version"), int) or profile.get("version", 0) < 1:
        _add(diagnostics, "TWIN-PROFILE-001", "$.version", "must be a positive integer")
    aggregate = _dict(profile.get("aggregate"))
    if not aggregate.get("type"):
        _add(diagnostics, "TWIN-PROFILE-001", "$.aggregate.type", "is required")


def _validate_event_sourcing(profile: dict[str, Any], diagnostics: list[Diagnostic]) -> None:
    event_sourcing = _dict(profile.get("eventSourcing"))
    for field in (
        "appendOnly",
        "optimisticConcurrency",
        "expectedVersionRequired",
        "transactionalOutbox",
    ):
        if event_sourcing.get(field) is not True:
            _add(diagnostics, "TWIN-EVENT-001", f"$.eventSourcing.{field}", "must be true")
    metadata = event_sourcing.get("requiredMetadata")
    metadata_set = {item for item in _list(metadata) if isinstance(item, str)}
    for missing in sorted(REQUIRED_EVENT_METADATA - metadata_set):
        _add(
            diagnostics,
            "TWIN-EVENT-001",
            "$.eventSourcing.requiredMetadata",
            f"missing canonical EventEnvelope field {missing}",
        )
    aggregate = _dict(profile.get("aggregate"))
    if aggregate.get("snapshotSourceOfTruth") is not False:
        _add(
            diagnostics,
            "TWIN-REPLAY-001",
            "$.aggregate.snapshotSourceOfTruth",
            "snapshots must be caches, never the source of truth",
        )
    if event_sourcing.get("replayDefault") != "observe":
        _add(
            diagnostics,
            "TWIN-REPLAY-001",
            "$.eventSourcing.replayDefault",
            "must equal observe",
        )
    if event_sourcing.get("replayExecutesEffects") is not False:
        _add(
            diagnostics,
            "TWIN-REPLAY-001",
            "$.eventSourcing.replayExecutesEffects",
            "replay must not execute historical effects",
        )


def _validate_core_boundaries(profile: dict[str, Any], diagnostics: list[Diagnostic]) -> None:
    cqrs = _dict(profile.get("cqrs"))
    expected_cqrs = {
        "commandsEmitEvents": True,
        "queriesReadProjections": True,
        "commandsWriteProjections": False,
        "queriesEmitEvents": False,
    }
    for field, expected in expected_cqrs.items():
        if cqrs.get(field) is not expected:
            _add(diagnostics, "TWIN-CQRS-001", f"$.cqrs.{field}", f"must be {str(expected).lower()}")

    authority = _dict(profile.get("authority"))
    if authority.get("requiredForMutations") is not True:
        _add(
            diagnostics,
            "TWIN-AUTH-001",
            "$.authority.requiredForMutations",
            "every mutation must require an authority reference",
        )
    if authority.get("receiptsRequired") is not True:
        _add(
            diagnostics,
            "TWIN-AUTH-001",
            "$.authority.receiptsRequired",
            "accepted mutations must produce receipts",
        )
    secrets = _dict(authority.get("secrets"))
    if secrets.get("handlesOnly") is not True or secrets.get("valuesForbidden") is not True:
        _add(
            diagnostics,
            "TWIN-SECRET-001",
            "$.authority.secrets",
            "must allow opaque handles only and forbid secret values",
        )

    connectors = _list(profile.get("connectors"))
    if not connectors:
        _add(diagnostics, "TWIN-CONNECTOR-001", "$.connectors", "at least one outbox adapter is required")
    for index, raw in enumerate(connectors):
        connector = _dict(raw)
        path = f"$.connectors[{index}]"
        if connector.get("owner") != "adapter":
            _add(diagnostics, "TWIN-CONNECTOR-001", path + ".owner", "must equal adapter")
        for field in ("domainRules", "eventStore", "authorityDecisions"):
            if connector.get(field) is not False:
                _add(diagnostics, "TWIN-CONNECTOR-001", path + f".{field}", "must be false")

    observability = _dict(profile.get("observability"))
    if observability.get("evidenceRequired") is not True:
        _add(diagnostics, "TWIN-EVIDENCE-001", "$.observability.evidenceRequired", "must be true")
    join_keys = set(item for item in _list(observability.get("requiredJoinKeys")) if isinstance(item, str))
    for missing in sorted({"aggregate_id", "target_uri"} - join_keys):
        _add(
            diagnostics,
            "TWIN-EVIDENCE-001",
            "$.observability.requiredJoinKeys",
            f"missing evidence join key {missing}",
        )
    unevaluable = observability.get("unevaluableState")
    healthy = set(item for item in _list(observability.get("healthyStates")) if isinstance(item, str))
    if unevaluable != "UNEVALUABLE" or unevaluable in healthy:
        _add(
            diagnostics,
            "TWIN-EVIDENCE-001",
            "$.observability.unevaluableState",
            "UNEVALUABLE must exist and must not be healthy",
        )


def _validate_operations(
    profile: dict[str, Any], diagnostics: list[Diagnostic]
) -> dict[str, dict[str, Any]]:
    operations: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(_list(profile.get("operations"))):
        operation = _dict(raw)
        path = f"$.operations[{index}]"
        operation_id = operation.get("id")
        if not isinstance(operation_id, str) or not OPERATION_PATTERN.fullmatch(operation_id):
            _add(diagnostics, "TWIN-OPERATION-001", path + ".id", "must be a canonical twin.* or uri.* operation ID")
            continue
        if operation_id in operations:
            _add(diagnostics, "TWIN-OPERATION-001", path + ".id", f"duplicate operation {operation_id}")
            continue
        operations[operation_id] = operation
        kind = operation.get("kind")
        if kind not in {"command", "query"}:
            _add(diagnostics, "TWIN-OPERATION-001", path + ".kind", "must be command or query")
        for field in ("request", "response"):
            if not isinstance(operation.get(field), str) or "." not in operation.get(field, ""):
                _add(diagnostics, "TWIN-OPERATION-001", path + f".{field}", "must be a qualified protobuf message")
        if kind == "command":
            emitted = _list(operation.get("emits"))
            if operation.get("mutating") is not True or not emitted:
                _add(
                    diagnostics,
                    "TWIN-CQRS-001",
                    path,
                    "a command must be mutating and declare emitted events",
                )
            if not all(isinstance(event, str) and "." in event for event in emitted):
                _add(
                    diagnostics,
                    "TWIN-OPERATION-001",
                    path + ".emits",
                    "every emitted event must be a qualified protobuf message",
                )
            if "projection" in operation:
                _add(diagnostics, "TWIN-CQRS-001", path + ".projection", "a command must not own a projection")
        elif kind == "query":
            if operation.get("mutating") is not False or not isinstance(operation.get("projection"), str):
                _add(
                    diagnostics,
                    "TWIN-CQRS-001",
                    path,
                    "a query must be non-mutating and read a named projection",
                )
            if "emits" in operation:
                _add(diagnostics, "TWIN-CQRS-001", path + ".emits", "a query must not emit events")
    if not operations:
        _add(diagnostics, "TWIN-OPERATION-001", "$.operations", "at least one operation is required")
    return operations


def _validate_uri_operations(
    profile: dict[str, Any], operations: dict[str, dict[str, Any]], diagnostics: list[Diagnostic]
) -> None:
    seen_uris: dict[str, str] = {}
    seen_capabilities: dict[str, str] = {}
    reviewed_providers = {"twin-core"} | {
        connector.get("id")
        for raw in _list(profile.get("connectors"))
        if (connector := _dict(raw)) and isinstance(connector.get("id"), str)
    }
    for operation_id, operation in operations.items():
        path = f"$.operations[{operation_id}]"
        uri = operation.get("uri")
        match = URI_ROUTE_PATTERN.fullmatch(uri) if isinstance(uri, str) else None
        if not match:
            _add(
                diagnostics,
                "TWIN-URI-001",
                path + ".uri",
                "must match scheme://uri-authority/resource.../(query|command)/action without query or fragment",
            )
        else:
            expected_effect = operation.get("kind")
            if match.group("effect") != expected_effect:
                _add(
                    diagnostics,
                    "TWIN-URI-001",
                    path + ".uri",
                    f"URI effect {match.group('effect')} disagrees with {expected_effect}",
                )
            previous = seen_uris.get(uri)
            if previous:
                _add(diagnostics, "TWIN-URI-001", path + ".uri", f"duplicates operation URI owned by {previous}")
            else:
                seen_uris[uri] = operation_id

        capability = operation.get("capability")
        if not isinstance(capability, str) or not CAPABILITY_PATTERN.fullmatch(capability):
            _add(
                diagnostics,
                "TWIN-CAPABILITY-001",
                path + ".capability",
                "must be a canonical capability identifier",
            )
        else:
            previous = seen_capabilities.get(capability)
            if previous:
                _add(
                    diagnostics,
                    "TWIN-CAPABILITY-001",
                    path + ".capability",
                    f"duplicates capability owned by {previous}",
                )
            else:
                seen_capabilities[capability] = operation_id
        if operation.get("providerRef") not in reviewed_providers:
            _add(
                diagnostics,
                "TWIN-CAPABILITY-001",
                path + ".providerRef",
                "must identify twin-core or a declared reviewed connector",
            )
        if not isinstance(operation.get("risk"), str) or not re.fullmatch(r"R[0-4]", operation.get("risk", "")):
            _add(diagnostics, "TWIN-CAPABILITY-001", path + ".risk", "must be a risk class from R0 through R4")
        if operation.get("status") not in {"available", "planned", "unavailable"}:
            _add(
                diagnostics,
                "TWIN-CAPABILITY-001",
                path + ".status",
                "must be available, planned or unavailable",
            )
        for field in ("credentialRefs", "requiresCapabilities", "featureFlags", "preconditions"):
            if field in operation:
                values = operation.get(field)
                if (
                    not isinstance(values, list)
                    or not values
                    or not all(isinstance(item, str) and item for item in values)
                ):
                    _add(
                        diagnostics,
                        "TWIN-CAPABILITY-001",
                        path + f".{field}",
                        "must be an array of non-empty identifiers or reviewed preconditions",
                    )


def _validate_traits(
    profile: dict[str, Any], operations: dict[str, dict[str, Any]], diagnostics: list[Diagnostic]
) -> None:
    seen: set[str] = set()
    for index, raw in enumerate(_list(profile.get("traits"))):
        trait = _dict(raw)
        trait_id = trait.get("id")
        path = f"$.traits[{index}]"
        if not isinstance(trait_id, str) or not trait_id:
            _add(diagnostics, "TWIN-TRAIT-001", path + ".id", "must be a non-empty string")
            continue
        if trait_id in seen:
            _add(diagnostics, "TWIN-TRAIT-001", path + ".id", f"duplicate trait {trait_id}")
        seen.add(trait_id)
        trait_operations = _list(trait.get("operations"))
        if not trait_operations:
            _add(diagnostics, "TWIN-TRAIT-001", path + ".operations", "trait must expose an operation")
        for operation_id in trait_operations:
            if operation_id not in operations:
                _add(
                    diagnostics,
                    "TWIN-TRAIT-001",
                    path + ".operations",
                    f"unknown operation {operation_id}",
                )
    for missing in sorted(REQUIRED_TRAITS - seen):
        _add(diagnostics, "TWIN-TRAIT-001", "$.traits", f"missing required trait {missing}")


def _validate_uri_process_policy(profile: dict[str, Any], diagnostics: list[Diagnostic]) -> None:
    capabilities = _dict(profile.get("uriCapabilities"))
    if capabilities.get("routePattern") != URI_ROUTE_GRAMMAR:
        _add(
            diagnostics,
            "TWIN-URI-001",
            "$.uriCapabilities.routePattern",
            f"must equal {URI_ROUTE_GRAMMAR}",
        )
    for field in (
        "reviewedBaselineRequired",
        "liveDiscoveryRequired",
        "capabilityMapHashRequired",
        "resolutionBeforeExecution",
        "plannedRouteFailsClosed",
        "connectorRouteMustMatchPlan",
    ):
        if capabilities.get(field) is not True:
            _add(diagnostics, "TWIN-CAPABILITY-001", f"$.uriCapabilities.{field}", "must be true")
    if capabilities.get("uriAuthorityIsAuthorization") is not False:
        _add(
            diagnostics,
            "TWIN-AUTH-001",
            "$.uriCapabilities.uriAuthorityIsAuthorization",
            "URI routing authority must never be authorization authority",
        )
    gaps = _list(capabilities.get("typedGaps"))
    gap_set = {gap for gap in gaps if isinstance(gap, str)}
    if len(gap_set) != len(gaps):
        _add(diagnostics, "TWIN-CAPABILITY-001", "$.uriCapabilities.typedGaps", "must be unique strings")
    for missing in sorted(REQUIRED_RESOLUTION_GAPS - gap_set):
        _add(
            diagnostics,
            "TWIN-CAPABILITY-001",
            "$.uriCapabilities.typedGaps",
            f"missing fail-closed resolution gap {missing}",
        )

    runtime = _dict(profile.get("processRuntime"))
    for field in (
        "definitionImmutable",
        "planPinnedToCapabilityMapHash",
        "stepTimeoutRequired",
        "stepRetryDeclared",
        "stepIdempotencyRequired",
        "stepReceiptsRequired",
        "compensationExplicit",
        "humanTaskCannotGrantAuthority",
        "llmVerdictCannotGrantAuthority",
    ):
        if runtime.get(field) is not True:
            _add(diagnostics, "TWIN-PROCESS-001", f"$.processRuntime.{field}", "must be true")
    if runtime.get("replayExecutesSteps") is not False:
        _add(
            diagnostics,
            "TWIN-REPLAY-001",
            "$.processRuntime.replayExecutesSteps",
            "process replay must never dispatch URI steps",
        )
    for field, required in (
        ("states", REQUIRED_PROCESS_STATES),
        ("terminalStates", REQUIRED_TERMINAL_STATES),
        ("humanTaskStates", REQUIRED_HUMAN_TASK_STATES),
    ):
        actual = {item for item in _list(runtime.get(field)) if isinstance(item, str)}
        for missing in sorted(required - actual):
            _add(diagnostics, "TWIN-PROCESS-001", f"$.processRuntime.{field}", f"missing state {missing}")
    terminal = {item for item in _list(runtime.get("terminalStates")) if isinstance(item, str)}
    if terminal - REQUIRED_PROCESS_STATES:
        _add(
            diagnostics,
            "TWIN-PROCESS-001",
            "$.processRuntime.terminalStates",
            "terminal states must belong to the declared process state machine",
        )


def _process_graph_has_cycle(step_ids: set[str], dependencies: dict[str, set[str]]) -> bool:
    remaining = {
        step_id: set(dependencies.get(step_id, set())) & step_ids
        for step_id in step_ids
    }
    while remaining:
        ready = {step_id for step_id, required in remaining.items() if not required}
        if not ready:
            return True
        for step_id in ready:
            remaining.pop(step_id)
        for required in remaining.values():
            required.difference_update(ready)
    return False


def _validate_processes(
    profile: dict[str, Any], operations: dict[str, dict[str, Any]], diagnostics: list[Diagnostic]
) -> None:
    processes = _list(profile.get("processes"))
    if not processes:
        _add(diagnostics, "TWIN-PROCESS-001", "$.processes", "at least one URI Process definition is required")
        return
    process_revisions: set[tuple[str, int]] = set()
    process_uris: set[str] = set()
    uri_operations = {
        operation.get("uri"): operation
        for operation in operations.values()
        if isinstance(operation.get("uri"), str)
    }
    for process_index, raw_process in enumerate(processes):
        process = _dict(raw_process)
        path = f"$.processes[{process_index}]"
        process_id = process.get("id")
        process_version = process.get("version")
        if not isinstance(process_id, str) or not CAPABILITY_PATTERN.fullmatch(process_id):
            _add(diagnostics, "TWIN-PROCESS-001", path + ".id", "must be a canonical immutable process ID")
        elif type(process_version) is int and process_version > 0:
            revision = (process_id, process_version)
            if revision in process_revisions:
                _add(
                    diagnostics,
                    "TWIN-PROCESS-001",
                    path + ".version",
                    f"duplicate immutable process revision {process_id}@{process_version}",
                )
            else:
                process_revisions.add(revision)
        process_uri = process.get("uri")
        process_uri_match = URI_ROUTE_PATTERN.fullmatch(process_uri) if isinstance(process_uri, str) else None
        if not process_uri_match or process_uri_match.group("effect") != "query":
            _add(
                diagnostics,
                "TWIN-URI-001",
                path + ".uri",
                "a process definition must have a canonical query URI",
            )
        elif process_uri in process_uris or process_uri in uri_operations:
            _add(diagnostics, "TWIN-URI-001", path + ".uri", "process URI must be globally unique")
        else:
            process_uris.add(process_uri)
        if type(process_version) is not int or process_version < 1:
            _add(diagnostics, "TWIN-PROCESS-001", path + ".version", "must be a positive integer")
        if process.get("immutable") is not True:
            _add(diagnostics, "TWIN-PROCESS-001", path + ".immutable", "must be true")
        if not isinstance(process.get("intent"), str) or not process.get("intent"):
            _add(diagnostics, "TWIN-PROCESS-001", path + ".intent", "must describe the process outcome")

        steps = _list(process.get("steps"))
        if not steps:
            _add(diagnostics, "TWIN-PROCESS-001", path + ".steps", "must contain at least one step")
            continue
        step_ids: set[str] = set()
        dependencies: dict[str, set[str]] = {}
        for step_index, raw_step in enumerate(steps):
            step = _dict(raw_step)
            step_path = f"{path}.steps[{step_index}]"
            step_id = step.get("id")
            if not isinstance(step_id, str) or not CAPABILITY_PATTERN.fullmatch(step_id):
                _add(diagnostics, "TWIN-PROCESS-001", step_path + ".id", "must be a canonical step ID")
                continue
            if step_id in step_ids:
                _add(diagnostics, "TWIN-PROCESS-001", step_path + ".id", f"duplicate step {step_id}")
            step_ids.add(step_id)
            dependency_values = _list(step.get("dependsOn"))
            if not all(isinstance(item, str) and item for item in dependency_values):
                _add(diagnostics, "TWIN-PROCESS-001", step_path + ".dependsOn", "must contain step IDs")
            dependencies[step_id] = {item for item in dependency_values if isinstance(item, str)}

            operation_id = step.get("operation")
            operation = operations.get(operation_id)
            if not operation:
                _add(diagnostics, "TWIN-PROCESS-001", step_path + ".operation", f"unknown operation {operation_id}")
            else:
                if step.get("uri") != operation.get("uri"):
                    _add(
                        diagnostics,
                        "TWIN-URI-001",
                        step_path + ".uri",
                        "must exactly match the URI owned by the declared operation",
                    )
                for step_field, operation_field in (
                    ("capability", "capability"),
                    ("providerRef", "providerRef"),
                ):
                    if step.get(step_field) != operation.get(operation_field):
                        _add(
                            diagnostics,
                            "TWIN-CAPABILITY-001",
                            step_path + f".{step_field}",
                            f"must exactly match {operation_field} owned by the declared operation",
                        )
            timeout = step.get("timeoutMs")
            if type(timeout) is not int or timeout < 1:
                _add(diagnostics, "TWIN-PROCESS-001", step_path + ".timeoutMs", "must be a positive integer")
            retry = _dict(step.get("retry"))
            attempts = retry.get("maxAttempts")
            backoff = retry.get("backoffMs")
            if type(attempts) is not int or not 1 <= attempts <= 10:
                _add(
                    diagnostics,
                    "TWIN-PROCESS-001",
                    step_path + ".retry.maxAttempts",
                    "must be between 1 and 10",
                )
            if type(backoff) is not int or backoff < 0:
                _add(diagnostics, "TWIN-PROCESS-001", step_path + ".retry.backoffMs", "must be non-negative")
            failure_policy = step.get("onFailure")
            if failure_policy not in {"stop", "continue", "compensate"}:
                _add(diagnostics, "TWIN-PROCESS-001", step_path + ".onFailure", "must be stop, continue or compensate")
            for field in ("idempotencyRequired", "receiptRequired"):
                if step.get(field) is not True:
                    _add(diagnostics, "TWIN-PROCESS-001", step_path + f".{field}", "must be true")
            reversible = step.get("reversible")
            inverse_uri = step.get("inverseUri")
            if reversible is not True and reversible is not False:
                _add(diagnostics, "TWIN-PROCESS-001", step_path + ".reversible", "must be boolean")
            if reversible is True:
                inverse_operation = uri_operations.get(inverse_uri)
                if not inverse_operation or inverse_operation.get("kind") != "command":
                    _add(
                        diagnostics,
                        "TWIN-PROCESS-001",
                        step_path + ".inverseUri",
                        "a reversible step must name a declared command URI",
                    )
            elif inverse_uri is not None:
                _add(diagnostics, "TWIN-PROCESS-001", step_path + ".inverseUri", "is allowed only when reversible")
            if failure_policy == "compensate" and reversible is not True:
                _add(
                    diagnostics,
                    "TWIN-PROCESS-001",
                    step_path + ".onFailure",
                    "compensate requires an explicit reversible inverse URI",
                )
            if operation and operation.get("kind") == "command":
                if not isinstance(step.get("authorityScope"), str) or not step.get("authorityScope"):
                    _add(
                        diagnostics,
                        "TWIN-AUTH-001",
                        step_path + ".authorityScope",
                        "every command step must name an external authority scope",
                    )

        for step_id, required in dependencies.items():
            for dependency in sorted(required - step_ids):
                _add(
                    diagnostics,
                    "TWIN-PROCESS-001",
                    path + ".steps",
                    f"step {step_id} depends on unknown step {dependency}",
                )
            if step_id in required:
                _add(diagnostics, "TWIN-PROCESS-001", path + ".steps", f"step {step_id} depends on itself")
        if _process_graph_has_cycle(step_ids, dependencies):
            _add(diagnostics, "TWIN-PROCESS-001", path + ".steps", "step dependency graph must be acyclic")


def _binding_operation_counts(bindings: list[Any]) -> Counter[str]:
    return Counter(
        binding.get("operation")
        for raw in bindings
        if (binding := _dict(raw)) and isinstance(binding.get("operation"), str)
    )


def _validate_transports(
    profile: dict[str, Any], operations: dict[str, dict[str, Any]], diagnostics: list[Diagnostic]
) -> None:
    transports = _dict(profile.get("transports"))
    operation_ids = set(operations)
    for surface_name in REQUIRED_SURFACES:
        surface = _dict(transports.get(surface_name))
        path = f"$.transports.{surface_name}"
        if surface.get("enabled") is not True:
            _add(diagnostics, "TWIN-TRANSPORT-001", path + ".enabled", "surface must be enabled")
        bindings = _list(surface.get("bindings"))
        counts = _binding_operation_counts(bindings)
        for operation_id in sorted(operation_ids | set(counts)):
            count = counts.get(operation_id, 0)
            if operation_id not in operation_ids:
                _add(diagnostics, "TWIN-TRANSPORT-001", path + ".bindings", f"unknown operation {operation_id}")
            elif count != 1:
                _add(
                    diagnostics,
                    "TWIN-TRANSPORT-001",
                    path + ".bindings",
                    f"operation {operation_id} must have exactly one binding; found {count}",
                )

        unique_surface_keys: set[Any] = set()
        for index, raw in enumerate(bindings):
            binding = _dict(raw)
            binding_path = f"{path}.bindings[{index}]"
            operation = operations.get(binding.get("operation"), {})
            if surface_name in {"cli", "shell"}:
                argv = binding.get("argv")
                if not isinstance(argv, list) or not argv or not all(isinstance(arg, str) and arg for arg in argv):
                    _add(diagnostics, "TWIN-TRANSPORT-001", binding_path + ".argv", "must be a non-empty string array")
                    continue
                key = tuple(argv)
                if surface_name == "shell" and any(UNSAFE_SHELL_PATTERN.search(arg) for arg in argv):
                    _add(
                        diagnostics,
                        "TWIN-SHELL-001",
                        binding_path + ".argv",
                        "argv contains shell evaluation or redirection syntax",
                    )
            elif surface_name == "rest":
                method = binding.get("method")
                route = binding.get("path")
                key = (method, route)
                expected_method = "POST" if operation.get("kind") == "command" else "GET"
                if method != expected_method or not isinstance(route, str) or not route.startswith("/"):
                    _add(
                        diagnostics,
                        "TWIN-REST-001",
                        binding_path,
                        f"must use {expected_method} and an absolute path",
                    )
            else:
                key = binding.get("name")
                expected_kind = "tool" if operation.get("kind") == "command" else {"tool", "resource"}
                actual_kind = binding.get("kind")
                kind_valid = actual_kind == expected_kind if isinstance(expected_kind, str) else actual_kind in expected_kind
                if not kind_valid or not isinstance(key, str) or not key:
                    _add(diagnostics, "TWIN-MCP-001", binding_path, "MCP binding kind or name is invalid")
                if operation.get("kind") == "command" and binding.get("requiresAuthority") is not True:
                    _add(
                        diagnostics,
                        "TWIN-MCP-001",
                        binding_path + ".requiresAuthority",
                        "mutating MCP tools must require authority",
                    )
            if key in unique_surface_keys:
                _add(diagnostics, "TWIN-TRANSPORT-001", binding_path, "binding endpoint must be unique")
            unique_surface_keys.add(key)

    shell = _dict(transports.get("shell"))
    for field in ("argvOnly", "noEval", "noInterpolation"):
        if shell.get(field) is not True:
            _add(diagnostics, "TWIN-SHELL-001", f"$.transports.shell.{field}", "must be true")
    if "command" in shell:
        _add(diagnostics, "TWIN-SHELL-001", "$.transports.shell.command", "raw shell command text is forbidden")

    rest = _dict(transports.get("rest"))
    if rest.get("encoding") != "protojson":
        _add(diagnostics, "TWIN-REST-001", "$.transports.rest.encoding", "must equal protojson")

    mcp = _dict(transports.get("mcp"))
    if mcp.get("protocol") != "json-rpc" or mcp.get("encoding") != "protojson":
        _add(
            diagnostics,
            "TWIN-MCP-001",
            "$.transports.mcp",
            "MCP must use native JSON-RPC with ProtoJSON message mapping",
        )
    mcp_transports = set(item for item in _list(mcp.get("transports")) if isinstance(item, str))
    if not {"stdio", "streamable-http"}.issubset(mcp_transports):
        _add(
            diagnostics,
            "TWIN-MCP-001",
            "$.transports.mcp.transports",
            "stdio and streamable-http support are required",
        )


def _strip_proto_comments(text: str) -> str:
    result: list[str] = []
    index = 0
    quoted = False
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if quoted:
            result.append(char)
            if char == "\\" and index + 1 < len(text):
                result.append(text[index + 1])
                index += 2
                continue
            if char == '"':
                quoted = False
            index += 1
            continue
        if char == '"':
            quoted = True
            result.append(char)
            index += 1
            continue
        if char == "/" and next_char == "/":
            result.extend((" ", " "))
            index += 2
            while index < len(text) and text[index] != "\n":
                result.append(" ")
                index += 1
            continue
        if char == "/" and next_char == "*":
            result.extend((" ", " "))
            index += 2
            while index < len(text):
                if index + 1 < len(text) and text[index : index + 2] == "*/":
                    result.extend((" ", " "))
                    index += 2
                    break
                result.append("\n" if text[index] == "\n" else " ")
                index += 1
            continue
        result.append(char)
        index += 1
    return "".join(result)


def _mask_proto_strings(text: str) -> str:
    result = list(text)
    index = 0
    quoted = False
    while index < len(text):
        char = text[index]
        if quoted:
            if char != "\n":
                result[index] = " "
            if char == "\\" and index + 1 < len(text):
                index += 1
                if text[index] != "\n":
                    result[index] = " "
            elif char == '"':
                quoted = False
            index += 1
            continue
        if char == '"':
            quoted = True
            result[index] = " "
        index += 1
    return "".join(result)


def _proto_brace_depths(structure: str) -> tuple[list[int], bool]:
    depths = [0] * (len(structure) + 1)
    depth = 0
    valid = True
    for index, char in enumerate(structure):
        depths[index] = depth
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                valid = False
    depths[len(structure)] = depth
    return depths, valid and depth == 0


def _matching_proto_brace(structure: str, opening: int) -> int | None:
    depth = 0
    for index in range(opening, len(structure)):
        if structure[index] == "{":
            depth += 1
        elif structure[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    return None


def _proto_blocks(text: str, keyword: str) -> list[tuple[str, str, int]]:
    structure = _mask_proto_strings(text)
    depths, _ = _proto_brace_depths(structure)
    pattern = re.compile(rf"\b{re.escape(keyword)}\s+([A-Za-z_]\w*)\s*\{{")
    blocks: list[tuple[str, str, int]] = []
    for match in pattern.finditer(structure):
        opening = match.end() - 1
        closing = _matching_proto_brace(structure, opening)
        if closing is not None:
            blocks.append((match.group(1), text[opening + 1 : closing], depths[match.start()]))
    return blocks


def _message_scope_body(body: str) -> str:
    structure = _mask_proto_strings(body)
    pattern = re.compile(r"\b(?:message|enum)\s+[A-Za-z_]\w*\s*\{")
    masked = list(body)
    for match in pattern.finditer(structure):
        closing = _matching_proto_brace(structure, match.end() - 1)
        if closing is None:
            continue
        for index in range(match.start(), closing + 1):
            if masked[index] != "\n":
                masked[index] = " "
    return "".join(masked)


_PROTO_FIELD_PATTERN = re.compile(
    r"(?:\b(?:optional|repeated)\s+)?"
    r"(?:map\s*<\s*[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\s*,\s*"
    r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\s*>|\.?[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)"
    r"\s+([A-Za-z_]\w*)\s*=\s*(\d+)\b"
)


def _proto_fields(body: str) -> list[tuple[str, str]]:
    scope = _mask_proto_strings(_message_scope_body(body))
    return [match.groups() for match in _PROTO_FIELD_PATTERN.finditer(scope)]


def _profile_root(profile_path: Path) -> Path:
    parent = profile_path.resolve().parent
    return parent.parent if parent.name == "profiles" else parent


def _validate_proto(
    profile: dict[str, Any], profile_path: Path, operations: dict[str, dict[str, Any]], diagnostics: list[Diagnostic]
) -> None:
    declaration = _dict(profile.get("protobuf"))
    relative = declaration.get("path")
    package = declaration.get("package")
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
        _add(diagnostics, "TWIN-PROTO-001", "$.protobuf.path", "must be a safe repository-relative path")
        return
    if not isinstance(package, str) or not package:
        _add(diagnostics, "TWIN-PROTO-001", "$.protobuf.package", "must be a non-empty package")
        return
    root = _profile_root(profile_path)
    proto_path = (root / relative).resolve()
    try:
        proto_path.relative_to(root.resolve())
    except ValueError:
        _add(diagnostics, "TWIN-PROTO-001", "$.protobuf.path", "escapes the profile root")
        return
    try:
        text = proto_path.read_text(encoding="utf-8")
    except OSError as error:
        _add(diagnostics, "TWIN-PROTO-001", "$.protobuf.path", f"cannot read protobuf: {error.strerror or error}")
        return
    clean = _strip_proto_comments(text)
    if not re.search(r'\bsyntax\s*=\s*"proto3"\s*;', clean):
        _add(diagnostics, "TWIN-PROTO-001", "$.protobuf.path", "protobuf syntax must be proto3")
    package_match = re.search(r"\bpackage\s+([A-Za-z_][\w.]*)\s*;", clean)
    if not package_match or package_match.group(1) != package:
        _add(diagnostics, "TWIN-PROTO-001", "$.protobuf.package", "does not match the protobuf package")
    structure = _mask_proto_strings(clean)
    _, braces_balanced = _proto_brace_depths(structure)
    if not braces_balanced:
        _add(diagnostics, "TWIN-PROTO-001", "$.protobuf.path", "protobuf braces must be balanced")
    message_blocks = _proto_blocks(clean, "message")
    service_blocks = _proto_blocks(clean, "service")
    top_level_message_blocks = [(name, body) for name, body, depth in message_blocks if depth == 0]
    top_level_service_blocks = [(name, body) for name, body, depth in service_blocks if depth == 0]
    messages = {name for name, _ in top_level_message_blocks}
    services = {name for name, _ in top_level_service_blocks}
    for missing in sorted(REQUIRED_MESSAGES - messages):
        _add(diagnostics, "TWIN-PROTO-001", "$.protobuf.path", f"missing required message {missing}")
    for missing in sorted(REQUIRED_SERVICES - services):
        _add(diagnostics, "TWIN-PROTO-001", "$.protobuf.path", f"missing required service {missing}")

    referenced: set[str] = set()
    for operation in operations.values():
        for field in ("request", "response"):
            reference = operation.get(field)
            if isinstance(reference, str):
                prefix = package + "."
                if not reference.startswith(prefix):
                    _add(diagnostics, "TWIN-OPERATION-001", "$.operations", f"type {reference} is outside package {package}")
                else:
                    referenced.add(reference[len(prefix) :])
        for reference in _list(operation.get("emits")):
            if isinstance(reference, str) and reference.startswith(package + "."):
                referenced.add(reference[len(package) + 1 :])
            elif isinstance(reference, str):
                _add(diagnostics, "TWIN-OPERATION-001", "$.operations", f"event {reference} is outside package {package}")
    for missing in sorted(referenced - messages):
        _add(diagnostics, "TWIN-PROTO-001", "$.operations", f"referenced protobuf message {missing} does not exist")

    bodies = dict(top_level_message_blocks)
    service_bodies = dict(top_level_service_blocks)
    forbidden_secret_fields = {"secret", "password", "token", "credentialvalue", "secretvalue"}
    for name, body, _ in message_blocks:
        fields = _proto_fields(body)
        numbers = [number for _, number in fields]
        duplicates = sorted(number for number, count in Counter(numbers).items() if count > 1)
        for number in duplicates:
            _add(diagnostics, "TWIN-PROTO-001", "$.protobuf.path", f"message {name} repeats field number {number}")
        for field_name, _ in fields:
            normalized_field_name = re.sub(r"[^a-z0-9]", "", field_name.lower())
            if normalized_field_name in forbidden_secret_fields:
                _add(
                    diagnostics,
                    "TWIN-SECRET-001",
                    "$.protobuf.path",
                    f"message {name} models forbidden secret field {field_name}",
                )
    def message_fields(name: str) -> set[str]:
        return {field_name for field_name, _ in _proto_fields(bodies.get(name, ""))}

    event_fields = message_fields("EventEnvelope")
    for missing in sorted(REQUIRED_EVENT_METADATA - event_fields):
        _add(diagnostics, "TWIN-PROTO-001", "$.protobuf.path", f"EventEnvelope is missing {missing}")
    for message_name, required_fields in (
        ("CommandEnvelope", REQUIRED_COMMAND_FIELDS),
        ("CommandReceipt", REQUIRED_RECEIPT_FIELDS),
        ("EvidenceRef", {"evidence_id", "aggregate_id", "target_uri"}),
        ("Observation", {"observation_id", "aggregate_id", "target_uri", "status", "evidence"}),
        ("OutboxMessage", {"message_id", "aggregate_id", "operation", "credential_ref", "source_event_ids"}),
        ("UriRoute", {"uri", "scheme", "uri_authority", "resource_path", "effect", "action"}),
        ("UriCapability", {"capability_id", "effect", "status", "risk", "providers"}),
        ("ResolutionGap", {"kind", "capability_id", "detail", "execution_policy"}),
        ("CapabilityMap", {"map_hash", "baseline_version", "observed_at", "capabilities", "evidence"}),
        (
            "UriProcessStep",
            {
                "step_id",
                "operation_id",
                "route",
                "capability_id",
                "provider_ref",
                "depends_on",
                "timeout_ms",
                "retry",
                "failure_policy",
                "reversible",
                "inverse_uri",
                "authority_scope",
                "idempotency_required",
                "receipt_required",
            },
        ),
        ("UriProcessDefinition", {"process_id", "process_uri", "version", "intent", "steps", "immutable"}),
        ("UriProcessPlan", {"plan_id", "process_id", "process_version", "capability_map_hash", "resolved", "steps", "gaps"}),
        (
            "UriStepReceipt",
            {
                "receipt_id",
                "run_id",
                "step_id",
                "operation_uri",
                "attempt",
                "idempotency_key",
                "status",
                "event_ids",
                "evidence",
                "output_digest_sha256",
            },
        ),
        ("HumanTask", {"task_id", "run_id", "step_id", "state", "requested_actor_ref", "required_authority_scope", "decision_ref"}),
        (
            "UriProcessRun",
            {
                "run_id",
                "plan_id",
                "capability_map_hash",
                "state",
                "current_step_ids",
                "actor_ref",
                "authority_ref",
                "step_receipts",
                "human_tasks",
                "gaps",
            },
        ),
    ):
        for missing in sorted(required_fields - message_fields(message_name)):
            _add(diagnostics, "TWIN-PROTO-001", "$.protobuf.path", f"{message_name} is missing {missing}")

    service_rpcs: dict[str, set[tuple[str, str]]] = {}
    service_rpc_names: dict[str, set[str]] = {}
    for service_name, body in service_bodies.items():
        declarations = re.findall(
            r"\brpc\s+([A-Za-z_]\w*)\s*\(\s*((?:[A-Za-z_]\w*\.)*[A-Za-z_]\w*)\s*\)\s*returns\s*\(\s*((?:[A-Za-z_]\w*\.)*[A-Za-z_]\w*)\s*\)",
            body,
        )
        service_rpc_names[service_name] = {rpc_name for rpc_name, _, _ in declarations}
        service_rpcs[service_name] = {(request.split(".")[-1], response.split(".")[-1]) for _, request, response in declarations}
    for operation_id, operation in operations.items():
        request = str(operation.get("request", "")).split(".")[-1]
        response = str(operation.get("response", "")).split(".")[-1]
        if operation_id.startswith("uri."):
            service_name = (
                "TwinUriProcessCommandService"
                if operation.get("kind") == "command"
                else "TwinUriProcessQueryService"
            )
        else:
            service_name = "TwinCommandService" if operation.get("kind") == "command" else "TwinQueryService"
        if (request, response) not in service_rpcs.get(service_name, set()):
            _add(
                diagnostics,
                "TWIN-PROTO-001",
                "$.protobuf.path",
                f"{service_name} has no RPC for operation {operation_id} ({request} -> {response})",
            )
    for service_name, rpc_names in (
        ("TwinEventStore", {"Append", "Read"}),
        ("TwinProjectionService", {"Rebuild"}),
    ):
        for missing in sorted(rpc_names - service_rpc_names.get(service_name, set())):
            _add(diagnostics, "TWIN-PROTO-001", "$.protobuf.path", f"{service_name} is missing RPC {missing}")
    if "OBSERVATION_STATUS_UNEVALUABLE" not in clean:
        _add(diagnostics, "TWIN-PROTO-001", "$.protobuf.path", "ObservationStatus must model UNEVALUABLE")
    for enum_value in (
        "URI_EFFECT_QUERY",
        "URI_EFFECT_COMMAND",
        "RESOLUTION_GAP_KIND_CONNECTOR_UNAVAILABLE",
        "RESOLUTION_GAP_KIND_PROVIDER_NOT_IMPLEMENTED",
        "RESOLUTION_GAP_KIND_CREDENTIAL_MISSING",
        "RESOLUTION_GAP_KIND_CAPABILITY_MISSING",
        "RESOLUTION_GAP_KIND_PRECONDITION_FAILED",
        "RESOLUTION_GAP_KIND_AUTHORITY_MISSING",
        "URI_PROCESS_RUN_STATE_COMPENSATED",
        "HUMAN_TASK_STATE_DECLINED",
        "HUMAN_TASK_STATE_EXPIRED",
    ):
        if enum_value not in clean:
            _add(diagnostics, "TWIN-PROTO-001", "$.protobuf.path", f"missing URI Process enum value {enum_value}")


def _validate_generation(profile: dict[str, Any], diagnostics: list[Diagnostic]) -> None:
    generation = _dict(profile.get("generation"))
    if generation.get("executableCode") is not False:
        _add(
            diagnostics,
            "TWIN-GENERATION-001",
            "$.generation.executableCode",
            "the standard generator must not emit executable application code",
        )
    if generation.get("outputs") != EXPECTED_OUTPUTS:
        _add(
            diagnostics,
            "TWIN-GENERATION-001",
            "$.generation.outputs",
            "must declare exactly the four standard outputs in canonical order",
        )


def validate_profile(profile_path: str | os.PathLike[str]) -> list[Diagnostic]:
    """Return deterministic diagnostics for a Twin profile and its protobuf."""

    path = Path(profile_path)
    diagnostics: list[Diagnostic] = []
    try:
        profile = _read_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        _add(diagnostics, "TWIN-JSON-001", "$", str(error))
        return sorted(set(diagnostics))
    _validate_profile_shape(profile, diagnostics)
    _validate_event_sourcing(profile, diagnostics)
    _validate_core_boundaries(profile, diagnostics)
    operations = _validate_operations(profile, diagnostics)
    _validate_uri_operations(profile, operations, diagnostics)
    _validate_traits(profile, operations, diagnostics)
    _validate_uri_process_policy(profile, diagnostics)
    _validate_processes(profile, operations, diagnostics)
    _validate_transports(profile, operations, diagnostics)
    _validate_proto(profile, path, operations, diagnostics)
    _validate_generation(profile, diagnostics)
    return sorted(set(diagnostics))


def validation_report(diagnostics: Iterable[Diagnostic]) -> dict[str, Any]:
    ordered = sorted(set(diagnostics))
    return {
        "schema": "twin.validation/v1",
        "valid": not ordered,
        "diagnostics": [asdict(item) for item in ordered],
    }


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_bytes(value))


def _binding_for(profile: dict[str, Any], surface: str, operation_id: str) -> dict[str, Any]:
    bindings = _list(_dict(_dict(profile.get("transports")).get(surface)).get("bindings"))
    return next(_dict(binding) for binding in bindings if _dict(binding).get("operation") == operation_id)


def _conformance_document(profile: dict[str, Any]) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for operation in _list(profile.get("operations")):
        operation = _dict(operation)
        operation_id = operation["id"]
        for surface in REQUIRED_SURFACES:
            cases.append(
                {
                    "id": f"binding.{surface}.{operation_id}",
                    "kind": "transport-binding",
                    "operation": operation_id,
                    "surface": surface,
                    "request": operation["request"],
                    "response": operation["response"],
                    "uri": operation["uri"],
                    "capability": operation["capability"],
                    "risk": operation["risk"],
                    "binding": _binding_for(profile, surface, operation_id),
                }
            )
    for process in _list(profile.get("processes")):
        process = _dict(process)
        for step in _list(process.get("steps")):
            step = _dict(step)
            cases.append(
                {
                    "id": f"process.{process['id']}.{step['id']}",
                    "kind": "uri-process-step",
                    "process": process["id"],
                    "processVersion": process["version"],
                    "step": step,
                    "expected": "resolved-or-typed-gap",
                }
            )
    invariants = [
        "append-only-events",
        "expected-version-concurrency",
        "idempotent-command",
        "projection-rebuild-observe-only",
        "connector-outbox-boundary",
        "secret-handles-only",
        "unevaluable-is-not-healthy",
        "canonical-uri-effect-matches-cqrs",
        "reviewed-discovery-resolution-only",
        "capability-map-hash-pinned",
        "process-dag-acyclic",
        "process-step-receipts-idempotent",
        "process-replay-observe-only",
        "actor-identity-is-not-authority",
    ]
    cases.extend(
        {"id": f"invariant.{name}", "kind": "semantic-invariant", "expected": "pass"}
        for name in invariants
    )
    return {"schema": "twin.conformance/v1", "cases": cases}


def generate_bundle(
    profile_path: str | os.PathLike[str],
    destination: str | os.PathLike[str],
    language: str,
) -> list[str]:
    """Validate and atomically publish a deterministic four-file bundle."""

    diagnostics = validate_profile(profile_path)
    if diagnostics:
        raise ContractInvalid(diagnostics)
    if not LANGUAGE_PATTERN.fullmatch(language):
        raise GenerationError(
            "TWIN-GENERATION-001",
            "language must match [A-Za-z][A-Za-z0-9_.+-]{0,63}",
        )
    profile_path_obj = Path(profile_path).resolve()
    destination_path = Path(destination).resolve()
    if destination_path.exists():
        raise GenerationError("TWIN-OUTPUT-001", "destination already exists; refusing to overwrite it")
    parent = destination_path.parent
    if not parent.is_dir():
        raise GenerationError("TWIN-OUTPUT-001", "destination parent must already exist")

    profile = _read_json(profile_path_obj)
    profile_bytes = _canonical_bytes(profile)
    proto_relative = _dict(profile["protobuf"])["path"]
    proto_source = (_profile_root(profile_path_obj) / proto_relative).resolve()
    proto_bytes = proto_source.read_bytes()
    transport_document = {
        "schema": "twin.transport-map/v1",
        "operations": profile["operations"],
        "transports": profile["transports"],
        "uriCapabilities": profile["uriCapabilities"],
        "processRuntime": profile["processRuntime"],
        "processes": profile["processes"],
    }
    manifest = {
        "schema": "twin.bundle/v1",
        "standardVersion": STANDARD_VERSION,
        "language": language,
        "profile": {
            "id": profile["id"],
            "version": profile["version"],
            "sha256": _sha256(profile_bytes),
        },
        "protobuf": {
            "package": _dict(profile["protobuf"])["package"],
            "path": proto_relative,
            "sha256": _sha256(proto_bytes),
        },
        "executableCode": False,
        "uriProcessDefinitions": len(profile["processes"]),
        "outputs": EXPECTED_OUTPUTS,
    }

    temporary = Path(tempfile.mkdtemp(prefix=f".{destination_path.name}.", dir=parent))
    try:
        _write_json(temporary / "twin.manifest.json", manifest)
        proto_target = temporary / proto_relative
        proto_target.parent.mkdir(parents=True, exist_ok=True)
        proto_target.write_bytes(proto_bytes)
        _write_json(temporary / "transport-map.json", transport_document)
        _write_json(temporary / "conformance.json", _conformance_document(profile))
        if destination_path.exists():
            raise GenerationError("TWIN-OUTPUT-001", "destination appeared during generation; refusing to overwrite it")
        os.rename(temporary, destination_path)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return list(EXPECTED_OUTPUTS)


def _render_validation(diagnostics: list[Diagnostic], output_format: str) -> str:
    if output_format == "json":
        return _canonical_bytes(validation_report(diagnostics)).decode("utf-8").rstrip("\n")
    if not diagnostics:
        return "VALID Twin profile"
    return "\n".join(f"{item.code} {item.path}: {item.message}" for item in diagnostics)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="twin-standard")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="validate a Twin profile")
    validate.add_argument("profile")
    validate.add_argument("--format", choices=("text", "json"), default="text")
    generate = subparsers.add_parser("generate", help="generate a deterministic Twin bundle")
    generate.add_argument("profile")
    generate.add_argument("--out", required=True)
    generate.add_argument("--language", required=True)
    generate.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "validate":
        diagnostics = validate_profile(args.profile)
        print(_render_validation(diagnostics, args.format))
        return 1 if diagnostics else 0
    try:
        outputs = generate_bundle(args.profile, args.out, args.language)
    except ContractInvalid as error:
        print(_render_validation(error.diagnostics, args.format))
        return 1
    except (GenerationError, OSError) as error:
        code = error.code if isinstance(error, GenerationError) else "TWIN-OUTPUT-001"
        if args.format == "json":
            print(
                _canonical_bytes(
                    {"schema": "twin.generation/v1", "generated": False, "error": {"code": code, "message": str(error)}}
                ).decode("utf-8").rstrip("\n")
            )
        else:
            print(f"{code}: {error}", file=sys.stderr)
        return 2
    result = {"schema": "twin.generation/v1", "generated": True, "destination": str(Path(args.out)), "outputs": outputs}
    if args.format == "json":
        print(_canonical_bytes(result).decode("utf-8").rstrip("\n"))
    else:
        print(f"GENERATED {len(outputs)} files at {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
