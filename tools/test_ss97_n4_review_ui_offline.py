import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class N4ReviewSecurityUX(unittest.TestCase):
 def test_ui_guest_prompt_and_hidden_decision(self):
  html=(ROOT/"softsystem97/www/ss97-cyber-review.html").read_text()
  js=(ROOT/"softsystem97/public/js/ss97_cyber_review.js").read_text()
  self.assertIn('id="n4-review-panel" hidden',html)
  self.assertIn('panel.hidden=true;',js)
  self.assertIn('panel.hidden=false;',js)
  self.assertIn('if(panel.hidden)return;',js)
  self.assertIn('/login?redirect-to=',js)
  self.assertIn('/ss97-tech-os',js)
  self.assertIn('get_n4_assessments',js)
  self.assertNotIn('innerHTML',js)
if __name__=="__main__":unittest.main()
