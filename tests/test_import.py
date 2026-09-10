import argparse,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,'src')
from import_review import sheets,run
from support import read
class ImportTests(unittest.TestCase):
 def test_real_workbook_has_blank_labels(self):
  path=Path('review/human-review.xlsx')
  ss=sheets(path);original={r['id']:r for r in read('data/test.csv')}
  rows=[r for r in ss['Gold labels'] if r.get('A') in original]
  self.assertEqual(len(rows),200)
  for r in rows:
   self.assertEqual(r['B'],original[r['A']]['message'])
   self.assertFalse(r.get('C'));self.assertFalse(r.get('D'))
  self.assertIn('Evidence',ss)
 def fixture(self,gold,blind):
  evidence=[{'A':r['review_id'],'B':e['id'],'C':e['message'],'D':e['reply']} for r in blind for e in r['evidence']]
  return {
   'Gold labels':[dict(A=r['id'],B=r['message'],C='other',D='1',E='SYNTHETIC UNIT TEST',F='TEST_FIXTURE') for r in reversed(gold)],
   'Reply ratings':[dict(A=r['review_id'],B=r['message'],C=r['reply'],D=','.join(e['id'] for e in r['evidence']),E='1',F='2',G='3',H='4',I='SYNTHETIC UNIT TEST',J='TEST_FIXTURE') for r in blind],
   'Evidence':evidence,
  }
 def test_complete_fixture_import_and_reordered_rows(self):
  gold=read('data/test.csv');blind=json.loads(Path('review/blind_replies.json').read_text())
  ss=self.fixture(gold,blind)
  with tempfile.TemporaryDirectory() as tmp:
   a=argparse.Namespace(workbook='README.md',test='data/test.csv',blind='review/blind_replies.json',out=tmp)
   with patch('import_review.sheets',return_value=ss):run(a)
   self.assertEqual([r['id'] for r in read(Path(tmp)/'gold.csv')],[r['id'] for r in gold])
   self.assertEqual(len(read(Path(tmp)/'human_ratings.csv')),60)
   ss['Gold labels'][0]['B']='tampered'
   with patch('import_review.sheets',return_value=ss):
    with self.assertRaisesRegex(ValueError,'changed'):run(a)
 def test_evidence_content_mismatch_rejected(self):
  gold=read('data/test.csv');blind=json.loads(Path('review/blind_replies.json').read_text())
  ss=self.fixture(gold,blind)
  ss['Evidence'][0]['C']='tampered historical message'
  with tempfile.TemporaryDirectory() as tmp:
   a=argparse.Namespace(workbook='README.md',test='data/test.csv',blind='review/blind_replies.json',out=tmp)
   with patch('import_review.sheets',return_value=ss):
    with self.assertRaisesRegex(ValueError,'Evidence'):run(a)
 def test_missing_evidence_tab_rejected(self):
  gold=read('data/test.csv');blind=json.loads(Path('review/blind_replies.json').read_text())
  ss=self.fixture(gold,blind);del ss['Evidence']
  with tempfile.TemporaryDirectory() as tmp:
   a=argparse.Namespace(workbook='README.md',test='data/test.csv',blind='review/blind_replies.json',out=tmp)
   with patch('import_review.sheets',return_value=ss):
    with self.assertRaisesRegex(ValueError,'Evidence tab'):run(a)
if __name__=='__main__':unittest.main()
