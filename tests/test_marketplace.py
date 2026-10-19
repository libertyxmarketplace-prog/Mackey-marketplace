import os,sys,tempfile,unittest,threading,json,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import server
from http.server import ThreadingHTTPServer
class MarketplaceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();server.DATA=Path(cls.temp.name);server.UP=server.DATA/'uploads';server.UP.mkdir();server.DB=server.DATA/'marketplace.sqlite3';server.init();server.migrate();cls.http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);cls.url='http://127.0.0.1:'+str(cls.http.server_port);cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
 @classmethod
 def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.temp.cleanup()
 def call(self,path,payload=None,cookie=None):
  headers={'Content-Type':'application/json'}
  if cookie:headers['Cookie']=cookie
  req=urllib.request.Request(self.url+path,data=json.dumps(payload).encode() if payload is not None else None,headers=headers)
  try:r=urllib.request.urlopen(req)
  except urllib.error.HTTPError as e:r=e
  with r:return r.status,json.loads(r.read()),r.headers
 def test_flow(self):
  self.assertEqual(self.call('/api/health')[0],200)
  self.assertEqual(self.call('/api/listings')[1]['listings'],[])
  status,body,headers=self.call('/api/register',{'email':'test@example.com','name':'Creator','password':'secure-pass-123'});self.assertEqual(status,201)
  cookie=headers['Set-Cookie'].split(';')[0]
  self.assertEqual(self.call('/api/me',cookie=cookie)[1]['user']['name'],'Creator')
  self.assertEqual(self.call('/api/profile',{'name':'Updated'},cookie)[1]['user']['name'],'Updated')
  self.assertEqual(self.call('/api/listings',{'title':'Free livery','department':'Fire & Rescue','description':'Test asset','price':0,'filename':'asset.txt','content':'aGVsbG8=','codes':[{'label':'Front','code':'12345'}]},cookie)[0],201)
  listings=self.call('/api/listings')[1]['listings'];self.assertEqual(len(listings),1);lid=listings[0]['id'];self.assertEqual(listings[0]['department'],'Fire & Rescue')
  self.assertEqual(self.call('/api/save',{'id':lid,'saved':True},cookie)[0],200)
  self.assertEqual(self.call('/api/claim',{'id':lid},cookie)[0],200)
  self.assertEqual(len(self.call('/api/orders',cookie=cookie)[1]['orders']),1)
  self.assertEqual(self.call('/api/delete-listing',{'id':lid},cookie)[0],409)
  self.assertEqual(self.call('/api/logout',{},cookie)[0],200)
  self.assertIsNone(self.call('/api/me',cookie=cookie)[1]['user'])
  self.assertEqual(self.call('/api/save',{'id':lid,'saved':True},cookie)[0],401)
  self.assertEqual(self.call('/api/listings',{'title':'Bad','department':'Police','price':'NaN','filename':'x','content':'eA=='},cookie)[0],401)
 def test_private_files(self):
  req=urllib.request.Request(self.url+'/data/marketplace.sqlite3')
  with self.assertRaises(urllib.error.HTTPError) as ctx:urllib.request.urlopen(req)
  self.assertEqual(ctx.exception.code,404)
if __name__=='__main__':unittest.main()
