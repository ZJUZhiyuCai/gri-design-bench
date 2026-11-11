"""Independent supplemental audit: native arrays, token ledger and preservation."""
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np
from gri_bench.publication import public_score
from gri_bench.runner import ROOT, dump, load_case, verify_runtime_lock
from gri_bench.repeat_runner import SYSTEM_PROMPT, verify_repeat_lock

EXPERIMENT=ROOT/'experiments/repeats-2026-11-11'
DESTINATION=ROOT/'results/repetitions-2026-11-11'


def audit_native_results(tag):
    """Independent saved-array arithmetic with publication-safe score comparison.

    Uses the same arithmetic as the frozen original audit. The only export
    difference is a verified redaction of sealed exception diagnostics.
    """
    paths=sorted((ROOT/'private/runs'/tag).glob('*/metadata.json'))
    assert len(paths)==36
    verified=failed=safety_failed=0;max_error=0.;keys=set()
    for path in paths:
        folder=path.parent;meta=json.loads(path.read_text())
        score=json.loads((folder/'score.json').read_text())
        key=(meta['instance_id'],meta['requested_model']);assert key not in keys;keys.add(key)
        for name,expected in meta.get('artifact_sha256',{}).items():
            assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==expected
        public_folder=ROOT/'results'/tag/folder.name
        exported=json.loads((public_folder/'result.json').read_text())
        assert exported['score']==public_score(score,meta['split'])
        if meta['split']=='sealed':assert sorted(p.name for p in public_folder.iterdir())==['result.json']
        if score['status']!='verified':
            assert not score['feasible'] and score['safe_tir'] in (0.,None)
            failed+=1;continue
        archive=folder/'native-traces.npz'
        assert hashlib.sha256(archive.read_bytes()).hexdigest()==score['native_traces_sha256']
        assert len(score['rows'])==18
        computed=[]
        with np.load(archive,allow_pickle=False) as data:
            assert len(data.files)==36
            for i,row in enumerate(score['rows']):
                trace=data[f'trace_{i:02d}'];minute=data[f'minute_{i:02d}']
                assert trace.shape==(1440,5) and minute.shape==(4321,)
                assert np.isfinite(trace).all() and np.isfinite(minute).all()
                glucose=trace[480:,0]
                metrics={'tir':100*np.count_nonzero((glucose>=70)&(glucose<=180))/len(glucose),
                         'tbr70':100*np.count_nonzero(glucose<70)/len(glucose),
                         'tbr54':100*np.count_nonzero(glucose<54)/len(glucose),
                         'minimum':float(minute.min()),'mean_glucose':float(np.sum(glucose)/len(glucose))}
                for name,value in metrics.items():
                    error=abs(value-row['metrics'][name]);max_error=max(max_error,error);assert error<1e-9
                computed.append(metrics)
        feasible=all(r['tbr70']<=4 and r['tbr54']<=1 and r['minimum']>=40 for r in computed)
        tir=sum(r['tir'] for r in computed)/18
        assert feasible==score['feasible']
        assert abs(score['mean_tir']-tir)<1e-9
        assert abs(score['safe_tir']-(tir if feasible else 0.))<1e-9
        verified+=1;safety_failed+=not feasible
    report={'passed':True,'attempts':len(paths),'verified_designs':verified,
            'failed_attempts_retained':failed,'safety_failures_retained':safety_failed,
            'native_trajectories_recomputed':verified*18,'maximum_metric_error':max_error,
            'note':'Independent arithmetic from saved native arrays. No submitted code executed. Sealed failure reasons are compared through the publication-only redaction function; raw private scores remain unchanged.'}
    dump(ROOT/'results'/tag/'audit.json',report)
    return report


