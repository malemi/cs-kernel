"""Supervisor-owned launch configuration and conservative request admission.

Executor billing authority is independent of engine/classifier configuration.
An unknown response cost retains its reservation and stops further requests.
"""
from __future__ import annotations

from decimal import Decimal, localcontext
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator
from .operator_executor_protocol import Strict, Identity, Digest, USD, UInt, UUIDString, canonical, decode, sha256


class Pricing(Strict):
    provider: Literal['anthropic', 'openrouter']
    model: str
    source: Annotated[str, Field(min_length=1)]
    response_models: Annotated[list[str], Field(max_length=16)] = Field(default_factory=list)

    @field_validator('model', 'response_models')
    @classmethod
    def finite_models(cls, value):
        import re
        values = value if isinstance(value, list) else [value]
        if len(set(values)) != len(values) or any(not re.fullmatch(r'~?[A-Za-z0-9][A-Za-z0-9._/-]{0,199}', name) for name in values):
            raise ValueError('unsupported finite model binding')
        return value

    def accepts(self, model):
        return model in (self.response_models or [self.model])
    # Supervisor-reviewed worst-case rates including cache writes/thinking and
    # long-context tiers, per million billed tokens; not optimistic list rates.
    input_upper_usd_per_million: USD
    output_upper_usd_per_million: USD
    maximum_context_tokens: Annotated[int, Field(strict=True, gt=0)]
    input_usd_per_million: USD | None = None
    output_usd_per_million: USD | None = None
    cache_read_usd_per_million: USD | None = None
    cache_write_5m_usd_per_million: USD | None = None

    @model_validator(mode='after')
    def actual_rates(self):
        rates = [self.input_usd_per_million,self.output_usd_per_million,
            self.cache_read_usd_per_million,self.cache_write_5m_usd_per_million]
        if any(value is not None for value in rates):
            if any(value is None or Decimal(value) <= 0 for value in rates):
                raise ValueError('incomplete explicit usage pricing')
            if (any(Decimal(value) > Decimal(self.input_upper_usd_per_million) for value in (rates[0],rates[2],rates[3]))
                    or Decimal(rates[1]) > Decimal(self.output_upper_usd_per_million)):
                raise ValueError('usage prices exceed conservative reserve rates')
        return self

    @property
    def cost_basis(self):
        return 'usage_price_estimate' if self.input_usd_per_million is not None else 'conservative_usage_upper_estimate'

    def estimate(self,input_tokens,output_tokens,cache_read_tokens=0,cache_write_tokens=0,cache_write_1h_tokens=0):
        values = (input_tokens,output_tokens,cache_read_tokens,cache_write_tokens,cache_write_1h_tokens)
        if any(type(value) is not int or value < 0 for value in values):
            raise AdmissionError('usage_unavailable')
        if cache_write_1h_tokens or cache_read_tokens+cache_write_tokens > input_tokens:
            raise AdmissionError('unsupported_cache_usage')
        normal = input_tokens-cache_read_tokens-cache_write_tokens
        if self.input_usd_per_million is None:
            if cache_read_tokens or cache_write_tokens:
                raise AdmissionError('cache_usage_pricing_unavailable')
            amounts = ((normal,self.input_upper_usd_per_million),(output_tokens,self.output_upper_usd_per_million))
        else:
            amounts = ((normal,self.input_usd_per_million),(output_tokens,self.output_usd_per_million),
                (cache_read_tokens,self.cache_read_usd_per_million),(cache_write_tokens,self.cache_write_5m_usd_per_million))
        return sum(Decimal(tokens)*Decimal(rate) for tokens,rate in amounts)/Decimal(1000000)



class FrozenIdentity(Identity):
    model_config = ConfigDict(extra='forbid',strict=True,frozen=True)


class ExecutorJob(Strict):
    model_config = ConfigDict(extra='forbid',strict=True,frozen=True)
    primary_run_id: UUIDString
    nonce: Annotated[str,Field(pattern=r'^[0-9a-f]{32}$')]
    owner: str
    clone_root: str
    supervisor: FrozenIdentity
    admitted_at_utc: str
    expires_at_utc: str
    monotonic_start_ns: UInt

    @property
    def deadline_monotonic_ns(self):
        duration=utc_datetime(self.expires_at_utc)-utc_datetime(self.admitted_at_utc)
        nanoseconds=(duration.days*86400+duration.seconds)*1000000000+duration.microseconds*1000
        return self.monotonic_start_ns+min(10800*1000000000,nanoseconds)


