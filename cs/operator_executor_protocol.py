"""Strict, versioned evidence for the Python scheduled execution host.

A digest chain detects mutation; it is not authentication. Consumers must join
this evidence to independently captured process, owner and source identities.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, AfterValidator, model_validator

SCHEMA = 'pydantic-executor-v1'
UInt = Annotated[int, Field(strict=True, ge=0)]
Digest = Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
USD = Annotated[str, Field(pattern=r'^(0|[1-9][0-9]*)(\.[0-9]+)?$')]

def canonical_uuid(value: str) -> str:
    if str(UUID(value)) != value:
        raise ValueError('noncanonical UUID')
    return value

UUIDString = Annotated[str, AfterValidator(canonical_uuid)]



def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def decode(raw: str | bytes):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('nonfinite JSON value')
    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Identity(Strict):
    pid: UInt
    started_ticks: UInt


class Artifact(Strict):
    artifact_id: UUIDString
    path: str
    bytes: UInt
    sha256: Digest


class Diagnostic(Strict):
    stage: str
    cause: str
    expected: str
    observed: str
    run_id: UUIDString
    tool_id: UUIDString | None


class RunStart(Strict):
    kind: Literal['run_start'] = 'run_start'
    owner: str
    nonce: str
    clone_root: str
    supervisor: Identity
    executor: Identity
    interpreter: Artifact
    kernel_version: str
    kernel_source_digest: Digest
    executor_module_digest: Digest
    dependency_version: str
    policy_digest: Digest
    context_digest: Digest
    provider: str
    model: str
    endpoint: str | None
    soft_budget_usd: USD
    admitted_ceiling_usd: USD
    max_requests: UInt
    max_output_tokens: UInt
    deadline_seconds: UInt


class ToolStart(Strict):
    kind: Literal['tool_start'] = 'tool_start'
    tool_id: UUIDString
    parent_request_id: UUIDString | None
    name: Literal['run_cs', 'read_context', 'load_workflow', 'read_artifact', 'pause_status', 'git_metadata']
    argv: list[str] | None
    path: str | None
    offset: UInt | None
    length: UInt | None
    decision: Literal['allow', 'deny']
    cause: str | None
    producer: Identity


class ToolSpawn(Strict):
    kind: Literal['tool_spawn'] = 'tool_spawn'
    tool_id: UUIDString
    child: Identity
    parent: Identity


class ToolEnd(Strict):
    kind: Literal['tool_end'] = 'tool_end'
    tool_id: UUIDString
    status: Literal['ok', 'error', 'denied', 'timeout', 'cancelled', 'unknown']
    exit_code: int | None
    stdout: Artifact | None
    stderr: Artifact | None
    effect: bool
    unknown_effect: bool
    business_result: Literal['success', 'held', 'error', 'unavailable']


class ContextPage(Strict):
    kind: Literal['context_page'] = 'context_page'
    page_id: UUIDString
    artifact_id: UUIDString
    source_path: str
    source_sha256: Digest
    owner: str
    start: UInt
    end: UInt
    total_bytes: UInt
    eof: bool
    sha256: Digest
    decoding: Literal['utf-8', 'base64']

    @model_validator(mode='after')
    def interval(self):
        if not self.start <= self.end <= self.total_bytes or self.eof != (self.end == self.total_bytes):
            raise ValueError('invalid page interval or EOF')
        if self.start == self.end and self.total_bytes != 0:
            raise ValueError('empty nonempty-source page')
        return self


class ModelRequest(Strict):
    kind: Literal['model_request'] = 'model_request'
    request_id: UUIDString
    transport: Literal['function-test', 'anthropic-boundary']
    messages: Artifact
    payload_sha256: Digest
    page_ids: list[UUIDString]
    phase: str
    input_token_estimate: UInt
    reserved_maximum_usd: USD


class ProviderSubmission(Strict):
    kind: Literal['provider_submission'] = 'provider_submission'
    request_id: UUIDString
    body: Artifact
    page_ids: list[UUIDString]
    endpoint: str


class ModelResponse(Strict):
    kind: Literal['model_response'] = 'model_response'
    request_id: UUIDString
    provider_request_id: str | None
    model: str | None
    input_tokens: UInt | None
    output_tokens: UInt | None
    accounted_cost_usd: USD | None
    status: Literal['ok', 'error', 'cancelled', 'unknown', 'capacity']
    finish_reason: str | None
    http_status: Annotated[int, Field(strict=True, ge=100, le=599)] | None = None
    normal_input_tokens: UInt | None = None
    cache_read_tokens: UInt | None = None
    cache_write_tokens: UInt | None = None
    cache_write_1h_tokens: UInt | None = None
    cost_basis: Literal['usage_price_estimate','conservative_usage_upper_estimate'] | None = None
    error_kind: Literal['billing', 'rate_limit', 'authentication', 'permission', 'request', 'overloaded', 'connection', 'timeout', 'cancelled', 'unknown'] | None = None


class Phase(Strict):
    kind: Literal['phase'] = 'phase'
    name: str
    prerequisites: list[str]
    tool_ids: list[UUIDString]
    request_ids: list[UUIDString]
    outcome: Literal['completed', 'held', 'failed']


class RunEnd(Strict):
    kind: Literal['run_end'] = 'run_end'
    terminal: Literal['completed', 'held', 'failed', 'cancelled', 'timeout', 'budget_exhausted', 'capacity', 'unknown']
    outstanding_tool_ids: list[UUIDString]
    outstanding_request_ids: list[UUIDString]
    phase_outcomes: dict[str, Literal['completed', 'held', 'failed']]
    input_tokens: UInt
    output_tokens: UInt
    accounted_cost_usd: USD
    uncertain_cost_usd: USD
    model_completed: bool
    health: Literal['unassessed'] = 'unassessed'
    acceptance: Literal['unassessed'] = 'unassessed'
    final_journal_digest: Digest
    diagnostic: Diagnostic | None


Payload = Annotated[Union[RunStart, ToolStart, ToolSpawn, ToolEnd, ContextPage,
                         ModelRequest, ProviderSubmission, ModelResponse, Phase, RunEnd], Field(discriminator='kind')]


class Record(Strict):
    schema_version: Literal['pydantic-executor-v1'] = SCHEMA
    run_id: UUIDString
    attempt_id: UUIDString
    sequence: UInt
    monotonic_ns: UInt
    previous_digest: Digest
    payload: Payload

    @field_validator('run_id', 'attempt_id')
    @classmethod
    def uuid_string(cls, value):
        if str(UUID(value)) != value:
            raise ValueError('noncanonical UUID')
        return value


RECORD_ADAPTER = TypeAdapter(Record)


class Journal:
    """Exclusive private append-only producer. No model-callable write surface."""
    def __init__(self, path: Path, run_id: str, attempt_id: str):
        self.path, self.run_id, self.attempt_id = path, run_id, attempt_id
        self.sequence, self.digest = 0, '0' * 64
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        self.stream = os.fdopen(descriptor, 'wb', buffering=0)

    def append(self, payload):
        record = Record(run_id=self.run_id, attempt_id=self.attempt_id, sequence=self.sequence,
                        monotonic_ns=time.monotonic_ns(), previous_digest=self.digest, payload=payload)
        raw = canonical(record.model_dump(mode='json'))
        self.stream.write(raw + b'\n')
        os.fsync(self.stream.fileno())
        self.digest, self.sequence = sha256(raw), self.sequence + 1
        return record

    def close(self):
        self.stream.close()


def parse_journal(path: Path) -> list[Record]:
    records = []
    previous, last_time = '0' * 64, -1
    for raw in path.read_bytes().splitlines():
        row = Record.model_validate(decode(raw))
        if row.sequence != len(records) or row.previous_digest != previous or row.monotonic_ns < last_time:
            raise ValueError('journal order or chain differs')
        if records and (row.run_id != records[0].run_id or row.attempt_id != records[0].attempt_id):
            raise ValueError('foreign journal record')
        if records and records[-1].payload.kind == 'run_end':
            raise ValueError('record after terminal')
        if row.payload.kind == 'run_end' and row.payload.final_journal_digest != previous:
            raise ValueError('terminal digest differs')
        records.append(row)
        previous, last_time = sha256(canonical(row.model_dump(mode='json'))), row.monotonic_ns
    if not records or records[0].payload.kind != 'run_start' or records[-1].payload.kind != 'run_end':
        raise ValueError('missing start or terminal')
    return records
