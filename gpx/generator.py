from lxml import etree
from smashrun import smashrun

#tree.write(destination, xml_declaration=True, encoding='UTF-8')

class GpxGenerator:
  
  def __init__(self, filename="default.gpx", smashrun_activity=None):
    self.filename = filename
    self.smashrun_activity = smashrun_activity
    
  def build(self):
    
    if self.smashrun_activity is None:
      print('[!] no smashrun activity given')
      return None
    
    
    
if __name__ == "__main__":
  print("Hello, from gpx/generator!")