class MetadataObservation(Strict):
    model_config = ConfigDict(extra='forbid',strict=True,frozen=True)
    path: str
    bytes: Annotated[int,Field(strict=True,gt=0,le=65536)]
    sha256: Digest
    url: str
    http_status: Literal[200] = 200
    observed_at_utc: str


class ResolvedPricing(Strict):
    model_config = ConfigDict(extra='forbid',strict=True,frozen=True)
    provider: Literal['openrouter'] = 'openrouter'
    model: str
    source: str
    response_models: tuple[str,...]
    input_upper_usd_per_million: USD
    output_upper_usd_per_million: USD
    maximum_context_tokens: Annotated[int,Field(strict=True,gt=0)]
    input_usd_per_million: USD
    output_usd_per_million: USD
    cache_read_usd_per_million: USD
    cache_write_5m_usd_per_million: USD

    @model_validator(mode='after')
    def valid_prices(self):
        Pricing.model_validate(self.model_dump(mode='json'))
        return self


class FallbackResolution(Strict):
    model_config = ConfigDict(extra='forbid',strict=True,frozen=True)
    schema_version: Literal['pydantic-fallback-resolution-v1'] = 'pydantic-fallback-resolution-v1'
    resolution_id: UUIDString
    configured_alias: str
    canonical_model: str
    response_models: tuple[str,...]
    pricing: ResolvedPricing
    cap_policy_sha256: Digest
    cache_mode: Literal['disabled','5m']
    metadata: MetadataObservation

    def binding(self,job):
        value=self.model_dump(mode='json')
        return dict(policy=value,policy_sha256=sha256(canonical(value)),job=job.model_dump(mode='json'))


def utc_datetime(value):
    from datetime import datetime,timedelta
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None or result.utcoffset()!=timedelta(0):
        raise ValueError('metadata_time_not_utc')
    return result


def check_executor_job(job,policy,*,now=None,monotonic_ns=None):
    import time
    from datetime import datetime,timezone,timedelta
    now=now or datetime.now(timezone.utc)
    monotonic_ns=time.monotonic_ns() if monotonic_ns is None else monotonic_ns
    admitted=utc_datetime(job.admitted_at_utc)
    expires=utc_datetime(job.expires_at_utc)
    if now<admitted or monotonic_ns<job.monotonic_start_ns:
        raise ValueError('executor_job_clock_rollback')
    if now>expires or monotonic_ns>job.deadline_monotonic_ns:
        raise ValueError('executor_job_expired')
    if policy is not None:
        observed=utc_datetime(policy.metadata.observed_at_utc)
        if observed>now or observed<admitted:
            raise ValueError('metadata_observation_time_differs')
        if now-observed>timedelta(hours=24):
            raise ValueError('metadata_stale')
        if expires!=min(observed+timedelta(hours=24),admitted+timedelta(hours=3)):
            raise ValueError('executor_job_expiry_binding_differs')


def fallback_metadata_url(model):
    import re
    from urllib.parse import quote
    if not isinstance(model,str) or not re.fullmatch(r'~?anthropic/claude-[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*',model):
        raise ValueError('fallback_metadata_model_unsupported')
    return 'https://openrouter.ai/api/v1/model/'+'/'.join(quote(part,safe='') for part in model.split('/'))


