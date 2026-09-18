import React,{useMemo,useState} from 'react';
import guide from '../docs/BABY_GUIDE.md?raw';
import pipeline from '../docs/PIPELINE_LOGIC.md?raw';
import glossary from '../docs/GLOSSARY.md?raw';
import sources from '../docs/DATA_SOURCES.md?raw';
import safety from '../docs/SAFETY_AND_AUTHORITY.md?raw';
import architecture from '../docs/SYSTEM_ARCHITECTURE.md?raw';
import changelog from '../docs/CHANGELOG.md?raw';
import decisionRules from '../docs/DECISION_RULES.md?raw';
import troubleshooting from '../docs/TROUBLESHOOTING.md?raw';

const docs=[
  ['guide','Baby Guide','Every screen, section and button',guide],
  ['pipeline','Pipeline Logic','How each research stage gets data and defines results',pipeline],
  ['glossary','Glossary','Abbreviations, statuses and Baby terms in simple language',glossary],
  ['sources','Data Sources','Where information comes from and how it is used',sources],
  ['safety','Safety & Authority','What Baby and AI can and cannot do',safety],
  ['architecture','Architecture','How the system fits together',architecture],
  ['rules','Decision Rules','Trade-plan authority and user quantity',decisionRules],
  ['troubleshooting','Troubleshooting','Common Baby operational questions',troubleshooting],
  ['changelog',"What's New",'Version history and important changes',changelog],
];

function Inline({text}){
  const parts=String(text).split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
  return <>{parts.map((p,i)=>{
    if(p.startsWith('`')&&p.endsWith('`'))return <code key={i}>{p.slice(1,-1)}</code>;
    if(p.startsWith('**')&&p.endsWith('**'))return <strong key={i}>{p.slice(2,-2)}</strong>;
    return <React.Fragment key={i}>{p}</React.Fragment>;
  })}</>
}

function Markdown({text}){
  const lines=String(text||'').split('\n');
  const out=[];let code=[];let inCode=false;let bullets=[];
  const flushBullets=()=>{if(bullets.length){out.push(<ul key={`ul-${out.length}`}>{bullets.map((x,i)=><li key={i}><Inline text={x}/></li>)}</ul>);bullets=[]}};
  const flushCode=()=>{if(code.length){out.push(<pre key={`pre-${out.length}`}><code>{code.join('\n')}</code></pre>);code=[]}};
  lines.forEach((line,idx)=>{
    if(line.trim().startsWith('```')){flushBullets();if(inCode){flushCode();inCode=false}else inCode=true;return}
    if(inCode){code.push(line);return}
    if(line.startsWith('- ')){bullets.push(line.slice(2));return}
    flushBullets();
    if(line.startsWith('### '))out.push(<h3 key={idx}><Inline text={line.slice(4)}/></h3>);
    else if(line.startsWith('## '))out.push(<h2 key={idx}><Inline text={line.slice(3)}/></h2>);
    else if(line.startsWith('# '))out.push(<h1 key={idx}><Inline text={line.slice(2)}/></h1>);
    else if(line.trim()==='---')out.push(<hr key={idx}/>);
    else if(line.trim())out.push(<p key={idx}><Inline text={line}/></p>);
  });
  flushBullets();flushCode();
  return <div className="docsMarkdown">{out}</div>
}

export default function Documentation(){
  const[active,setActive]=useState('guide');const[docsSearch,setDocsSearch]=useState('');
  const doc=useMemo(()=>docs.find(x=>x[0]===active)||docs[0],[active]);
  return <main className="screenPage docsPage">
    <section className="pageExplain compactExplain">
      <div>
        <span className="pageKicker">DOCUMENTATION</span>
        <h1>How Baby works</h1>
        <p>Plain-language product documentation stored with the code so the explanation can evolve with the system.</p>
      </div>
    </section>
    <div className="docsSearchBar"><input value={docsSearch} onChange={e=>setDocsSearch(e.target.value)} placeholder="Search documentation..."/></div><div className="docsLayout">
      <aside className="docsNav">
        {docs.filter(([,title,desc,body])=>!docsSearch||`${title} ${desc} ${body}`.toLowerCase().includes(docsSearch.toLowerCase())).map(([id,title,desc])=><button key={id} className={active===id?'active':''} onClick={()=>setActive(id)}>
          <b>{title}</b><small>{desc}</small>
        </button>)}
      </aside>
      <section className="docsContent">
        <div className="docsContentHead"><span className="eyebrow">BABY V15.3 DOCUMENTATION</span><h2>{doc[1]}</h2><p>{doc[2]}</p></div>
        <Markdown text={doc[3]}/>
      </section>
    </div>
  </main>
}
