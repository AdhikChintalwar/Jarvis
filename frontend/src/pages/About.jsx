import React from 'react';
import BabyLogo from '../components/BabyLogo';

export default function About(){
  return <main className="screenPage aboutPage">
    <section className="aboutHero">
      <BabyLogo/>
      <div>
        <span className="pageKicker">ABOUT BABY</span>
        <h1>Investment research and monitoring</h1>
        <p>Baby organizes market evidence, deterministic research, trade-plan monitoring and PAPER-broker review while keeping execution authority outside the AI layer.</p>
      </div>
    </section>

    <section className="aboutFlow">
      {['Discovery','Research','Validation','Trade Plan','Monitoring','Human Review','Alpaca PAPER'].map((x,i)=><React.Fragment key={x}>
        <div className="aboutFlowNode"><small>{String(i+1).padStart(2,'0')}</small><b>{x}</b></div>
        {i<6&&<span className="aboutArrow">→</span>}
      </React.Fragment>)}
    </section>

    <div className="aboutGrid">
      <section className="aboutCard"><span className="eyebrow">PRODUCT</span><h2>What Baby is for</h2><p>Baby helps you understand why a stock surfaced, inspect the evidence, view a deterministic plan, monitor a setup over time and review PAPER actions deliberately.</p></section>
      <section className="aboutCard"><span className="eyebrow">BOUNDARY</span><h2>What Baby does not do</h2><p>Baby V15.3 does not enable live-money execution, does not give AI authority to override deterministic scoring or risk rules, and does not automatically submit broker orders.</p></section>
      <section className="aboutCard"><span className="eyebrow">VERSION</span><h2>V15.3</h2><p>Product UI, documentation, branding, navigation, system status and transparency release.</p></section>
      <section className="aboutCard"><span className="eyebrow">ENVIRONMENT</span><h2>Production UI · Alpaca PAPER</h2><p>Broker testing remains simulated. Real-money execution remains disabled.</p></section>
    </div>

    <section className="aboutPrinciples">
      <h2>Design principles</h2>
      <div>
        <span><b>Evidence first</b><small>Missing evidence remains unknown instead of being invented.</small></span>
        <span><b>Deterministic authority</b><small>Research scoring, trade levels and safety gates remain deterministic.</small></span>
        <span><b>Human review</b><small>Setup-ready means review the plan; it is not an automatic order.</small></span>
        <span><b>Explainable system</b><small>Documentation and visible reasoning should make Baby understandable.</small></span>
      </div>
    </section>
  </main>
}
