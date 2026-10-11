import json, sqlite3, os, hashlib, io, csv, math, re, base64, hmac, secrets
from datetime import datetime, timezone
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

BASE=Path(__file__).parent
DATA=Path(os.environ.get('RUNLAB_DATA',str(BASE/'localdata')))
DATA.mkdir(parents=True,exist_ok=True)
DB=DATA/'runlab.sqlite3'
OPTIONS=DATA/'options.json'
def configured_password():
 try:
  return str(json.loads(OPTIONS.read_text()).get('runlab_password',''))
 except (OSError, ValueError, TypeError):
  return os.environ.get('RUNLAB_PASSWORD','')
RUNLAB_PASSWORD=configured_password()
if len(RUNLAB_PASSWORD)<12:
 raise SystemExit('RunLab: Angiv runlab_password (mindst 12 tegn) under Konfiguration før opstart.')

def conn():
 c=sqlite3.connect(DB,timeout=20)
 c.row_factory=sqlite3.Row
 c.execute('PRAGMA journal_mode=WAL')
 c.execute('CREATE TABLE IF NOT EXISTS activities (id INTEGER PRIMARY KEY, hash TEXT UNIQUE, filename TEXT, source TEXT, sport TEXT, started TEXT, duration_s REAL, distance_km REAL, avg_hr REAL, max_hr REAL, avg_speed_kmh REAL, points TEXT, imported TEXT DEFAULT CURRENT_TIMESTAMP)')
 return c

def num(v):
 try:
  n=float(v)
  return n if math.isfinite(n) else None
 except (ValueError,TypeError): return None

def timestamp(v):
 if isinstance(v,datetime): return v.isoformat()
 if isinstance(v,(int,float)): return datetime.fromtimestamp(v/1000 if v>1e11 else v,timezone.utc).isoformat()
 if v: return str(v)
 return None

def normalize_points(points):
 out=[]
 for p in points[:50000]:
  if not isinstance(p,dict): continue
  t=timestamp(p.get('time') or p.get('timestamp') or p.get('date'))
  hr=num(p.get('hr',p.get('heart_rate',p.get('heartRate',p.get('pulse')))))
  dist=num(p.get('distance_km',p.get('distanceKm')))
  if dist is None:
   meters=num(p.get('distance_m',p.get('distanceMeters')))
   if meters is not None: dist=meters/1000
  speed=num(p.get('speed_kmh',p.get('speedKmh',p.get('speed'))))
  if speed is None:
   ms=num(p.get('speed_m_s'))
   if ms is not None:speed=ms*3.6
  out.append({'time':t,'hr':hr,'distance_km':dist,'speed_kmh':speed,'lat':num(p.get('lat',p.get('latitude'))),'lon':num(p.get('lon',p.get('longitude')))})
 return out

def parse_json(raw):
 d=json.loads(raw)
 if isinstance(d,list): d={'points':d}
 if not isinstance(d,dict):raise ValueError('JSON skal indeholde et objekt eller en liste af målepunkter')
 root=d.get('activity') if isinstance(d.get('activity'),dict) else d
 pts=root.get('points',root.get('samples',root.get('records',root.get('track',[]))))
 if not isinstance(pts,list):pts=[]
 points=normalize_points(pts)
 duration=num(root.get('duration_s',root.get('durationSeconds',root.get('duration'))))
 distance=num(root.get('distance_km',root.get('distanceKm')))
 if distance is None:
  m=num(root.get('distance_m',root.get('distanceMeters')))
  if m is not None:distance=m/1000
 return {'source':'Løbebånd / JSON','sport':str(root.get('sport','running')),'started':timestamp(root.get('started',root.get('startTime',root.get('date')))),'duration_s':duration,'distance_km':distance,'points':points}

def parse_xml(raw):
 root=ET.fromstring(raw)
 is_gpx=root.tag.lower().endswith('gpx')
 points=[]
 for el in root.iter():
  tag=el.tag.split('}')[-1].lower()
  if tag not in ('trackpoint','trkpt'):continue
  p={}
  if tag=='trkpt':p={'lat':el.get('lat'),'lon':el.get('lon')}
  for node in el.iter():
   k=node.tag.split('}')[-1].lower()
   if k=='time':p['time']=node.text
   elif k in ('heartratebpm','hr'):
    if k=='hr':p['hr']=node.text
   elif k=='distancemeters':p['distance_m']=node.text
   elif k=='speed':p['speed_m_s']=node.text
  points.append(p)
  if len(points)>50000:raise ValueError('For mange målepunkter (maks. 50.000)')
 started=next((p.get('time') for p in points if p.get('time')),None)
 return {'source':'Garmin GPX' if is_gpx else 'Garmin TCX','sport':'running','started':started,'duration_s':None,'distance_km':None,'points':normalize_points(points)}

def parse_fit(raw):
 from fitparse import FitFile
 f=FitFile(io.BytesIO(raw));points=[];session={}
 for m in f.get_messages():
  if m.name=='record':
   p={x.name:x.value for x in m}
   if len(points)>=50000:raise ValueError('For mange målepunkter (maks. 50.000)')
   points.append({'time':p.get('timestamp'),'hr':p.get('heart_rate'),'distance_m':p.get('distance'),'speed_m_s':p.get('enhanced_speed',p.get('speed'))})
  elif m.name=='session':session={x.name:x.value for x in m}
 return {'source':'Garmin FIT','sport':'running','started':timestamp(session.get('start_time')),'duration_s':num(session.get('total_timer_time')),'distance_km':(num(session.get('total_distance')) or 0)/1000 or None,'points':normalize_points(points)}

