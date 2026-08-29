import os, csv, time
from functools import wraps
from collections import defaultdict
import requests
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY","change-me")

BASE = os.getenv("KOBO_BASE_URL","https://kf.kobotoolbox.org").rstrip("/")
TOKEN = os.getenv("KOBO_API_TOKEN","").strip()
CACHE_SECONDS = int(os.getenv("CACHE_SECONDS","60"))
AUTH_USERNAME = os.getenv("AUTH_USERNAME","admin")
AUTH_PASSWORD_HASH = os.getenv("AUTH_PASSWORD_HASH","").strip()

PRESIDENT_CANDIDATE_NAMES = [
 x.strip() for x in os.getenv(
  "PRESIDENT_CANDIDATE_NAMES",
  os.getenv(
   "CANDIDATE_NAMES",
   "Candidate 1,Candidate 2,Candidate 3,Candidate 4,Candidate 5,"
   "Candidate 6,Candidate 7,Candidate 8,Candidate 9,Candidate 10"
  )
 ).split(",")
]
while len(PRESIDENT_CANDIDATE_NAMES) < 10:
 PRESIDENT_CANDIDATE_NAMES.append(f"Candidate {len(PRESIDENT_CANDIDATE_NAMES)+1}")
PRESIDENT_CANDIDATE_NAMES = PRESIDENT_CANDIDATE_NAMES[:10]

ELECTIONS = {
 "PRESIDENT": {
  "uid": os.getenv("PRESIDENT_ASSET_UID","agzzJrY3u2U33csFtFGhcu").strip(),
  "group":"presidential_votes", "slots":10, "title":"President", "minimum_scope":"national"
 },
 "GOVERNOR": {
  "uid": os.getenv("GOVERNOR_ASSET_UID","aWKtgxrQtbPpDHqjYK7fqW").strip(),
  "group":"gubernatorial_votes", "slots":15, "title":"Governor", "minimum_scope":"county"
 },
 "SENATOR": {
  "uid": os.getenv("SENATOR_ASSET_UID","avEBET9b6ECZuESQhGVMzz").strip(),
  "group":"senatorial_votes", "slots":15, "title":"Senator", "minimum_scope":"county"
 },
 "WOMAN REP": {
  "uid": os.getenv("WOMAN_REP_ASSET_UID","axWEJc6ppQajbqg9Z2segz").strip(),
  "group":"woman_rep_votes", "slots":15, "title":"Woman Rep", "minimum_scope":"county"
 },
 "MNA": {
  "uid": os.getenv("MNA_ASSET_UID","a3VF993pfwxTwxnxiocTe7").strip(),
  "group":"national_assembly_votes", "slots":20, "title":"MNA", "minimum_scope":"constituency"
 },
 "MCA": {
  "uid": os.getenv("MCA_ASSET_UID","attsMRdXB3jHY3HZG39vMb").strip(),
  "group":"county_assembly_votes", "slots":30, "title":"MCA", "minimum_scope":"ward"
 },
}

http = requests.Session()
if TOKEN:
    http.headers.update({"Authorization":f"Token {TOKEN}"})

_cache={"at":0,"elections":{},"hierarchy":None,"errors":{}}

def auth(fn):
 @wraps(fn)
 def w(*a,**k):
  if not session.get("ok"):
   return redirect(url_for("login"))
  return fn(*a,**k)
 return w

@app.route("/login",methods=["GET","POST"])
def login():
 error=""
 if request.method=="POST":
  ok=False
  try:
   ok=(request.form.get("username","")==AUTH_USERNAME and AUTH_PASSWORD_HASH
       and check_password_hash(AUTH_PASSWORD_HASH,request.form.get("password","")))
  except Exception:
   ok=False
  if ok:
   session["ok"]=True
   return redirect(url_for("dashboard"))
  error="Invalid username or password."
 return render_template("login.html",error=error)

@app.get("/logout")
def logout():
 session.clear()
 return redirect(url_for("login"))

def norm(x):
 return " ".join(str(x or "").strip().lower().replace("_"," ").replace("-"," ").split())

def label(x):
 return str(x or "").strip().replace("_"," ").replace("-"," ").title()

def val(row,path,default=""):
 if path in row:
  return row.get(path,default)
 cur=row
 for p in path.split("/"):
  if not isinstance(cur,dict):
   return default
  cur=cur.get(p)
 return default if cur is None else cur

def first(row,*paths):
 for p in paths:
  v=val(row,p,"")
  if str(v or "").strip():
   return str(v).strip()
 return ""

def nint(v):
 try:
  return int(float(str(v or "0").replace(",","").strip()))
 except Exception:
  return 0

