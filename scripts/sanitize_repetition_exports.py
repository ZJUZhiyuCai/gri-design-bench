"""Archive and redact sealed error diagnostics after all supplemental trials finish.

This is a publication-only step. It changes no submission, private score,
numeric metric, execution file, or original release result.
"""
import hashlib
import json
from gri_bench.publication import public_score
from gri_bench.runner import ROOT, dump


def digest(raw):return hashlib.sha256(raw).hexdigest()


def evidence(tag,record,original,score,published):
    return {'tag':tag,'trial_id':record['trial_id'],'changed_fields':['score.reason'],
            'original_export_sha256':digest(original),'private_score_sha256':digest(score),
            'published_result_sha256':digest(published),'published_reason':record['score']['reason']}


def main():
    plan=json.loads((ROOT/'experiments/repeats-2026-11-11/plan.json').read_text())
    expected={(j['tag'],j['case'],j['model']) for j in plan['jobs']}
    files=[p for tag in plan['tags'] for p in (ROOT/'results'/tag).glob('*/result.json')]
    actual={(p.parents[1].name,json.loads(p.read_text())['instance_id'],json.loads(p.read_text())['requested_model']) for p in files}
    assert actual==expected and len(files)==108,'Require the complete graded matrix'
    report_path=ROOT/'results/repetitions-2026-11-11/publication-redactions.json'
    report_path.parent.mkdir(parents=True,exist_ok=True)
    records=json.loads(report_path.read_text())['records'] if report_path.exists() else []
    known={(r['tag'],r['trial_id']):r for r in records}
    assert len(known)==len(records)
    for path in files:
        raw=path.read_bytes();record=json.loads(raw);tag=path.parents[1].name
        private=ROOT/'private/runs'/tag/path.parent.name
        score_raw=(private/'score.json').read_bytes();score=json.loads(score_raw)
        expected_score=public_score(score,record['split'])
        archive=ROOT/'private/original-exports'/tag/path.parent.name/'result.json'
        if record['score']==expected_score:
            if (tag,record['trial_id']) in known:
                assert digest(raw)==known[(tag,record['trial_id'])]['published_result_sha256']
            elif archive.exists():
                # Recover if publication finished but a process stopped before
                # writing the final manifest. Never overwrite the original.
                original=archive.read_bytes();expected_original={**record,'score':{k:v for k,v in score.items() if k!='rows'}}
                assert json.loads(original)==expected_original
                assert expected_original['score']!=expected_score and record['split']=='sealed'
                item=evidence(tag,record,original,score_raw,raw)
                records.append(item);known[(tag,record['trial_id'])]=item
            continue
        assert record['score']=={k:v for k,v in score.items() if k!='rows'}
        assert record['split']=='sealed'
        assert (tag,record['trial_id']) not in known
        assert {k:v for k,v in record['score'].items() if k!='reason'}=={k:v for k,v in expected_score.items() if k!='reason'}
        archive.parent.mkdir(parents=True,exist_ok=True)
        if archive.exists():assert archive.read_bytes()==raw
        else:archive.write_bytes(raw)
        record['score']=expected_score;dump(path,record)
        item=evidence(tag,record,raw,score_raw,path.read_bytes())
        records.append(item);known[(tag,record['trial_id'])]=item
    report={'scope':'Supplemental public exports only; all original release result bytes unchanged.',
            'reason':'Frozen verifier exception messages can contain private sealed bounds. Publication redacts diagnostic text only; raw scores and original exports remain private with hashes.',
            'modified_score_values':0,'redacted_exports':len(records),'records':records}
    dump(report_path,report);print(json.dumps({'redacted_exports':len(records),'modified_score_values':0}))


if __name__=='__main__':main()
