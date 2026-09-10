"""Read-only checks of all packaged splits and cached prediction provenance."""
import itertools,json,time
from pathlib import Path
from support import read,dump,filehash,normalized
from workflow import isolation,source_hash
root=Path(__file__).resolve().parents[1]
parts={k:read(root/'data'/f'{k}.csv') for k in ['train','dev','test']}
for a,b in itertools.combinations(parts,2):isolation(parts[a],parts[b])
b=json.loads((root/'results/predictions.json').read_text())
if b['metadata']['train_sha256']!=filehash(root/'data/train.csv'):raise ValueError('Training cache mismatch')
if b['metadata']['code_sha256']!=source_hash():raise ValueError('Code cache mismatch. Regenerate predictions after changes.')
train_ids={r['id'] for r in parts['train']}
for p in b['predictions']:
 if any(e['id'] not in train_ids for e in p['evidence']):raise ValueError('Evidence outside training')
 if not set(p['cited_ids'])<=set(e['id'] for e in p['evidence']):raise ValueError('Citation outside evidence')
result={'status':'passed','counts':{k:len(v) for k,v in parts.items()},'customer_overlap':0,'tweet_overlap':0,'normalized_exact_overlap':0,'prediction_count':len(b['predictions']),'all_evidence_in_training':True,'human_labels_present':sum(bool(r['annotator']) for r in parts['test']),'scope':'Does not detect semantic near-duplicates or guarantee root threads are complete.'}
dump(root/'results/data_audit.json',result);print(json.dumps(result,indent=2))
