"""Reproducible generation, blind review, label import, final scoring and gates."""
import argparse, collections, csv, json, os, random, re, sys, time
from pathlib import Path
from support import read,write,dump,digest,filehash,normalized,clean,intent,Retriever,predict,INTENTS,validate
from evaluation import score,bootstrap,agreement,system_rating_summary
from judge import RUBRIC
SYSTEMS=['trivial','simple','agent']
DIMS=['grounding','relevance','safety','clarity']
METRIC_KEYS=['n','intent_accuracy','intent_macro_f1','intent_macro_f1_present_classes','auto_coverage','auto_count','unsafe_auto_count','unsafe_auto_rate','unsafe_auto_wilson95','human_needed_count','escalation_recall','unnecessary_escalation_count']
AGREEMENT_KEYS=['n','exact_agreement','within_one','mean_absolute_error','quadratic_weighted_kappa']
ROOT=Path(__file__).resolve().parents[1]

def source_hash():
    # Prediction identity is the agent, not report/import helpers.
    return filehash(ROOT/'src'/'support.py')

def isolation(train,test):
    for key in ['id','group']:
        if {r[key] for r in train}&{r[key] for r in test}:raise ValueError(f'{key} overlap between training and evaluation')
    if {normalized(r['message']) for r in train}&{normalized(r['message']) for r in test}:raise ValueError('Normalized message overlap')

def generate(a):
    if not 0<=a.threshold<=1:raise ValueError('Threshold must be between 0 and 1')
    if a.llm and not all(os.environ.get(k) for k in ['LLM_BASE_URL','LLM_MODEL','LLM_API_KEY']):raise ValueError('Configure LLM credentials before requesting generation')
    train=read(a.train);test=read(a.test);isolation(train,test)
    retriever=Retriever(train);labels=[r['intent'] or intent(r['message']) for r in train]
    majority=collections.Counter(labels).most_common(1)[0][0];start=time.perf_counter();outputs=[]
    for g in test:
        # Pass only the message. Reference reply and human labels cannot enter prediction.
        row={'message':g['message']}
        for model in SYSTEMS:
            then=time.perf_counter();p=predict(row,model,retriever,majority,a.threshold,a.llm and model=='agent')
            outputs.append({'id':g['id'],'message':g['message'],'model':model,**p,'latency_ms':(time.perf_counter()-then)*1000})
    payload={'metadata':{'status':'UNSCORED_REAL_DATA','train_sha256':filehash(a.train),'messages_sha256':digest(json.dumps([(r['id'],r['message']) for r in test])),'code_sha256':source_hash(),'threshold':a.threshold,'threshold_status':'fixed engineering choice; not human-calibrated','label_source':'weak keyword labels except any explicitly labelled training rows','llm':a.llm,'llm_model':os.environ.get('LLM_MODEL') if a.llm else None,'runtime_seconds':time.perf_counter()-start,'n_messages':len(test)},'predictions':outputs}
    dump(a.output,payload)
    print(json.dumps({'output':a.output,'n_messages':len(test),'n_predictions':len(outputs),'seconds':payload['metadata']['runtime_seconds'],'draft_sources':dict(collections.Counter(p['draft_source'] for p in outputs if p['model']=='agent'))},indent=2))

def ask(a):
    train=read(a.train);r=Retriever(train)
    majority=collections.Counter(x['intent'] or intent(x['message']) for x in train).most_common(1)[0][0]
    print(json.dumps(predict({'message':clean(a.message)},'agent',r,majority,a.threshold,a.llm),indent=2,ensure_ascii=False))

def shared_evidence(rows, message_id):
    common={}
    for x in rows:
        if x['id']==message_id:
            for e in x['evidence']:
                common[e['id']]=e
    return [common[k] for k in sorted(common)]

def review(a):
    bundle=json.loads(Path(a.predictions).read_text());rows=bundle['predictions'];mapping=[];blind=[]
    rng=random.Random(71)
    # Matched 20-message cohort, three systems per message. Randomize presentation.
    ids=sorted(set(r['id'] for r in rows));chosen=set(rng.sample(ids,min(20,len(ids))))
    selected=[r for r in rows if r['id'] in chosen];rng.shuffle(selected)
    for i,p in enumerate(selected):
        rid=f'R{i+1:03d}'
        evidence=shared_evidence(rows, p['id'])
        blind.append({'review_id':rid,'message':p['message'],'reply':p['reply'],'evidence':evidence,'grounding':'','relevance':'','safety':'','clarity':'','reason':'','annotator':''})
        mapping.append({'review_id':rid,'id':p['id'],'model':p['model']})
    dump(a.out+'/blind_replies.json',blind);dump(a.out+'/review_mapping.json',mapping)
    dump(a.out+'/review_manifest.json',{'seed':71,'n_messages':len(chosen),'n_replies':len(blind),'prediction_sha256':filehash(a.predictions),'blind_sha256':filehash(a.out+'/blind_replies.json')})
    print('Created blind reply cohort. Keep mapping and model outputs closed until human rating is complete.')

