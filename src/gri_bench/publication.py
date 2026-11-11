"""Public score views; never disclose sealed bounds through exception messages."""
import re


def public_score(score, split):
    result={k:v for k,v in score.items() if k!='rows'}
    if split!='sealed' or result['status']=='verified':
        return result
    # Raw verifier messages may embed private numeric bounds or patient inputs.
    # Keep the raw score and its hash privately; publish only a bounded category.
    reason=str(result.get('reason') or '')
    outside=re.fullmatch(r'(theta_a|relative_leak|ec50_mg_dl|hill_n|tau_min|theta_L|theta_c) outside \[[^\n]+\]',reason)
    if result['status']=='submission_failure':
        if outside:
            result['reason']=outside.group(1)+' outside allowed bounds (private bounds withheld)'
        elif reason=='Required submission file missing or invalid':
            result['reason']=reason
        else:
            result['reason']='submission_contract_failed (private diagnostic retained)'
    elif result['status']=='simulation_failure':
        result['reason']='native_simulation_failed (private diagnostic retained)'
    elif result['status']=='infrastructure_error':
        result['reason']='infrastructure_error (private diagnostic retained)'
    else:
        raise ValueError('Unknown failed score status')
    return result
