import os, json, sqlite3, hashlib, hmac, secrets, time, mimetypes, urllib.parse, urllib.request, base64
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
from http.cookies import SimpleCookie
# Local data lives outside the public pages. Never serve the data directory.
ROOT=Path(__file__).resolve().parent; DATA=ROOT/'data'; DATA.mkdir(exist_ok=True); UP=DATA/'uploads'; UP.mkdir(exist_ok=True)
DB=DATA/'marketplace.sqlite3'; SECRET=os.getenv('LX_SECRET',secrets.token_hex(32)); PORT=int(os.getenv('PORT','8000'))
def db():
 c=sqlite3.connect(DB,timeout=20);c.row_factory=sqlite3.Row;c.execute('PRAGMA journal_mode=WAL');return c
def init():
 with db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT UNIQUE,name TEXT NOT NULL,password TEXT,discord_id TEXT UNIQUE,created INTEGER);CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER,expires INTEGER);CREATE TABLE IF NOT EXISTS listings(id INTEGER PRIMARY KEY,owner INTEGER,title TEXT,department TEXT,description TEXT,price REAL,filename TEXT,original TEXT,created INTEGER);CREATE TABLE IF NOT EXISTS saved(user_id INTEGER,listing_id INTEGER,PRIMARY KEY(user_id,listing_id));CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY,user_id INTEGER,listing_id INTEGER,created INTEGER,UNIQUE(user_id,listing_id));''')
def migrate():
 with db() as c:
  cols=[x[1] for x in c.execute('PRAGMA table_info(users)')]
  if 'avatar' not in cols:c.execute('ALTER TABLE users ADD COLUMN avatar TEXT')
  cols=[x[1] for x in c.execute('PRAGMA table_info(listings)')]
  if 'codes' not in cols:c.execute("ALTER TABLE listings ADD COLUMN codes TEXT DEFAULT '[]'")
  if 'preview' not in cols:c.execute('ALTER TABLE listings ADD COLUMN preview TEXT')
def pw_hash(p,s=None):
 s=s or secrets.token_hex(16);return s+':'+hashlib.pbkdf2_hmac('sha256',p.encode(),bytes.fromhex(s),260000).hex()
def verify(p,stored):
 try:s=stored.split(':')[0];return hmac.compare_digest(pw_hash(p,s),stored)
 except:return False
def validate_codes(codes):
 if not isinstance(codes,list) or len(codes)>20:raise ValueError('Up to 20 code entries are allowed')
 clean=[]
 for item in codes:
  if not isinstance(item,dict):raise ValueError('Invalid code entry')
  label=str(item.get('label','')).strip()[:48]
  code=str(item.get('code','')).strip()
  if not label or not code or len(code)>120 or any(ord(c)<32 for c in code):raise ValueError('Each code needs a label and valid value')
  clean.append({'label':label,'code':code})
 return clean
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw):super().__init__(*a,directory=str(ROOT),**kw)
 def respond(self,status,obj,headers=None):
  raw=json.dumps(obj).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Security-Policy',"frame-ancestors 'none'")
  for k,v in (headers or {}).items():self.send_header(k,v)
  self.end_headers();self.wfile.write(raw)
 def body(self):
  n=int(self.headers.get('Content-Length','0'))
  if n>32_000_000:raise ValueError('Request exceeds 32 MB limit')
  return json.loads(self.rfile.read(n) or b'{}')
 def user(self):
  cookie=SimpleCookie()
  try:cookie.load(self.headers.get('Cookie',''))
  except:return None
  t=cookie.get('lx_session');token=t.value if t else ''
  if not token:return None
  with db() as c:return c.execute('SELECT users.id,users.name,users.avatar FROM sessions JOIN users ON users.id=sessions.user_id WHERE token_hash=? AND expires>?',(hashlib.sha256(token.encode()).hexdigest(),int(time.time()))).fetchone()
 def session(self,uid):
  token=secrets.token_urlsafe(40)
  with db() as c:c.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),uid,int(time.time())+30*86400))
  secure='; Secure' if self.headers.get('X-Forwarded-Proto')=='https' else ''
  return {'Set-Cookie':f'lx_session={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age=2592000{secure}'}
 def do_GET(self):
  path=urllib.parse.urlparse(self.path).path
  if path.startswith('/api/'):
   try:self.api_get(path)
   except Exception as e:self.respond(400,{'error':str(e)})
   return
  if path.startswith('/data/') or path.startswith('/.') or path.endswith(('.py','.sqlite3','.db','.zip','.pyc','.log','.env','.bak')):self.send_error(404);return
  return super().do_GET()
 def api_get(self,path):
  u=self.user()
  if path=='/api/me':return self.respond(200,{'user':dict(u) if u else None,'discord_enabled':bool(os.getenv('DISCORD_CLIENT_ID') and os.getenv('DISCORD_CLIENT_SECRET'))})
  if path=='/api/health':return self.respond(200,{'ok':True})
  if path=='/api/listings':
   with db() as c:rows=c.execute('SELECT l.id,l.owner,l.title,l.department,l.description,l.price,l.created,l.codes,l.preview,u.name creator FROM listings l JOIN users u ON u.id=l.owner ORDER BY l.created DESC').fetchall()
   return self.respond(200,{'listings':[dict(x) for x in rows]})
  if not u:return self.respond(401,{'error':'Sign in required'})
  with db() as c:
   if path=='/api/saved':return self.respond(200,{'ids':[x[0] for x in c.execute('SELECT listing_id FROM saved WHERE user_id=?',(u['id'],))]})
   if path=='/api/orders':return self.respond(200,{'orders':[dict(x) for x in c.execute('SELECT o.id,o.listing_id,o.created,l.title,l.original FROM orders o JOIN listings l ON l.id=o.listing_id WHERE o.user_id=? ORDER BY o.created DESC',(u['id'],))]})
   if path.startswith('/api/download/'):
    lid=int(path.rsplit('/',1)[-1]);row=c.execute('SELECT l.filename,l.original FROM listings l JOIN orders o ON o.listing_id=l.id WHERE l.id=? AND o.user_id=?',(lid,u['id'])).fetchone()
    if not row:return self.respond(403,{'error':'Asset not in your library'})
    f=UP/row['filename'];raw=f.read_bytes();name=urllib.parse.quote(row['original']);self.send_response(200);self.send_header('Content-Type','application/octet-stream');self.send_header('Content-Disposition',f"attachment; filename*=UTF-8''{name}");self.send_header('Content-Length',str(len(raw)));self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(raw);return
  self.respond(404,{'error':'Not found'})
 def do_POST(self):
  try:self.api_post(urllib.parse.urlparse(self.path).path,self.body())
  except (ValueError,KeyError,TypeError) as e:self.respond(400,{'error':str(e)})
  except sqlite3.IntegrityError:self.respond(409,{'error':'Account or item already exists'})
 def api_post(self,path,b):
  if path=='/api/register':
   email=str(b.get('email','')).strip().lower();name=str(b.get('name','')).strip();p=str(b.get('password',''))
   if '@' not in email or len(name)<2 or len(p)<8:return self.respond(400,{'error':'Enter a valid email, name and password of at least 8 characters'})
   with db() as c:uid=c.execute('INSERT INTO users(email,name,password,created) VALUES(?,?,?,?)',(email,name,pw_hash(p),int(time.time()))).lastrowid
   return self.respond(201,{'user':{'id':uid,'name':name,'avatar':None}},self.session(uid))
  if path=='/api/login':
   with db() as c:u=c.execute('SELECT * FROM users WHERE email=?',(str(b.get('email','')).lower().strip(),)).fetchone()
   if not u or not u['password'] or not verify(str(b.get('password','')),u['password']):return self.respond(401,{'error':'Incorrect email or password'})
   return self.respond(200,{'user':{'id':u['id'],'name':u['name'],'avatar':u['avatar']}},self.session(u['id']))
  u=self.user()
  if path=='/api/logout':
   token=SimpleCookie();token.load(self.headers.get('Cookie',''));t=token.get('lx_session')
   if t:
    with db() as c:c.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(t.value.encode()).hexdigest(),))
   return self.respond(200,{'ok':True},{'Set-Cookie':'lx_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0'})
  if not u:return self.respond(401,{'error':'Sign in required'})
  if path=='/api/profile':
   name=str(b.get('name','')).strip()
   if not 2<=len(name)<=32 or any(ord(ch)<32 for ch in name):return self.respond(400,{'error':'Username must be 2–32 characters'})
   avatar=b.get('avatar')
   if avatar is not None:
    if not isinstance(avatar,str) or (avatar and (len(avatar)>28000000 or not avatar.startswith(('data:image/png;base64,','data:image/jpeg;base64,','data:image/webp;base64,')))):return self.respond(400,{'error':'Use a PNG, JPEG or WebP image under 20 MB'})
    if avatar:
     try:raw=base64.b64decode(avatar.split(',',1)[1],validate=True)
     except Exception:return self.respond(400,{'error':'Invalid image'})
     if len(raw)>20*1024*1024 or not (raw.startswith(b'\x89PNG\r\n\x1a\n') or raw.startswith(b'\xff\xd8\xff') or raw.startswith(b'RIFF') and raw[8:12]==b'WEBP'):return self.respond(400,{'error':'Invalid image or file too large'})
   with db() as c:
    if avatar is None:c.execute('UPDATE users SET name=? WHERE id=?',(name,u['id']))
    else:c.execute('UPDATE users SET name=?,avatar=? WHERE id=?',(name,avatar or None,u['id']))
   return self.respond(200,{'user':{'id':u['id'],'name':name,'avatar':u['avatar'] if avatar is None else avatar or None}})
  if path=='/api/listings':
   title=str(b.get('title','')).strip();dep=str(b.get('department',''));desc=str(b.get('description','')).strip();price=float(b.get('price',0));filename=str(b.get('filename','')).strip();raw=base64.b64decode(b.get('content',''),validate=True);codes=b.get('codes',[]);codes=validate_codes(codes)
   preview=b.get('preview')
   if preview is not None:
    if not isinstance(preview,str) or len(preview)>28000000 or not preview.startswith(('data:image/png;base64,','data:image/jpeg;base64,','data:image/webp;base64,')):raise ValueError('Invalid preview image')
    image=base64.b64decode(preview.split(',',1)[1],validate=True)
    if len(image)>1000000 or not (image.startswith(b'\x89PNG\r\n\x1a\n') or image.startswith(b'\xff\xd8\xff') or image.startswith(b'RIFF') and image[8:12]==b'WEBP'):raise ValueError('Invalid preview image')
   if not 3<=len(title)<=120 or len(desc)>10000 or not __import__('math').isfinite(price) or dep not in ('Police','Sheriff','Fire & Rescue','DOT','Uniforms') or not 0<=price<=10000 or not filename or not raw or len(raw)>8_000_000:raise ValueError('Valid title, department and a file under 8 MB are required')
   safe=Path(filename).name[:120];stored=secrets.token_hex(20);(UP/stored).write_bytes(raw)
   with db() as c:lid=c.execute('INSERT INTO listings(owner,title,department,description,price,filename,original,created,codes,preview) VALUES(?,?,?,?,?,?,?,?,?,?)',(u['id'],title,dep,desc,price,stored,safe,int(time.time()),json.dumps(codes),preview)).lastrowid
   return self.respond(201,{'id':lid})
  if path=='/api/save':
   lid=int(b['id']);
   with db() as c:
    if b.get('saved'):
     if not c.execute('SELECT 1 FROM listings WHERE id=?',(lid,)).fetchone():return self.respond(404,{'error':'Listing not found'})
     c.execute('INSERT OR IGNORE INTO saved VALUES(?,?)',(u['id'],lid))
    else:c.execute('DELETE FROM saved WHERE user_id=? AND listing_id=?',(u['id'],lid))
   return self.respond(200,{'ok':True})
  if path=='/api/delete-listing':
   lid=int(b['id'])
   with db() as c:
    row=c.execute('SELECT filename FROM listings WHERE id=? AND owner=?',(lid,u['id'])).fetchone()
    if not row:return self.respond(404,{'error':'Your listing was not found'})
    claimed=c.execute('SELECT 1 FROM orders WHERE listing_id=? LIMIT 1',(lid,)).fetchone()
    if claimed:return self.respond(409,{'error':'This listing has been claimed. Keep it available for existing downloads.'})
    c.execute('DELETE FROM saved WHERE listing_id=?',(lid,))
    c.execute('DELETE FROM listings WHERE id=? AND owner=?',(lid,u['id']))
   (UP/row['filename']).unlink(missing_ok=True)
   return self.respond(200,{'ok':True})
  if path=='/api/claim':
   lid=int(b['id'])
   with db() as c:
    l=c.execute('SELECT price FROM listings WHERE id=?',(lid,)).fetchone()
    if not l:return self.respond(404,{'error':'Listing not found'})
    if l['price']!=0:return self.respond(402,{'error':'Paid checkout is not configured. No payment was taken.'})
    c.execute('INSERT OR IGNORE INTO orders(user_id,listing_id,created) VALUES(?,?,?)',(u['id'],lid,int(time.time())))
   return self.respond(200,{'ok':True})
  self.respond(404,{'error':'Not found'})
if __name__=='__main__':
 init();migrate();print(f'LX Marketplace: http://localhost:{PORT}');ThreadingHTTPServer(('127.0.0.1',PORT),Handler).serve_forever()