def human_labels(rows):
    validate(rows)
    for r in rows:
        if r.get('label_source')!='human' or any(t in r['annotator'].upper() for t in ['SYNTHETIC','AI_GENERATED']):raise ValueError('Human label provenance required')

def score_systems(gold, bundle, gold_path, predictions_path):
    human_labels(gold)
    if not 150<=len(gold)<=250:raise ValueError('150–250 human-labelled gold examples required')
    if digest(json.dumps([(r['id'],r['message']) for r in gold]))!=bundle['metadata']['messages_sha256']:raise ValueError('Gold messages differ from the prediction cohort')
    outputs=bundle['predictions'];result={'provenance':bundle['metadata'],'gold_sha256':filehash(gold_path),'predictions_sha256':filehash(predictions_path),'systems':{}}
    for model in SYSTEMS:
        selected=[r for r in outputs if r['model']==model];idx={r['id']:r for r in selected}
        if len(idx)!=len(selected) or set(idx)!={r['id'] for r in gold}:raise ValueError('Duplicate or missing prediction IDs')
        ordered=[idx[r['id']] for r in gold];result['systems'][model]={**score(gold,ordered),'bootstrap':bootstrap(gold,ordered)}
    failures=[]
    for g in gold:
        for p in outputs:
            if p['id']==g['id'] and (g['intent']!=p['intent'] or int(g['escalate'])!=p['escalate']):
                failures.append({'id':g['id'],'model':p['model'],'message':g['message'],'gold_intent':g['intent'],'predicted_intent':p['intent'],'gold_escalate':g['escalate'],'predicted_escalate':p['escalate'],'reply':p['reply'],'human_reason':g['label_reason']})
    return result, failures

def finish(a):
    gold=read(a.gold);bundle=json.loads(Path(a.predictions).read_text())
    result,failures=score_systems(gold,bundle,a.gold,a.predictions)
    dump(a.out+'/metrics.json',result);dump(a.out+'/failures.json',failures)
    print('Scored all three systems. Inspect failures.json and finish report.md before submission.')

def require_full_evidence(judge):
    if not judge.get('metadata',{}).get('complete'):raise ValueError('Judge run incomplete')
    if judge['metadata'].get('evidence_omitted'):raise ValueError('Judge ratings omitted historical evidence')
    if any(r.get('evidence_omitted') for r in judge.get('ratings',[])):raise ValueError('Judge ratings omitted historical evidence')

def agreement_payload(humans, judge, mapping, human_path, judge_path):
    require_full_evidence(judge)
    if judge['metadata']['blind_sha256']!=filehash(ROOT/'review/blind_replies.json'):raise ValueError('Judge rated a different review cohort')
    provenance=json.loads((ROOT/'data/human_provenance.json').read_text())
    if provenance['blind_sha256']!=judge['metadata']['blind_sha256']:raise ValueError('Human and judge cohorts differ')
    idx={r['review_id']:r for r in judge['ratings']}
    if len(idx)!=len(judge['ratings']):raise ValueError('Duplicate judge IDs')
    if len(humans)<30 or len({r['review_id'] for r in humans})!=len(humans):raise ValueError('At least 30 unique human ratings required')
    for r in humans:
        if r.get('label_source')!='human' or not r['annotator'].strip() or not r.get('reason','').strip():raise ValueError('Complete human rating provenance required')
        if r['review_id'] not in idx:raise ValueError('Missing judge rating')
    metrics={k:agreement([(int(r[k]),idx[r['review_id']][k]) for r in humans]) for k in DIMS}
    disagreements=[{'review_id':r['review_id'],'dimension':k,'human':int(r[k]),'judge':idx[r['review_id']][k]} for r in humans for k in DIMS if abs(int(r[k])-idx[r['review_id']][k])>=2]
    judge_rows=[{'review_id':r['review_id'],**{k:r[k] for k in DIMS}} for r in judge['ratings']]
    return {'metrics':metrics,'systems':{'human':system_rating_summary(humans,mapping,DIMS,SYSTEMS),'judge':system_rating_summary(judge_rows,mapping,DIMS,SYSTEMS)},'large_disagreements':disagreements,'human_sha256':filehash(human_path),'judge_sha256':filehash(judge_path),'rubric_sha256':judge['metadata']['rubric_sha256'],'caveat':'60 replies from 20 messages are correlated; agreement is descriptive, not a population guarantee. Pooled judge-human agreement does not by itself compare systems.'}