def check_ledger(meta,folder):
    remaining=18000
    entries=meta['completion_token_accounting']
    assert len(entries)==meta['model_calls']<=12
    errors={e['call']:e for e in meta['api_errors']}
    assert len(errors)==len(meta['api_errors'])<=2
    violations=0;unexpected_failures=0
    for index,entry in enumerate(entries):
        assert remaining>0 and entry['call']==index
        assert entry['remaining_before']==remaining
        cap=min(6000,remaining)
        assert entry['requested_max_tokens']==cap
        basis=entry['basis']
        if basis=='failed_request_reserved_max':
            expected=cap
            if index in errors:
                assert errors[index]['charged_completion_tokens']==cap
            else:
                # The frozen runner's finally block reserves a pending request
                # even when an unexpected exception bypasses its API-error handler.
                assert meta['status']=='infrastructure_error' and meta.get('error_type')
                assert index==len(entries)-1
                unexpected_failures+=1
        else:
            assert index not in errors
            response=json.loads((folder/f'response-{index:02d}.json').read_text())
            usage=response.get('usage')
            value=usage.get('completion_tokens') if isinstance(usage,dict) else None
            valid=isinstance(value,int) and not isinstance(value,bool) and value>=0
            if basis=='provider_usage':
                assert valid and value<=cap
                assert entry['reported_completion_tokens']==value
                expected=value
            elif basis=='missing_or_invalid_usage_reserved_max':
                assert not valid
                expected=cap
            elif basis=='usage_exceeds_request':
                assert valid and value>cap and meta.get('token_usage_violation')
                assert meta['status']=='infrastructure_error'
                expected=cap;violations+=1
            else:raise AssertionError('Unrecognized accounting basis: '+basis)
        assert entry['charged_completion_tokens']==expected
        remaining-=expected
        assert entry['remaining_after']==remaining>=0
    assert meta['charged_completion_tokens']==18000-remaining<=18000
    assert meta['completion_token_budget_exhausted']==(remaining==0)
    assert not errors or max(errors)<len(entries)
    return {'attempts':len(entries),'charged':18000-remaining,'provider_usage_violations':violations,
            'unexpected_infrastructure_failure_reservations':unexpected_failures}