def resolve_fallback_metadata(raw,configured,cap,cache_mode,observation,resolution_id):
    import re
    fallback_metadata_url(configured)
    if cap.provider!='openrouter' or cache_mode not in ('disabled','5m'):
        raise ValueError('fallback_cap_policy_unsupported')
    value=decode(raw)
    data=value.get('data') if isinstance(value,dict) else None
    if not isinstance(data,dict) or data.get('id')!=configured:
        raise ValueError('fallback_metadata_identity_differs')
    if configured.startswith('~'):
        target=data.get('alias_target')
        target=target.get('slug') if isinstance(target,dict) else None
        family=re.fullmatch(r'~anthropic/claude-([a-z0-9]+)-latest',configured)
        if not family or not isinstance(target,str) or not target.startswith('anthropic/claude-'+family[1]+'-'):
            raise ValueError('fallback_metadata_target_unsupported')
    else:
        target=configured
        if data.get('canonical_slug')!=configured:
            raise ValueError('fallback_metadata_canonical_identity_differs')
    if not isinstance(target,str) or target.startswith('~'):
        raise ValueError('fallback_metadata_target_unresolved')
    fallback_metadata_url(target)
    if cap.model not in (configured,target):
        raise ValueError('fallback_cap_model_differs')
    prices=data.get('pricing')
    if not isinstance(prices,dict):
        raise ValueError('fallback_metadata_prices_missing')
    def decimal_price(value):
        if not isinstance(value,str) or len(value)>128 or value.strip()!=value:
            raise ValueError('fallback_metadata_price_invalid')
        try:result=Decimal(value)
        except Exception:raise ValueError('fallback_metadata_price_invalid') from None
        if not result.is_finite() or result<0:
            raise ValueError('fallback_metadata_price_invalid')
        parts=result.as_tuple()
        if len(parts.digits)>64 or not -64<=parts.exponent<=64 or result.adjusted()>32:
            raise ValueError('fallback_metadata_price_representation')
        return result
    fields={'prompt':'input_usd_per_million','completion':'output_usd_per_million',
        'input_cache_read':'cache_read_usd_per_million','input_cache_write':'cache_write_5m_usd_per_million'}
    def per_million(value):
        amount=decimal_price(value)
        with localcontext() as context:
            context.prec=72
            return format(amount*Decimal(1000000),'f')
    actual={name:per_million(prices[key]) for key,name in fields.items() if key in prices}
    if any(len(value)>128 for value in actual.values()):
        raise ValueError('fallback_metadata_price_representation')
    if len(actual)!=4:
        raise ValueError('fallback_metadata_prices_missing')
    ignored={'input_cache_write_1h','web_search','image','audio','input_audio','output_audio','audio_input','audio_output'}
    for key,value in prices.items():
        amount=decimal_price(value)
        if key=='request' and amount or key not in fields and key not in ignored and key!='request' and amount:
            raise ValueError('fallback_metadata_charge_unsupported')
    context=data.get('context_length')
    if type(context) is not int or context<=0 or context>cap.maximum_context_tokens:
        raise ValueError('fallback_metadata_context_unsupported')
    normalized=cap.model_dump(mode='json')
    normalized.update(model=target,response_models=[target],source=observation.url+'; observed '+observation.observed_at_utc,
        maximum_context_tokens=context,**actual)
    try:pricing=Pricing.model_validate(normalized)
    except ValueError:raise ValueError('fallback_metadata_price_exceeds_policy') from None
    frozen=pricing.model_dump(mode='json');frozen['response_models']=tuple(frozen['response_models'])
    return FallbackResolution(resolution_id=resolution_id,configured_alias=configured,canonical_model=target,
        response_models=(target,),pricing=ResolvedPricing.model_validate(frozen),
        cap_policy_sha256=sha256(canonical(cap.model_dump(mode='json'))),cache_mode=cache_mode,metadata=observation)