def paged(url):
 out=[]
 while url:
  r=http.get(url,timeout=75)
  r.raise_for_status()
  data=r.json()
  if isinstance(data,list):
   out.extend(data); break
  out.extend(data.get("results",[]))
  url=data.get("next")
 return out

def geo(row):
 return {
  "county": first(row,"electorals_units/selected_county","electoral_units/selected_county"),
  "constituency": first(row,"electorals_units/selected_constituency","electoral_units/selected_constituency"),
  "ward": first(row,"electorals_units/selected_ward","electoral_units/selected_ward"),
  "poll_station": first(row,"electorals_units/selected_poll_station","electoral_units/selected_poll_station"),
  "stream": first(row,"electorals_units/selected_stream","electoral_units/selected_stream"),
 }

def full_geo_key(g):
 return tuple(norm(g[k]) for k in ("county","constituency","ward","poll_station","stream"))

def submitted_at(row):
 return str(row.get("_submission_time") or row.get("_submitted_by") or row.get("_id") or "")

def dedupe_latest(rows):
 latest={}
 for r in rows:
  g=geo(r)
  k=full_geo_key(g)
  if not any(k):
   k=("submission",str(r.get("_id","")))
  old=latest.get(k)
  if old is None or submitted_at(r)>=submitted_at(old):
   latest[k]=r
 return list(latest.values())

def hierarchy_rows():
 if _cache["hierarchy"] is not None:
  return _cache["hierarchy"]
 path=os.path.join(os.path.dirname(__file__),"county_main.csv")
 with open(path,"r",encoding="utf-8-sig",errors="replace",newline="") as f:
  rows=list(csv.DictReader(f))
 _cache["hierarchy"]=rows
 return rows

def hierarchy_maps():
 rows=hierarchy_rows()
 counties={norm(r.get("name")):r for r in rows if r.get("list_name")=="county"}
 constituencies={norm(r.get("name")):r for r in rows if r.get("list_name")=="constituency"}
 wards={norm(r.get("name")):r for r in rows if r.get("list_name")=="ward"}
 stations={norm(r.get("name")):r for r in rows if r.get("list_name")=="poll_station"}
 return rows,counties,constituencies,wards,stations

def stream_universe():
 rows,counties,constituencies,wards,stations=hierarchy_maps()
 out=[]
 for r in rows:
  if r.get("list_name")!="poll_station_stream":
   continue
  ps=stations.get(norm(r.get("poll_station_key")),{})
  wd=wards.get(norm(ps.get("ward_key")),{})
  co=constituencies.get(norm(wd.get("constituency_key")),{})
  cy=counties.get(norm(co.get("county_key")),{})
  out.append({
   "county":str(cy.get("name") or co.get("county_key") or "").strip(),
   "county_label":str(cy.get("label") or label(cy.get("name") or co.get("county_key"))),
   "constituency":str(co.get("name") or wd.get("constituency_key") or "").strip(),
   "constituency_label":str(co.get("label") or label(co.get("name") or wd.get("constituency_key"))),
   "ward":str(wd.get("name") or ps.get("ward_key") or "").strip(),
   "ward_label":str(wd.get("label") or label(wd.get("name") or ps.get("ward_key"))),
   "poll_station":str(ps.get("name") or r.get("poll_station_key") or "").strip(),
   "poll_station_label":str(ps.get("label") or label(ps.get("name") or r.get("poll_station_key"))),
   "stream":str(r.get("name") or "").strip(),
   "stream_label":str(r.get("label") or label(r.get("name"))),
  })
 return out

def fetch_all(force=False):
 now=time.time()
 if not force and _cache["elections"] and now-_cache["at"]<CACHE_SECONDS:
  return
 data={}; errors={}
 for key,cfg in ELECTIONS.items():
  try:
   rows=paged(f"{BASE}/api/v2/assets/{cfg['uid']}/data/")
   data[key]=dedupe_latest(rows)
  except Exception as ex:
   data[key]=[]
   errors[key]=str(ex)
 _cache["elections"]=data
 _cache["errors"]=errors
 _cache["at"]=now

def in_scope(g,county="",constituency="",ward="",poll_station="",stream=""):
 return ((not county or norm(g["county"])==norm(county))
  and (not constituency or norm(g["constituency"])==norm(constituency))
  and (not ward or norm(g["ward"])==norm(ward))
  and (not poll_station or norm(g["poll_station"])==norm(poll_station))
  and (not stream or norm(g["stream"])==norm(stream)))