def compare(a):
    humans=read(a.human);judge=json.loads(Path(a.judge).read_text())
    mapping=json.loads((ROOT/'review/review_mapping.json').read_text())
    dump(a.output,agreement_payload(humans,judge,mapping,a.human,a.judge))

def verify_blind_matches_predictions(bundle):
    mapping=json.loads((ROOT/'review/review_mapping.json').read_text())
    blind={r['review_id']:r for r in json.loads((ROOT/'review/blind_replies.json').read_text())}
    preds={(p['id'],p['model']):p for p in bundle['predictions']}
    for row in mapping:
        if row['review_id'] not in blind:raise ValueError('Review mapping ID missing from blind replies')
        p=preds.get((row['id'],row['model']))
        if not p:raise ValueError('Blind mapping refers to a missing prediction')
        b=blind[row['review_id']]
        if b['message']!=p['message'] or b['reply']!=p['reply']:raise ValueError('Blind replies drifted from predictions')

def verify_gold_matches_test(gold, test):
    test_by={r['id']:r for r in test}
    if [r['id'] for r in gold]!=[r['id'] for r in test]:raise ValueError('Gold order differs from test')
    for g in gold:
        t=test_by[g['id']]
        if g['group']!=t['group'] or g['message']!=t['message']:raise ValueError('Gold customer group or message drifted from test')
    if digest(json.dumps([(r['id'],r['message']) for r in gold]))!=digest(json.dumps([(r['id'],r['message']) for r in test])):raise ValueError('Gold messages differ from test')

def packet_rows(packet):
    return [{'id':e['id'],'message':e['message'],'reply':e['reply']} for e in packet]

def check_review_evidence(train, bundle, mapping, blind):
    train_by={r['id']:r for r in train}
    blind_by={r['review_id']:r for r in blind}
    if len(mapping)!=60 or len(blind_by)!=60:raise ValueError('Blind review cohort is incomplete')
    if {r['review_id'] for r in mapping}!=set(blind_by):raise ValueError('Review mapping does not match blind replies')
    for p in bundle['predictions']:
        for e in p.get('evidence',[]):
            src=train_by.get(e['id'])
            if not src:raise ValueError('Review evidence outside training')
            if e.get('message')!=src['message'] or e.get('reply')!=src['historical_reply']:
                raise ValueError('Prediction evidence text drifted from training')
    packets_by_message={}
    for row in mapping:
        packet=blind_by[row['review_id']].get('evidence') or []
        if not packet:raise ValueError('Empty review evidence packet')
        ids=[e['id'] for e in packet]
        if len(ids)!=len(set(ids)):raise ValueError('Duplicate evidence IDs in a review packet')
        for e in packet:
            src=train_by.get(e['id'])
            if not src:raise ValueError('Review evidence outside training')
            if e.get('message')!=src['message'] or e.get('reply')!=src['historical_reply']:
                raise ValueError('Review evidence text drifted from training')
        expected=packet_rows(shared_evidence(bundle['predictions'], row['id']))
        if packet_rows(packet)!=expected:raise ValueError('Review evidence packet does not match the shared message packet')
        packets_by_message.setdefault(row['id'], []).append(tuple((e['id'],e['message'],e['reply']) for e in packet))
    for packets in packets_by_message.values():
        if len(set(packets))!=1:raise ValueError('Evidence packets differ across systems for a message')

def verify_review_evidence(train, bundle):
    mapping=json.loads((ROOT/'review/review_mapping.json').read_text())
    blind=json.loads((ROOT/'review/blind_replies.json').read_text())
    verify_blind_matches_predictions(bundle)
    check_review_evidence(train, bundle, mapping, blind)

