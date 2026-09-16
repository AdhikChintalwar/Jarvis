import React,{useState} from 'react';
export default function GlossaryTerm({term,glossary,children}){const [open,setOpen]=useState(false);const g=glossary?.[term];if(!g)return children||term;return <span className="term" onClick={()=>setOpen(!open)}>{children||term}{open&&<span className="tooltip"><b>{term} — {g.name}</b><span>{g.description}</span></span>}</span>}
