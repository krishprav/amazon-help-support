import sys, unittest
sys.path.insert(0,'src')
from support import *
class Tests(unittest.TestCase):
 def test_no_auto_for_refund(self):
  row={'id':'1','message':'refund my order','intent':'refund_return','historical_reply':'We refunded you'}
  p=predict(row,'agent',Retriever([row]),'other',.1)
  self.assertEqual(p['escalate'],1); self.assertNotIn('refunded',p['reply'])
 def test_no_evidence(self):
  row={'id':'1','message':'delivery late','intent':'delivery','historical_reply':'Hello'}
  p=predict({'message':'zqxvv'},'agent',Retriever([row]),'other',.65)
  self.assertEqual(p['escalate'],1); self.assertEqual(p['similarity'],0)
 def test_missing_labels(self):
  with self.assertRaises(ValueError): validate([{'intent':'','escalate':'','annotator':'','label_reason':''}])
 def test_abstention_not_perfect_safety(self):
  result=metrics([{'intent':'other','escalate':'1'}],[{'intent':'other','escalate':1}])
  self.assertIsNone(result['unsafe_auto_rate']); self.assertEqual(result['auto_coverage'],0)
 def test_redaction(self):
  self.assertNotIn('123456',clean('@bob order 123456 https://example.org'))
if __name__=='__main__': unittest.main()