def verify_chain():
    train=read(ROOT/'data/train.csv');test=read(ROOT/'data/test.csv');gold=read(ROOT/'data/gold.csv')
    isolation(train,test);human_labels(gold)
    verify_gold_matches_test(gold, test)
    bundle=json.loads((ROOT/'results/predictions.json').read_text())
    if bundle['metadata']['train_sha256']!=filehash(ROOT/'data/train.csv'):raise ValueError('Stale training data')
    if bundle['metadata']['code_sha256']!=source_hash():raise ValueError('Stale agent code')
    if digest(json.dumps([(r['id'],r['message']) for r in test]))!=bundle['metadata']['messages_sha256']:raise ValueError('Prediction messages differ from test')
    verify_review_evidence(train, bundle)
    stored=json.loads((ROOT/'results/final/metrics.json').read_text())
    recomputed,_=score_systems(gold,bundle,ROOT/'data/gold.csv',ROOT/'results/predictions.json')
    if stored['gold_sha256']!=filehash(ROOT/'data/gold.csv'):raise ValueError('Stale gold metrics')
    if stored['predictions_sha256']!=filehash(ROOT/'results/predictions.json'):raise ValueError('Stale predictions')
    for model in SYSTEMS:
        if model not in stored.get('systems',{}):raise ValueError('Forged or incomplete metrics')
        if stored['systems'][model]!=recomputed['systems'][model]:raise ValueError(f'Metrics mismatch for {model}')
    humans=read(ROOT/'data/human_ratings.csv');judge=json.loads((ROOT/'results/judge.json').read_text())
    mapping=json.loads((ROOT/'review/review_mapping.json').read_text())
    if {r['review_id'] for r in humans}!={m['review_id'] for m in mapping}:raise ValueError('Human ratings do not cover the review mapping')
    if judge['metadata'].get('rubric_sha256')!=digest(RUBRIC):raise ValueError('Judge rubric hash mismatch')
    require_full_evidence(judge)
    expected=agreement_payload(humans,judge,mapping,ROOT/'data/human_ratings.csv',ROOT/'results/judge.json')
    stored_ag=json.loads((ROOT/'results/final/agreement.json').read_text())
    if stored_ag['human_sha256']!=filehash(ROOT/'data/human_ratings.csv') or stored_ag['judge_sha256']!=filehash(ROOT/'results/judge.json'):raise ValueError('Stale agreement')
    if stored_ag.get('rubric_sha256')!=digest(RUBRIC):raise ValueError('Agreement rubric hash mismatch')
    if 'systems' not in stored_ag:raise ValueError('Agreement missing per-system reply scores')
    for key in ['metrics','systems','large_disagreements']:
        if stored_ag.get(key)!=expected[key]:raise ValueError(f'Agreement mismatch for {key}')
    provenance=json.loads((ROOT/'data/human_provenance.json').read_text())
    if provenance.get('source') not in {'cli','xlsx'}:raise ValueError('Human labels must come from the CLI or workbook importer')
    if provenance.get('blind_sha256')!=filehash(ROOT/'review/blind_replies.json'):raise ValueError('Provenance blind mismatch')
    if provenance.get('test_sha256')!=filehash(ROOT/'data/test.csv'):raise ValueError('Provenance test mismatch')
    manifest=json.loads((ROOT/'results/final/report_manifest.json').read_text())
    if manifest.get('report_sha256')!=filehash(ROOT/'docs/report.md'):raise ValueError('Stale report')
    if manifest.get('metrics_sha256')!=filehash(ROOT/'results/final/metrics.json'):raise ValueError('Stale report metrics hash')
    if manifest.get('agreement_sha256')!=filehash(ROOT/'results/final/agreement.json'):raise ValueError('Stale report agreement hash')
    return {'recomputed':True,'systems':list(SYSTEMS),'rubric_sha256':digest(RUBRIC)}

def gate(a):
    required=['data/gold.csv','data/human_ratings.csv','data/human_provenance.json','results/judge.json','results/final/metrics.json','results/final/agreement.json','results/final/report_manifest.json']
    missing=[p for p in required if not (ROOT/p).exists()]
    checks={'missing_files':missing,'passed':False}
    if not missing:
        try:
            checks.update(verify_chain());checks['passed']=True
        except Exception as e:checks['error']=str(e)
    print(json.dumps(checks,indent=2));return 0 if checks['passed'] else 2

def main():
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='command',required=True)
    x=s.add_parser('generate');x.add_argument('--train',default='data/train.csv');x.add_argument('--test',default='data/test.csv');x.add_argument('--output',default='results/predictions.json');x.add_argument('--threshold',type=float,default=.25);x.add_argument('--llm',action='store_true');x.set_defaults(fn=generate)
    x=s.add_parser('ask');x.add_argument('message');x.add_argument('--train',default='data/train.csv');x.add_argument('--threshold',type=float,default=.25);x.add_argument('--llm',action='store_true');x.set_defaults(fn=ask)
    x=s.add_parser('review');x.add_argument('--predictions',default='results/predictions.json');x.add_argument('--out',default='review');x.set_defaults(fn=review)
    x=s.add_parser('score');x.add_argument('--gold',default='data/gold.csv');x.add_argument('--predictions',default='results/predictions.json');x.add_argument('--out',default='results/final');x.set_defaults(fn=finish)
    x=s.add_parser('agreement');x.add_argument('--human',default='data/human_ratings.csv');x.add_argument('--judge',default='results/judge.json');x.add_argument('--output',default='results/final/agreement.json');x.set_defaults(fn=compare)
    x=s.add_parser('check');x.set_defaults(fn=gate)
    a=p.parse_args();code=a.fn(a);sys.exit(code or 0)
if __name__=='__main__':main()