class ExecutorConfig(Strict):
    run_id: str
    attempt_id: str
    owner: str
    nonce: Annotated[str, Field(pattern=r'^[0-9a-f]{32}$')]
    clone_root: str
    journal_path: str
    supervisor: Identity
    kernel_source_digest: Digest
    provider: Literal['anthropic', 'openrouter'] = 'anthropic'
    model: str
    api_key_env: str
    base_url: str | None = None
    pricing: Pricing
    cache_mode: Literal['disabled','5m'] = 'disabled'
    soft_budget_usd: USD = '4.00'
    admitted_ceiling_usd: USD
    max_requests: Annotated[int, Field(strict=True, gt=0, le=1000)] = 100
    max_output_tokens: Annotated[int, Field(strict=True, gt=0, le=64000)] = 8192
    deadline_seconds: Annotated[int, Field(strict=True, gt=0, le=10800)] = 10800
    job_deadline_monotonic_ns: UInt | None = None
    tool_timeout_seconds: Annotated[int, Field(strict=True, gt=0, le=2730)] = 2730
    page_bytes: Annotated[int, Field(strict=True, gt=0, le=65536)] = 16384
    max_artifact_bytes: Annotated[int, Field(strict=True, gt=0, le=67108864)] = 16777216
    send_mode: Literal['draft', 'send'] = 'draft'
    exact_send_ids: list[str] = Field(default_factory=list)
    # These are launcher policy expressions, not model-editable arguments.
    additional_denied: list[str] = Field(default_factory=list)
    founder_enabled: bool = False
    founder_account: str | None = None
    founder_question: str | None = None
    campaign_enabled: bool = True
    context_paths: list[str] = Field(default_factory=list)

    @field_validator('run_id', 'attempt_id')
    @classmethod
    def valid_uuid(cls, value):
        if str(UUID(value)) != value:
            raise ValueError('noncanonical UUID')
        return value

    @field_validator('api_key_env')
    @classmethod
    def dedicated_key(cls, value):
        import re
        if not re.fullmatch(r'[A-Z][A-Z0-9_]*', value) or any(x in value for x in ('CLASSIFIER', 'ENGINE')):
            raise ValueError('unsupported executor credential binding')
        return value

    @model_validator(mode='after')
    def bindings(self):
        if not self.owner or self.pricing.provider != self.provider or self.pricing.model != self.model:
            raise ValueError('provider/model/pricing binding differs')
        if any(Decimal(v) <= 0 for v in (self.soft_budget_usd, self.admitted_ceiling_usd,
                self.pricing.input_upper_usd_per_million, self.pricing.output_upper_usd_per_million)):
            raise ValueError('budget/pricing must be positive')
        if self.cache_mode == '5m' and self.pricing.input_usd_per_million is None:
            raise ValueError('cache requires explicit usage pricing')
        if self.base_url not in (None, self.endpoint):
            raise ValueError('provider endpoint binding differs')
        if self.provider == 'openrouter' and self.base_url != self.endpoint:
            raise ValueError('OpenRouter requires its explicit Messages endpoint')
        root, journal = Path(self.clone_root), Path(self.journal_path)
        if not root.is_absolute() or root.resolve() != root or not root.is_dir():
            raise ValueError('clone root must be a canonical directory')
        if not journal.is_absolute() or journal.parent.resolve() != journal.parent:
            raise ValueError('journal path must have canonical private parent')
        if self.founder_enabled and (not self.founder_account or not self.founder_question):
            raise ValueError('enabled founder requires rendered account/question binding')
        if self.send_mode != 'send' and self.exact_send_ids:
            raise ValueError('send grants require explicit send mode')
        return self

    def remaining_seconds(self):
        import time
        remaining=self.deadline_seconds
        if self.job_deadline_monotonic_ns is not None:
            remaining=min(remaining,(self.job_deadline_monotonic_ns-time.monotonic_ns())/1000000000)
        if remaining<=0:
            raise AdmissionError('executor_job_expired')
        return remaining

    @property
    def endpoint(self):
        return 'https://openrouter.ai/api' if self.provider == 'openrouter' else 'https://api.anthropic.com'

    @property
    def messages_endpoint(self):
        return self.endpoint + '/v1/messages'


def cache_request_matches(config, body):
    markers=[]
    def visit(value):
        if isinstance(value,dict):
            if 'cache_control' in value:markers.append(value['cache_control'])
            for child in value.values():visit(child)
        elif isinstance(value,list):
            for child in value:visit(child)
    visit(body)
    if config.cache_mode == 'disabled':
        return not markers
    return bool(markers) and all(isinstance(marker,dict) and set(marker) <= {'type','ttl'}
        and marker.get('type') == 'ephemeral' and marker.get('ttl','5m') == '5m' for marker in markers)


class AdmissionError(RuntimeError):
    pass


class Admission:
    def __init__(self, config: ExecutorConfig):
        self.config = config
        self.accounted = Decimal(0)
        self.uncertain = Decimal(0)
        self.requests = 0
        self.input_tokens = self.output_tokens = 0

    def reserve(self, input_bound: int) -> Decimal:
        c = self.config
        if self.uncertain:
            raise AdmissionError('unknown_previous_cost')
        if self.requests >= c.max_requests:
            raise AdmissionError('request_limit')
        if self.accounted >= Decimal(c.soft_budget_usd):
            raise AdmissionError('soft_target_reached')
        if input_bound + c.max_output_tokens > c.pricing.maximum_context_tokens:
            raise AdmissionError('context_capacity')
        bound = (Decimal(input_bound) * Decimal(c.pricing.input_upper_usd_per_million)
                 + Decimal(c.max_output_tokens) * Decimal(c.pricing.output_upper_usd_per_million)) / Decimal(1000000)
        if self.accounted + bound > Decimal(c.admitted_ceiling_usd):
            raise AdmissionError('admitted_ceiling')
        self.requests += 1
        self.uncertain = bound
        return bound

    def reconcile(self, input_tokens: int, output_tokens: int, *, cache_read_tokens=0,cache_write_tokens=0,cache_write_1h_tokens=0) -> Decimal:
        c = self.config
        cost = c.pricing.estimate(input_tokens,output_tokens,cache_read_tokens,cache_write_tokens,cache_write_1h_tokens)
        if cost > self.uncertain:
            raise AdmissionError('usage_exceeds_reserved_bound')
        self.accounted += cost
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.uncertain = Decimal(0)
        return cost
