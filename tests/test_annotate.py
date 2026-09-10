import io,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,'src')
from annotate import main, load_mapping_blocked, complete_gold
from support import read, write

class AnnotateTests(unittest.TestCase):
 def test_resume_saves_and_skips_complete_rows(self):
  test=read('data/test.csv')[:2]
  with tempfile.TemporaryDirectory() as tmp:
   src=Path(tmp)/'test.csv'; write(src,test)
   out=Path(tmp)/'gold.csv'
   fed=io.StringIO('delivery\n1\nNeeds account lookup\nq\n')
   buf=io.StringIO()
   main(['gold','--name','CB','--test',str(src),'--out',str(out)], io_in=fed, io_out=buf)
   rows=read(out)
   self.assertEqual(rows[0]['intent'],'delivery')
   self.assertEqual(rows[0]['label_source'],'human')
   self.assertEqual(rows[1]['intent'],'')
   fed=io.StringIO('other\n1\nUnclear request\n')
   buf=io.StringIO()
   main(['gold','--name','CB','--test',str(src),'--out',str(out)], io_in=fed, io_out=buf)
   rows=read(out)
   self.assertTrue(complete_gold(rows[0]))
   self.assertEqual(rows[1]['intent'],'other')
   self.assertNotIn('review_mapping', buf.getvalue())
 def test_numeric_intent_and_quit(self):
  test=read('data/test.csv')[:1]
  with tempfile.TemporaryDirectory() as tmp:
   src=Path(tmp)/'test.csv'; write(src,test)
   out=Path(tmp)/'gold.csv'
   fed=io.StringIO('1\n1\nLate parcel needs tracking lookup\n')
   main(['gold','--name','CB','--test',str(src),'--out',str(out)], io_in=fed, io_out=io.StringIO())
   self.assertEqual(read(out)[0]['intent'],'delivery')
 def test_rejects_synthetic_name(self):
  with self.assertRaisesRegex(ValueError,'synthetic'):
   main(['gold','--name','SYNTHETIC','--test','data/test.csv','--out','/tmp/unused.csv'], io_in=io.StringIO(), io_out=io.StringIO())
 def test_rating_does_not_load_mapping(self):
  blind=json.loads(Path('review/blind_replies.json').read_text())[:1]
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'blind.json'
   path.write_text(json.dumps(blind),encoding='utf-8')
   out=Path(tmp)/'ratings.csv'
   fed=io.StringIO('4\n2\n5\n4\nGeneric acknowledgement, safe but not specific\n')
   buf=io.StringIO()
   main(['rates','--name','CB','--blind',str(path),'--out',str(out),'--gold',str(Path(tmp)/'missing.csv')], io_in=fed, io_out=buf)
   self.assertEqual(read(out)[0]['grounding'],'4')
   self.assertIn('Model identities are hidden', buf.getvalue())
   self.assertNotIn('review_mapping', buf.getvalue())
 def test_mapping_helper_is_blocked(self):
  with self.assertRaisesRegex(RuntimeError,'review_mapping'):
   load_mapping_blocked()

if __name__=='__main__':
 unittest.main()