def expected_streams(county="",constituency="",ward="",poll_station="",stream=""):
 return [x for x in stream_universe()
  if (not county or norm(x["county"])==norm(county))
  and (not constituency or norm(x["constituency"])==norm(constituency))
  and (not ward or norm(x["ward"])==norm(ward))
  and (not poll_station or norm(x["poll_station"])==norm(poll_station))
  and (not stream or norm(x["stream"])==norm(stream))]

def scope_allowed(election,county,constituency,ward):
 minimum=ELECTIONS[election]["minimum_scope"]
 if minimum=="national": return True
 if minimum=="county": return bool(county)
 if minimum=="constituency": return bool(constituency)
 if minimum=="ward": return bool(ward)
 return True

def candidate_totals(election,county="",constituency="",ward="",poll_station="",stream=""):
 fetch_all()
 cfg=ELECTIONS[election]
 if not scope_allowed(election,county,constituency,ward):
  return {"available":False,"reason":cfg["minimum_scope"],"ranking":[]}

 rows=[]
 for r in _cache["elections"].get(election,[]):
  if in_scope(geo(r),county,constituency,ward,poll_station,stream):
   rows.append(r)

 # Tally by candidate SLOT first. Some Kobo calculated candidate-name fields
 # are not saved in submission exports, especially in the Presidential form.
 # The old V1/V2 logic skipped the votes whenever the candidate name was blank.
 slot_totals=[0]*cfg["slots"]
 slot_names=[""]*cfg["slots"]

 for r in rows:
  for i in range(1,cfg["slots"]+1):
   slot_totals[i-1]+=nint(val(r,f"{cfg['group']}/candidate{i}_votes",0))
   submitted_name=first(r,f"{cfg['group']}/candidate{i}")
   if submitted_name and not slot_names[i-1]:
    slot_names[i-1]=submitted_name

 # President uses the configured candidate list when Kobo does not export the
 # calculated candidate-name fields. Other contests retain submitted names,
 # with a safe slot label fallback instead of silently dropping valid votes.
 if election=="PRESIDENT":
  for i in range(cfg["slots"]):
   if not slot_names[i]:
    slot_names[i]=PRESIDENT_CANDIDATE_NAMES[i]
 else:
  for i in range(cfg["slots"]):
   if not slot_names[i] and slot_totals[i]:
    slot_names[i]=f"Candidate {i+1}"

 ranking=[
  {"candidate":slot_names[i] or f"Candidate {i+1}","votes":slot_totals[i]}
  for i in range(cfg["slots"])
  if slot_totals[i] or slot_names[i]
 ]
 ranking.sort(key=lambda x:(-x["votes"],norm(x["candidate"])))

 # reporting percentage uses unique streams reported for this contest
 reported={full_geo_key(geo(r)) for r in rows if any(full_geo_key(geo(r)))}
 exp={full_geo_key(x) for x in expected_streams(county,constituency,ward,poll_station,stream)}
 report_pct=round(len(reported & exp)/len(exp)*100,1) if exp else 0
 return {
  "available":True,
  "ranking":ranking,
  "reported_streams":len(reported & exp) if exp else len(reported),
  "expected_streams":len(exp),
  "reporting_percent":report_pct,
  "complete":bool(exp) and len(reported & exp)>=len(exp)
 }

def leader_card(election,county="",constituency="",ward="",poll_station="",stream=""):
 r=candidate_totals(election,county,constituency,ward,poll_station,stream)
 cfg=ELECTIONS[election]
 if not r["available"]:
  return {"election":election,"title":cfg["title"],"available":False,"minimum_scope":r["reason"]}
 ranking=r["ranking"]
 leader=ranking[0] if ranking else None
 runner=ranking[1] if len(ranking)>1 else None
 margin=(leader["votes"]-runner["votes"]) if leader and runner else (leader["votes"] if leader else 0)
 return {
  "election":election,"title":cfg["title"],"available":True,
  "leader":leader,"runner_up":runner,"margin":margin,
  "leader_label":"Winner" if r["complete"] else "Leading",
  "reported_streams":r["reported_streams"],
  "expected_streams":r["expected_streams"],
  "reporting_percent":r["reporting_percent"],
  "complete":r["complete"],
  "ranking":ranking[:10],
 }

@app.get("/")
def index():
 if session.get("ok"):
  return redirect(url_for("dashboard"))
 return redirect(url_for("login"))

@app.get("/dashboard")
@auth
def dashboard():
 return render_template("index.html")

