"""Read the supplied XLSX using standard XML/ZIP parsing, no Excel dependency."""
import argparse,collections,json,re,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
from support import read,write,dump,INTENTS,filehash
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
REL='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'

def sheets(path):
    with zipfile.ZipFile(path) as z:
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():strings=[''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',NS)]
        book=ET.fromstring(z.read('xl/workbook.xml'));rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        targets={r.attrib['Id']:r.attrib['Target'] for r in rels}
        out={}
        for s in book.findall('m:sheets/m:sheet',NS):
            target=targets[s.attrib[REL]];target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
            rows=[]
            for row in ET.fromstring(z.read(target)).findall('m:sheetData/m:row',NS):
                cells={}
                for c in row:
                    col=re.sub(r'\d','',c.attrib['r']);v=c.find('m:v',NS);value=v.text if v is not None else ''
                    if c.attrib.get('t')=='s':value=strings[int(value)]
                    if c.attrib.get('t')=='inlineStr':value=''.join(c.find('m:is',NS).itertext())
                    cells[col]=(value or '').strip()
                rows.append(cells)
            out[s.attrib['name']]=rows
        return out

def grouped_evidence(ss):
    if 'Evidence' not in ss:raise ValueError('Evidence tab required')
    grouped=collections.defaultdict(list)
    for row in ss['Evidence']:
        rid=row.get('A')
        if not rid or rid=='review_id':continue
        grouped[rid].append({'id':row.get('B',''),'message':row.get('C',''),'reply':row.get('D','')})
    return grouped

def check_evidence(review_id, orig, grouped, evidence_ids_cell):
    expected_ids=[e['id'] for e in orig['evidence']]
    if (evidence_ids_cell or '')!=','.join(expected_ids):raise ValueError(f'Evidence IDs changed for {review_id}')
    actual=grouped.get(review_id,[])
    if [e['id'] for e in actual]!=expected_ids:raise ValueError(f'Evidence IDs changed for {review_id}')
    for exp,got in zip(orig['evidence'],actual):
        if got['message']!=exp['message'] or got['reply']!=exp['reply']:raise ValueError(f'Evidence content changed for {review_id}')

def run(a):
    ss=sheets(a.workbook);gold=[];ratings=[];original={r['id']:r for r in read(a.test)}
    for row in ss['Gold labels']:
        if row.get('A') not in original:continue
        r=original[row['A']].copy()
        if row.get('B')!=r['message']:raise ValueError('Customer message changed in workbook')
        if row.get('C') not in INTENTS or row.get('D') not in ('0','1') or not row.get('E') or not row.get('F'):raise ValueError(f"Complete intent, escalation, reason and annotator for {r['id']}")
        r.update(intent=row['C'],escalate=row['D'],label_reason=row['E'],annotator=row['F'],label_source='human');gold.append(r)
    if len(gold)!=len(original) or len({r['id'] for r in gold})!=len(original):raise ValueError('Missing or duplicate gold IDs')
    # Restore canonical ordering for prediction hashes.
    indexed={r['id']:r for r in gold};gold=[indexed[r['id']] for r in read(a.test)]
    blind={r['review_id']:r for r in json.loads(Path(a.blind).read_text())}
    evidence=grouped_evidence(ss)
    if set(evidence)!=set(blind):raise ValueError('Evidence tab IDs do not match the blind cohort')
    for row in ss['Reply ratings']:
        if row.get('A') not in blind:continue
        orig=blind[row['A']]
        if row.get('B')!=orig['message'] or row.get('C')!=orig['reply']:raise ValueError('Rated content changed')
        check_evidence(row['A'],orig,evidence,row.get('D'))
        scores={k:row.get(col,'') for k,col in zip(['grounding','relevance','safety','clarity'],['E','F','G','H'])}
        if any(v not in ['1','2','3','4','5'] for v in scores.values()) or not row.get('I') or not row.get('J'):raise ValueError('Complete all reply ratings, reason and annotator')
        ratings.append({'review_id':row['A'],**scores,'reason':row['I'],'annotator':row['J'],'label_source':'human'})
    if len(ratings)!=len(blind) or len({r['review_id'] for r in ratings})!=len(blind):raise ValueError('Missing or duplicate reply ratings')
    write(a.out+'/gold.csv',gold);write(a.out+'/human_ratings.csv',ratings)
    dump(a.out+'/human_provenance.json',{'source':'xlsx','workbook_sha256':filehash(a.workbook),'blind_sha256':filehash(a.blind),'test_sha256':filehash(a.test),'gold_sha256':filehash(Path(a.out)/'gold.csv'),'ratings_sha256':filehash(Path(a.out)/'human_ratings.csv'),'note':'Human origin is self-attested by the named annotators; the importer validates completeness, not identity.'})
    print(f'Imported {len(gold)} gold labels and {len(ratings)} human ratings')

def main():
    p=argparse.ArgumentParser();p.add_argument('workbook');p.add_argument('--test',default='data/test.csv');p.add_argument('--blind',default='review/blind_replies.json');p.add_argument('--out',default='data');run(p.parse_args())
if __name__=='__main__':main()
