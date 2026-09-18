import React,{useEffect,useState} from 'react';

export default function RefreshClock({seconds=15,label='Refresh'}){
  const[left,setLeft]=useState(seconds);
  useEffect(()=>{
    setLeft(seconds);
    const t=setInterval(()=>setLeft(v=>v<=1?seconds:v-1),1000);
    return()=>clearInterval(t);
  },[seconds]);
  return <span className="refreshPill">{label} in {left}s</span>
}