@app.get("/api/filters")
@auth
def filters():
 county=request.args.get("county","")
 constituency=request.args.get("constituency","")
 ward=request.args.get("ward","")
 poll_station=request.args.get("poll_station","")
 rows=stream_universe()
 def uniq(value,label_key,pred):
  vals={(x[value],x[label_key]) for x in rows if x[value] and pred(x)}
  return [{"value":v,"label":l} for v,l in sorted(vals,key=lambda z:z[1])]
 return jsonify(
  counties=uniq("county","county_label",lambda x:True),
  constituencies=uniq("constituency","constituency_label",
   lambda x:not county or norm(x["county"])==norm(county)),
  wards=uniq("ward","ward_label",
   lambda x:(not county or norm(x["county"])==norm(county))
    and (not constituency or norm(x["constituency"])==norm(constituency))),
  poll_stations=uniq("poll_station","poll_station_label",
   lambda x:(not county or norm(x["county"])==norm(county))
    and (not constituency or norm(x["constituency"])==norm(constituency))
    and (not ward or norm(x["ward"])==norm(ward))),
  streams=uniq("stream","stream_label",
   lambda x:(not county or norm(x["county"])==norm(county))
    and (not constituency or norm(x["constituency"])==norm(constituency))
    and (not ward or norm(x["ward"])==norm(ward))
    and (not poll_station or norm(x["poll_station"])==norm(poll_station)))
 )

@app.get("/api/leaders")
@auth
def leaders():
 county=request.args.get("county","")
 constituency=request.args.get("constituency","")
 ward=request.args.get("ward","")
 poll_station=request.args.get("poll_station","")
 stream=request.args.get("stream","")
 cards=[leader_card(e,county,constituency,ward,poll_station,stream) for e in ELECTIONS]
 return jsonify(cards=cards,errors=_cache["errors"])

@app.get("/api/board")
@auth
def board():
 """
 Cross-area winners/leader board:
 - President: one national/current filtered scope row
 - Governor/Senator/Woman Rep: one row per county
 - MNA: one row per constituency
 - MCA: one row per ward
 """
 fetch_all()
 election=request.args.get("election","PRESIDENT")
 county=request.args.get("county","")
 constituency=request.args.get("constituency","")
 ward=request.args.get("ward","")
 rows=[]

 if election=="PRESIDENT":
  scopes=[("",county,constituency,ward)]
 elif election in ("GOVERNOR","SENATOR","WOMAN REP"):
  counties=sorted({x["county"] for x in stream_universe() if x["county"] and
   (not county or norm(x["county"])==norm(county))})
  scopes=[(c,c,"","") for c in counties]
 elif election=="MNA":
  vals=sorted({(x["county"],x["constituency"]) for x in stream_universe()
   if x["constituency"] and (not county or norm(x["county"])==norm(county))
   and (not constituency or norm(x["constituency"])==norm(constituency))})
  scopes=[(f"{label(co)} / {label(cn)}",co,cn,"") for co,cn in vals]
 else:
  vals=sorted({(x["county"],x["constituency"],x["ward"]) for x in stream_universe()
   if x["ward"] and (not county or norm(x["county"])==norm(county))
   and (not constituency or norm(x["constituency"])==norm(constituency))
   and (not ward or norm(x["ward"])==norm(ward))})
  scopes=[(f"{label(wd)} / {label(cn)}",co,cn,wd) for co,cn,wd in vals]

 for display_scope,co,cn,wd in scopes:
  if election=="PRESIDENT":
   card=leader_card(election,county,constituency,ward)
   scope_name="National" if not county else "Selected Locality"
  elif election in ("GOVERNOR","SENATOR","WOMAN REP"):
   card=leader_card(election,co)
   scope_name=label(co)
  elif election=="MNA":
   card=leader_card(election,co,cn)
   scope_name=display_scope
  else:
   card=leader_card(election,co,cn,wd)
   scope_name=display_scope

  if card.get("available") and card.get("leader"):
   rows.append({
    "scope":scope_name,
    "leader":card["leader"],
    "runner_up":card["runner_up"],
    "margin":card["margin"],
    "leader_label":card["leader_label"],
    "reporting_percent":card["reporting_percent"],
    "reported_streams":card["reported_streams"],
    "expected_streams":card["expected_streams"],
   })
 return jsonify(election=election,title=ELECTIONS[election]["title"],rows=rows)

@app.post("/api/refresh")
@auth
def refresh():
 _cache["at"]=0; _cache["elections"]={}; _cache["errors"]={}
 fetch_all(force=True)
 return jsonify(ok=True)

@app.errorhandler(404)
def not_found(error):
 # If an authenticated user lands on an obsolete or mistyped dashboard path,
 # return them to the main dashboard rather than a bare "Not Found" page.
 if session.get("ok"):
  return redirect(url_for("dashboard"))
 return redirect(url_for("login"))

if __name__=="__main__":
 app.run(host="0.0.0.0",port=int(os.getenv("PORT","5000")))
