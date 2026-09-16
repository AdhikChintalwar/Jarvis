from __future__ import annotations
from datetime import datetime,timezone
from .common import stage
MATERIAL=['earnings','guidance','offering','merger','acquisition','fda','bankruptcy','buyback','dividend','lawsuit','contract','management','sec']
def classify(text):
 t=text.lower(); hits=[x for x in MATERIAL if x in t]
 return hits[0].upper() if hits else 'GENERAL'
def build_events(symbol,news=None,research=None):
 out=[]
 for n in news or []:
  title=n.get('headline') or n.get('title') or ''
  out.append({'headline':title,'source':n.get('source') or n.get('provider') or 'UNKNOWN','published_at':n.get('created_at') or n.get('published_at'),'url':n.get('url'),'event_type':classify(title),'authority':'SECONDARY_NEWS','confidence':'MEDIUM','causality':'NOT_ESTABLISHED'})
 sec=next((s for s in (research or {}).get('stages',[]) if s.get('id')=='sec'),None)
 warnings=[] if out else ['No current news evidence supplied; news remains UNKNOWN rather than neutral/bearish.']
 d=stage('events_v103','V10.3 News, Catalyst & Event Intelligence',[],status='PASS' if out else 'UNKNOWN',summary='Structured event evidence; headlines do not establish price causality.',warnings=warnings)
 d['events']=out[:50]; d['production_sec_stage']=sec or {}; return d
