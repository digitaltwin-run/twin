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
}
REQUIRED_SERVICES = {
    "TwinCommandService",
    "TwinQueryService",
    "TwinEventStore",
    "TwinProjectionService",
}
EXPECTED_OUTPUTS = [
    "twin.manifest.json",
    "proto/twin/v1/twin.proto",
    "transport-map.json",
    "conformance.json",
]
LANGUAGE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.+\-]{0,63}$")
OPERATION_PATTERN = re.compile(r"^twin\.[a-z][a-z0-9.\-]*$")
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
            _add(diagnostics, "TWIN-OPERATION-001", path + ".id", "must be a canonical twin.* operation ID")
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
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"//.*", "", text)


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
    messages = set(re.findall(r"\bmessage\s+([A-Za-z_]\w*)\s*\{", clean))
    services = set(re.findall(r"\bservice\s+([A-Za-z_]\w*)\s*\{", clean))
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

    bodies = {
        name: body
        for name, body in re.findall(r"\bmessage\s+([A-Za-z_]\w*)\s*\{([^{}]*)\}", clean, flags=re.DOTALL)
    }
    service_bodies = {
        name: body
        for name, body in re.findall(r"\bservice\s+([A-Za-z_]\w*)\s*\{([^{}]*)\}", clean, flags=re.DOTALL)
    }
    for name, body in bodies.items():
        numbers = re.findall(r"=\s*(\d+)\s*;", body)
        duplicates = sorted(number for number, count in Counter(numbers).items() if count > 1)
        for number in duplicates:
            _add(diagnostics, "TWIN-PROTO-001", "$.protobuf.path", f"message {name} repeats field number {number}")
        field_names = re.findall(r"(?:\brepeated\s+)?[A-Za-z_][\w.<>]*\s+([a-z][a-z0-9_]*)\s*=", body)
        for field_name in field_names:
            if field_name in {"secret", "password", "token", "credential_value", "secret_value"}:
                _add(
                    diagnostics,
                    "TWIN-SECRET-001",
                    "$.protobuf.path",
                    f"message {name} models forbidden secret field {field_name}",
                )
    event_body = bodies.get("EventEnvelope", "")
    def message_fields(name: str) -> set[str]:
        return set(
            re.findall(
                r"(?:\brepeated\s+)?[A-Za-z_][\w.<>]*\s+([a-z][a-z0-9_]*)\s*=",
                bodies.get(name, ""),
            )
        )

    event_fields = message_fields("EventEnvelope")
    for missing in sorted(REQUIRED_EVENT_METADATA - event_fields):
        _add(diagnostics, "TWIN-PROTO-001", "$.protobuf.path", f"EventEnvelope is missing {missing}")
    for message_name, required_fields in (
        ("CommandEnvelope", REQUIRED_COMMAND_FIELDS),
        ("CommandReceipt", REQUIRED_RECEIPT_FIELDS),
        ("EvidenceRef", {"evidence_id", "aggregate_id", "target_uri"}),
        ("Observation", {"observation_id", "aggregate_id", "target_uri", "status", "evidence"}),
        ("OutboxMessage", {"message_id", "aggregate_id", "operation", "credential_ref", "source_event_ids"}),
    ):
        for missing in sorted(required_fields - message_fields(message_name)):
            _add(diagnostics, "TWIN-PROTO-001", "$.protobuf.path", f"{message_name} is missing {missing}")

    service_rpcs: dict[str, set[tuple[str, str]]] = {}
    service_rpc_names: dict[str, set[str]] = {}
    for service_name, body in service_bodies.items():
        declarations = re.findall(
            r"\brpc\s+([A-Za-z_]\w*)\s*\(\s*([A-Za-z_.]\w*)\s*\)\s*returns\s*\(\s*([A-Za-z_.]\w*)\s*\)",
            body,
        )
        service_rpc_names[service_name] = {rpc_name for rpc_name, _, _ in declarations}
        service_rpcs[service_name] = {(request.split(".")[-1], response.split(".")[-1]) for _, request, response in declarations}
    for operation_id, operation in operations.items():
        request = str(operation.get("request", "")).split(".")[-1]
        response = str(operation.get("response", "")).split(".")[-1]
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
    _validate_traits(profile, operations, diagnostics)
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
                    "binding": _binding_for(profile, surface, operation_id),
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