def main():
    plan=json.loads((EXPERIMENT/'plan.json').read_text())
    original_lock=verify_runtime_lock();verify_repeat_lock(plan['tags'][0])
    expected_commit=subprocess.check_output(['git','rev-parse','repeats-2026-11-11-plan^{}'],cwd=ROOT,text=True).strip()
    snapshot=json.loads((EXPERIMENT/'original-result-hashes.json').read_text())
    for name,expected in snapshot['files'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,name
    expected_keys={(j['tag'],j['case'],j['model']) for j in plan['jobs']}
    actual_keys=set();metadata=[];ledger_counts=[];native_audits=[];prompts_checked=0;evidence_checked=0;redacted_keys=set()
    for tag in plan['tags']:
        paths=sorted((ROOT/'private/runs'/tag).glob('*/metadata.json'))
        assert len(paths)==36,(tag,len(paths))
        for p in paths:
            meta=json.loads(p.read_text())
            key=(tag,meta['instance_id'],meta['requested_model'])
            assert key not in actual_keys;actual_keys.add(key)
            assert meta['source_commit']==expected_commit
            assert meta['execution_profile']=='strict-token-accounting-v1'
            assert meta['repetition_tag']==tag
            assert meta['image_id']==original_lock['pilot_image_id']
            assert meta['contract_sha256']==hashlib.sha256((ROOT/'contract/contract.json').read_bytes()).hexdigest()
            assert meta['system_prompt_sha256']==hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()
            assert meta['status']
            public=json.loads((ROOT/'results'/tag/p.parent.name/'result.json').read_text())
            assert all(public[k]==v for k,v in meta.items()),'Exported metadata mismatch'
            private_score=json.loads((p.parent/'score.json').read_text())
            if public['score'].get('reason')!=private_score.get('reason'):
                redacted_keys.add((tag,meta['trial_id']))
            for name,expected in public['private_evidence_sha256'].items():
                assert Path(name).name==name
                assert hashlib.sha256((p.parent/name).read_bytes()).hexdigest()==expected,'Evidence hash mismatch'
                evidence_checked+=1
            transcript=p.parent/'transcript.json'
            if transcript.exists():
                messages=json.loads(transcript.read_text())
                instance,_=load_case(meta['instance_id'])
                assert messages[0]=={'role':'system','content':SYSTEM_PROMPT}
                assert messages[1]=={'role':'user','content':(ROOT/'docs/AGENT_TASK.md').read_text()+'\n\nYOUR INSTANCE:\n'+json.dumps(instance)}
                prompts_checked+=1
            else:
                assert meta['status']!='submitted','Missing transcript for submitted trial'
            ledger_counts.append(check_ledger(meta,p.parent));metadata.append(meta)
        native_audits.append(audit_native_results(tag))
    assert actual_keys==expected_keys
    redactions=json.loads((DESTINATION/'publication-redactions.json').read_text())
    assert redactions['modified_score_values']==0
    assert len(redacted_keys)==len(redactions['records'])==redactions['redacted_exports']
    assert redacted_keys=={(r['tag'],r['trial_id']) for r in redactions['records']}
    for item in redactions['records']:
        archive=ROOT/'private/original-exports'/item['tag']/item['trial_id']/'result.json'
        published=ROOT/'results'/item['tag']/item['trial_id']/'result.json'
        score=ROOT/'private/runs'/item['tag']/item['trial_id']/'score.json'
        assert hashlib.sha256(archive.read_bytes()).hexdigest()==item['original_export_sha256']
        assert hashlib.sha256(published.read_bytes()).hexdigest()==item['published_result_sha256']
        assert hashlib.sha256(score.read_bytes()).hexdigest()==item['private_score_sha256']
        original=json.loads(archive.read_text());current=json.loads(published.read_text())
        original['score']['reason']=current['score']['reason']
        assert original==current,'Publication changed more than the diagnostic reason'
    report={'passed':True,'planned_and_audited_attempts':len(actual_keys),
            'source_commit':expected_commit,'original_result_files_unchanged':len(snapshot['files']),
            'original_runtime_files_unchanged':len(original_lock['files']),
            'supplemental_implementation_files_unchanged':len(json.loads((EXPERIMENT/'lock.json').read_text())['files']),
            'saved_initial_prompts_verified':prompts_checked,
            'private_evidence_hashes_verified':evidence_checked,
            'sealed_error_diagnostic_redactions_verified':redactions['redacted_exports'],
            'api_requests_accounted':sum(x['attempts'] for x in ledger_counts),
            'maximum_charged_completion_tokens':max(x['charged'] for x in ledger_counts),
            'provider_usage_overrun_requests':sum(x['provider_usage_violations'] for x in ledger_counts),
            'unexpected_infrastructure_failure_reservations':sum(x['unexpected_infrastructure_failure_reservations'] for x in ledger_counts),
            'maximum_recorded_cpu_seconds':max(m.get('cpu_seconds',0.) for m in metadata),
            'cpu_measurements_above_30_seconds':sum(m.get('cpu_seconds',0.)>30 for m in metadata),
            'maximum_recorded_wall_seconds':max(m['wall_seconds'] for m in metadata),
            'wall_measurements_above_360_seconds':sum(m['wall_seconds']>360 for m in metadata),
            'maximum_recorded_tool_wall_seconds':max(m.get('tool_wall_seconds',0.) for m in metadata),
            'tool_wall_measurements_above_90_seconds':sum(m.get('tool_wall_seconds',0.)>90 for m in metadata),
            'verified_designs':sum(a['verified_designs'] for a in native_audits),
            'submission_or_technical_failures_retained':sum(a['failed_attempts_retained'] for a in native_audits),
            'safety_failures_retained':sum(a['safety_failures_retained'] for a in native_audits),
            'native_trajectories_recomputed':sum(a['native_trajectories_recomputed'] for a in native_audits),
            'maximum_metric_error':max(a['maximum_metric_error'] for a in native_audits),
            'note':'All planned attempts retained; failures contribute zero to workflow aggregates. Token reservations include failed requests. Above-limit resource measurements, if any, are disclosed rather than hidden. All original release result bytes are preserved.'}
    DESTINATION.mkdir(parents=True,exist_ok=True)
    dump(DESTINATION/'audit.json',report)
    print(json.dumps(report))


if __name__=='__main__':main()