def enrich(a):
 pts=a['points'];hrs=[p['hr'] for p in pts if p['hr'] is not None and 35<=p['hr']<=230]
 if not a.get('started'):a['started']=next((p['time'] for p in pts if p['time']),None)
 if a.get('distance_km') is None:
  distances=[p['distance_km'] for p in pts if p['distance_km'] is not None]
  if distances:a['distance_km']=max(distances)-min(0,distances[0])
 if a.get('duration_s') is None and len(pts)>1:
  try:
   t0=datetime.fromisoformat(pts[0]['time'].replace('Z','+00:00'));t1=datetime.fromisoformat(pts[-1]['time'].replace('Z','+00:00'))
   a['duration_s']=max(0,(t1-t0).total_seconds())
  except (TypeError,ValueError):pass
 a['avg_hr']=round(sum(hrs)/len(hrs),1) if hrs else None
 a['max_hr']=max(hrs) if hrs else None
 a['avg_speed_kmh']=round(a['distance_km']/(a['duration_s']/3600),2) if a.get('distance_km') and a.get('duration_s') else None
 if not a.get('started'):raise ValueError('Ingen startdato fundet. Angiv started i JSON eller brug en fil med tidsstempler.')
 return a

class Handler(BaseHTTPRequestHandler):
 def authorized(self):
  header=self.headers.get("Authorization","")
  if not header.startswith("Basic "):return False
  try:
   decoded=base64.b64decode(header[6:],validate=True).decode("utf-8")
   username,password=decoded.split(":",1)
   return hmac.compare_digest(username,"runlab") and hmac.compare_digest(password,RUNLAB_PASSWORD)
  except (ValueError,UnicodeError):return False
 def require_auth(self):
  if self.authorized():return False
  self.send_response(401)
  self.send_header("WWW-Authenticate",'Basic realm="RunLab", charset="UTF-8"')
  self.send_header("Cache-Control","no-store")
  self.send_header("Content-Length","0")
  self.end_headers()
  return True
 def send(self,status,obj):
  body=json.dumps(obj,ensure_ascii=False,allow_nan=False).encode()
  self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
 def do_GET(self):
  if self.require_auth():return
  path=urlparse(self.path).path
  if path=='/api/activities':
   with conn() as c: rows=c.execute('SELECT id,filename,source,sport,started,duration_s,distance_km,avg_hr,max_hr,avg_speed_kmh,imported FROM activities ORDER BY started DESC').fetchall()
   return self.send(200,{'activities':[dict(r) for r in rows]})
  if path.startswith('/api/activities/'):
   try: aid=int(path.rsplit('/',1)[-1])
   except ValueError:return self.send(400,{'error':'Ugyldigt id'})
   with conn() as c:r=c.execute('SELECT * FROM activities WHERE id=?',(aid,)).fetchone()
   return self.send(200,{'activity':dict(r)|{'points':json.loads(r['points'])}}) if r else self.send(404,{'error':'Ikke fundet'})
  if path=='/api/export':
   with conn() as c:rows=[dict(r) for r in c.execute('SELECT * FROM activities ORDER BY started')]
   for r in rows:r['points']=json.loads(r['points'])
   return self.send(200,{'version':1,'activities':rows})
  name='index.html' if path=='/' else path.lstrip('/')
  if name not in ('index.html','app.js','manifest.webmanifest','sw.js'):return self.send(404,{'error':'Ikke fundet'})
  p=BASE/'static'/name
  mime={'index.html':'text/html','app.js':'text/javascript','manifest.webmanifest':'application/manifest+json','sw.js':'text/javascript'}[name]
  b=p.read_bytes();self.send_response(200);self.send_header('Content-Type',mime+'; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_POST(self):
  if self.require_auth():return
  if self.path!='/api/import':return self.send(404,{'error':'Ikke fundet'})
  try:size=int(self.headers.get('Content-Length','0'))
  except ValueError:return self.send(400,{'error':'Ugyldig filstørrelse'})
  if size<1 or size>25*1024*1024:return self.send(413,{'error':'Filen skal være under 25 MB'})
  try:
   raw=self.rfile.read(size);name=self.headers.get('X-Filename','training')[:180]
   digest=hashlib.sha256(raw).hexdigest();ext=name.lower().rsplit('.',1)[-1]
   if ext not in ('json','tcx','gpx','fit'):return self.send(400,{'error':'Ukendt filformat'})
   a=enrich({'json':parse_json,'tcx':parse_xml,'gpx':parse_xml,'fit':parse_fit}[ext](raw))
   with conn() as c:
    try:
     c.execute('INSERT INTO activities(hash,filename,source,sport,started,duration_s,distance_km,avg_hr,max_hr,avg_speed_kmh,points) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(digest,name,a['source'],a['sport'],a['started'],a.get('duration_s'),a.get('distance_km'),a.get('avg_hr'),a.get('max_hr'),a.get('avg_speed_kmh'),json.dumps(a['points'])))
    except sqlite3.IntegrityError:return self.send(200,{'status':'duplicate','filename':name})
   return self.send(201,{'status':'imported','filename':name,'points':len(a['points'])})
  except (ValueError,KeyError,ET.ParseError,UnicodeDecodeError) as e:return self.send(400,{'error':str(e)})
  except Exception as e:
   print('Import error:',repr(e),flush=True);return self.send(400,{'error':'Kunne ikke læse filen. Kontrollér formatet.'})
 def log_message(self,fmt,*args):print('%s - %s'%(self.address_string(),fmt%args),flush=True)

if __name__=='__main__':
 conn().close();print('RunLab started on :8099',flush=True)
 ThreadingHTTPServer(('0.0.0.0',8099),Handler).serve_forever()
