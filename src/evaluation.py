"""Metrics use human labels only. Bootstrap resamples customer groups."""
import collections, math, random
from support import INTENTS

def wilson(k,n):
    if not n:return None
    z=1.959963984540054;p=k/n;d=1+z*z/n
    center=(p+z*z/(2*n))/d;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [max(0,center-half),min(1,center+half)]

def score(gold,preds):
    if not gold or len(gold)!=len(preds):raise ValueError('Gold/prediction lengths must match and be nonempty')
    confusion={g:{p:0 for p in INTENTS} for g in INTENTS}
    for g,p in zip(gold,preds):
        if p['intent'] not in INTENTS or type(p['escalate']) is not int or p['escalate'] not in (0,1):raise ValueError('Invalid prediction')
        confusion[g['intent']][p['intent']]+=1
    classes={}
    for label in INTENTS:
        tp=confusion[label][label];support=sum(confusion[label].values());predicted=sum(row[label] for row in confusion.values())
        classes[label]={'support':support,'predicted':predicted,'precision':tp/predicted if predicted else None,'recall':tp/support if support else None,'f1':2*tp/(support+predicted) if support+predicted else 0}
    n=len(gold);auto=sum(p['escalate']==0 for p in preds);unsafe=sum(g['escalate']=='1' and p['escalate']==0 for g,p in zip(gold,preds));need=sum(g['escalate']=='1' for g in gold);caught=need-unsafe
    acc=sum(g['intent']==p['intent'] for g,p in zip(gold,preds))/n
    supported=[x['f1'] for x in classes.values() if x['support']]
    return {'n':n,'intent_accuracy':acc,'intent_macro_f1':sum(x['f1'] for x in classes.values())/len(INTENTS),'intent_macro_f1_present_classes':sum(supported)/len(supported),'auto_coverage':auto/n,'auto_count':auto,'unsafe_auto_count':unsafe,'unsafe_auto_rate':unsafe/auto if auto else None,'unsafe_auto_wilson95':wilson(unsafe,auto),'human_needed_count':need,'escalation_recall':caught/need if need else None,'unnecessary_escalation_count':sum(g['escalate']=='0' and p['escalate']==1 for g,p in zip(gold,preds)),'per_intent':classes,'confusion_matrix':confusion}

def bootstrap(gold,preds,iterations=500):
    groups=collections.defaultdict(list)
    for i,g in enumerate(gold):groups[g['group']].append(i)
    keys=sorted(groups);rng=random.Random(2026);values=collections.defaultdict(list)
    for _ in range(iterations):
        ids=[i for key in rng.choices(keys,k=len(keys)) for i in groups[key]]
        m=score([gold[i] for i in ids],[preds[i] for i in ids])
        for k in ['intent_macro_f1','intent_accuracy','auto_coverage','escalation_recall']:
            if m[k] is not None:values[k].append(m[k])
    result={}
    for k,v in values.items():
        v.sort();result[k]=[v[int(.025*(len(v)-1))],v[int(.975*(len(v)-1))]]
    return {'method':'customer-group percentile bootstrap','iterations':iterations,'seed':2026,'intervals95':result}

def agreement(pairs):
    if not pairs:raise ValueError('No rating pairs')
    if any(type(v) is not int or not 1<=v<=5 for pair in pairs for v in pair):raise ValueError('Scores must be integers 1–5')
    n=len(pairs);x=collections.Counter(a for a,b in pairs);y=collections.Counter(b for a,b in pairs)
    obs=sum((a-b)**2 for a,b in pairs)/n;exp=sum(x[a]*y[b]*(a-b)**2 for a in x for b in y)/n**2
    return {'n':n,'exact_agreement':sum(a==b for a,b in pairs)/n,'within_one':sum(abs(a-b)<=1 for a,b in pairs)/n,'mean_absolute_error':sum(abs(a-b) for a,b in pairs)/n,'quadratic_weighted_kappa':1-obs/exp if exp else None}

def system_rating_summary(rows, mapping, dims, systems):
    by_review={m['review_id']:m['model'] for m in mapping}
    if len(by_review)!=len(mapping):raise ValueError('Duplicate review mapping IDs')
    missing=[r.get('review_id') for r in rows if r.get('review_id') not in by_review]
    if missing:raise ValueError('Rating ID missing from review mapping')
    out={}
    for model in systems:
        selected=[r for r in rows if by_review[r['review_id']]==model]
        entry={'n':len(selected)}
        for dim in dims:
            vals=[int(r[dim]) for r in selected]
            entry[dim]={'n':len(vals),'mean':(sum(vals)/len(vals) if vals else None),'counts':{str(i):vals.count(i) for i in range(1,6)}}
        out[model]=entry
    return out
