"""Conservative enforcement of the existing completion-token allowance.

A request reserves its entire requested output cap before transmission. A valid
successful usage record releases the unused reservation. Failed, missing-usage,
or malformed responses release nothing, so retries cannot obtain free tokens.
"""
from dataclasses import dataclass, field


class TokenUsageViolation(ValueError):
    """The provider reports more output than the requested per-call cap."""


@dataclass
class CompletionBudget:
    total: int = 18000
    per_call: int = 6000
    charged: int = 0
    entries: list = field(default_factory=list)
    pending: dict | None = None

    @property
    def remaining(self):
        return self.total-self.charged

    def reserve(self, call_index):
        if self.pending is not None:
            raise RuntimeError('An earlier request is unsettled')
        if self.remaining <= 0:
            raise RuntimeError('Completion budget exhausted')
        limit=min(self.per_call,self.remaining)
        self.pending={'call':call_index,'remaining_before':self.remaining,
                      'requested_max_tokens':limit}
        self.charged+=limit
        return limit

    def settle(self, usage=None, *, failed=False, http_status=None):
        if self.pending is None:
            raise RuntimeError('No request reservation')
        entry=self.pending
        self.pending=None
        limit=entry['requested_max_tokens']
        reported=usage.get('completion_tokens') if isinstance(usage,dict) else None
        valid=isinstance(reported,int) and not isinstance(reported,bool) and reported>=0
        violation=valid and reported>limit
        if failed:
            charge=limit;basis='failed_request_reserved_max'
        elif valid and not violation:
            charge=reported;basis='provider_usage'
        else:
            charge=limit
            basis='usage_exceeds_request' if violation else 'missing_or_invalid_usage_reserved_max'
        self.charged-=limit-charge
        entry.update({'charged_completion_tokens':charge,'reported_completion_tokens':reported if valid else None,
                      'basis':basis,'http_status':http_status,'remaining_after':self.remaining})
        self.entries.append(entry)
        if violation:
            raise TokenUsageViolation('Reported completion usage exceeds the requested output cap')
        return entry
