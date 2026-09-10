import json,sys,unittest
from pathlib import Path
sys.path.insert(0,'src')
from import_review import sheets
from support import read
from workbook import build, write_xlsx

class WorkbookTests(unittest.TestCase):
 def setUp(self):
  self.test=read('data/test.csv')
  self.blind=json.loads(Path('review/blind_replies.json').read_text())
 def test_packaged_workbook_is_blank_and_complete(self):
  path=Path('review/human-review.xlsx')
  self.assertTrue(path.exists())
  ss=sheets(path)
  original={r['id']:r for r in self.test}
  gold=[r for r in ss['Gold labels'] if r.get('A') in original]
  self.assertEqual(len(gold),200)
  self.assertEqual([r['A'] for r in gold],[r['id'] for r in self.test])
  for r in gold:
   self.assertEqual(r['B'],original[r['A']]['message'])
   self.assertFalse(r.get('C'))
   self.assertFalse(r.get('D'))
   self.assertFalse(r.get('E'))
   self.assertFalse(r.get('F'))
  blind={r['review_id']:r for r in self.blind}
  ratings=[r for r in ss['Reply ratings'] if r.get('A') in blind]
  self.assertEqual(len(ratings),60)
  for r in ratings:
   orig=blind[r['A']]
   self.assertEqual(r['B'],orig['message'])
   self.assertEqual(r['C'],orig['reply'])
   self.assertEqual(r['D'],','.join(e['id'] for e in orig['evidence']))
   self.assertFalse(r.get('E'))
   self.assertFalse(r.get('F'))
   self.assertFalse(r.get('G'))
   self.assertFalse(r.get('H'))
  evidence=[r for r in ss['Evidence'] if r.get('A') in blind]
  expected=sum(len(r['evidence']) for r in self.blind)
  self.assertEqual(len(evidence),expected)
  grouped={}
  for r in evidence:
   grouped.setdefault(r['A'],[]).append(r['B'])
  for review_id,orig in blind.items():
   self.assertEqual(grouped[review_id],[e['id'] for e in orig['evidence']])
 def test_writer_round_trip_does_not_copy_suggestions(self):
  import tempfile
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'blank.xlsx'
   write_xlsx(path,build(self.test,self.blind))
   ss=sheets(path)
   self.assertEqual(set(ss),{'Guide','Gold labels','Reply ratings','Evidence'})
   gold=[r for r in ss['Gold labels'] if r.get('A')]
   self.assertEqual(gold[0]['A'],'id')
   labelled=[r for r in gold[1:] if r.get('C') or r.get('D')]
   self.assertEqual(labelled,[])
 def test_generator_refuses_overwrite(self):
  import tempfile,argparse
  from workbook import run
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'human-review.xlsx'
   path.write_bytes(b'existing')
   a=argparse.Namespace(test='data/test.csv',blind='review/blind_replies.json',output=str(path),force=False)
   with self.assertRaisesRegex(ValueError,'overwrite'):
    run(a)

if __name__=='__main__':
 unittest.main()
