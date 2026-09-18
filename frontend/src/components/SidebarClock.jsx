import React,{useEffect,useMemo,useState} from 'react';

const formatET=(date,showSeconds)=>new Intl.DateTimeFormat('en-US',{
  timeZone:'America/New_York',
  hour:'numeric',
  minute:'2-digit',
  second:showSeconds?'2-digit':undefined,
  hour12:true,
}).format(date);

const dateET=date=>new Intl.DateTimeFormat('en-US',{
  timeZone:'America/New_York',
  weekday:'short',
  month:'short',
  day:'numeric',
}).format(date);

export default function SidebarClock({showSeconds=false}){
  const[now,setNow]=useState(new Date());
  useEffect(()=>{const t=setInterval(()=>setNow(new Date()),1000);return()=>clearInterval(t)},[]);
  return <div className="babySidebarClock">
    <div className="babySidebarClockTime">{formatET(now,showSeconds)}</div>
    <div className="babySidebarClockMeta">{dateET(now)} · ET</div>
  </div>
}
