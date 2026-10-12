import { useMemo, useState } from 'react'
import { api } from './api'
import type {
  AppRecord,
  Architecture,
  Assessment,
  CostComparison,
  CostResult,
  Diagnosis,
  GraphResult,
  ParetoResult,
  Plan,
  Portfolio,
  ScenarioComparison,
  SecurityAssessment,
  Sensitivity,
  Strategy,
  TechnicalDebt,
} from './types'
import {
  ArchitecturePanel,
  ArchitectureRiskPanel,
  AssessmentPanel,
  AssumptionsPanel,
  CostComparisonPanel,
  CostPanel,
  Dependency,
  Empty,
  Inventory,
  JsonBlock,
  Kpis,
  ParetoPanel,
  SecurityGovernancePanel,
  SensitivityPanel,
  StrategyComparisonPanel,
  TechnicalDebtPanel,
  Waves,
} from './components/Panels'
import './styles.css'

const sections=['Portfolio Overview','Application Inventory','Dependency Graph','Architecture Risks','Technical Debt','Modernization Assessment','Decision Sensitivity','Strategy Comparison','Migration Wave Optimizer','Pareto Frontier','Migration Roadmap','Target Architecture','Cost Model','Security / Governance','Assumptions'] as const
type Section=typeof sections[number]
const strategies:Strategy[]=['Rehost','Replatform','Refactor','Replace','Retain','Retire']
const baseConstraints={max_waves:8,max_effort_per_wave:80,max_critical_apps_per_wave:3,max_risk_per_wave:60,budget_per_wave:200000,team_capacity_per_wave:80,precedence:[],together:[],earliest_wave:{},deadlines:{},wave_regions:{},compliance_allowed_waves:{},maintenance_allowed_waves:{},enforce_dependencies:true}
function constraintsFor(p:Portfolio){const n=Math.max(1,p.applications.length);const target=6;const effort=p.applications.reduce((s,a)=>s+a.migration_effort,0);const risk=p.applications.reduce((s,a)=>s+a.migration_risk,0);const cost=p.applications.reduce((s,a)=>s+a.migration_cost,0);const critical=p.applications.filter(a=>a.business_criticality==='critical').length;return {...baseConstraints,max_effort_per_wave:Math.max(10,Math.ceil(effort/target*1.25)),team_capacity_per_wave:Math.max(10,Math.ceil(effort/target*1.25)),max_risk_per_wave:Math.max(10,Math.ceil(risk/target*1.25)),budget_per_wave:Math.max(10000,Math.ceil(cost/target*1.25)),max_critical_apps_per_wave:Math.max(1,Math.ceil(critical/target)+1),max_waves:Math.min(12,Math.max(4,Math.ceil(n/100)+6))}}

type CostAssumptions={compute_per_rps_month:number;storage_per_gb_month:number;managed_db_base_month:number;network_fraction:number;operations_fraction:number;engineer_hourly_rate:number;effort_unit_hours:number;license_monthly:number}

export default function App(){
  const [active,setActive]=useState<Section>('Portfolio Overview')
  const [portfolio,setPortfolio]=useState<Portfolio>()
  const [graph,setGraph]=useState<GraphResult>()
  const [constraints,setConstraints]=useState(baseConstraints)
  const [diagnosis,setDiagnosis]=useState<Diagnosis[]>()
  const [debt,setDebt]=useState<TechnicalDebt[]>()
  const [assessment,setAssessment]=useState<Assessment[]>()
  const [sensitivity,setSensitivity]=useState<Sensitivity[]>()
  const [plan,setPlan]=useState<Plan>()
  const [pareto,setPareto]=useState<ParetoResult>()
  const [scenarios,setScenarios]=useState<ScenarioComparison[]>()
  const [architecture,setArchitecture]=useState<Architecture>()
  const [architectureStrategy,setArchitectureStrategy]=useState<Strategy>('Replatform')
  const [cost,setCost]=useState<CostResult>()
  const [costComparison,setCostComparison]=useState<CostComparison>()
  const [costStrategy,setCostStrategy]=useState<Strategy>('Replatform')
  const [security,setSecurity]=useState<SecurityAssessment[]>()
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [selected,setSelected]=useState<string>('')
  const [objective,setObjective]=useState('balanced_risk')
  const [costAssumptions,setCostAssumptions]=useState<CostAssumptions>({compute_per_rps_month:0.8,storage_per_gb_month:0.12,managed_db_base_month:180,network_fraction:0.08,operations_fraction:0.12,engineer_hourly_rate:45,effort_unit_hours:40,license_monthly:0})
  const app=useMemo(()=>portfolio?.applications.find(a=>a.application_id===selected)||portfolio?.applications[0],[portfolio,selected])

  async function guard(fn:()=>Promise<void>){setBusy(true);setError('');try{await fn()}catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy(false)}}
  async function loadDemo(size:number){await guard(async()=>{const p=await api.demo(size);setPortfolio(p);setConstraints(constraintsFor(p));setSelected(p.applications[0]?.application_id||'');setGraph(undefined);setPlan(undefined);setPareto(undefined);setArchitecture(undefined);setCost(undefined);setCostComparison(undefined)})}
  async function upload(file:File){await guard(async()=>{const p=await api.upload(file);setPortfolio(p);setConstraints(constraintsFor(p));setSelected(p.applications[0]?.application_id||'');setGraph(undefined);setPlan(undefined)})}
  async function analyze(){if(!portfolio)return;await guard(async()=>{const r=await api.post<{graph:GraphResult;diagnosis:Diagnosis[];technical_debt:TechnicalDebt[];assessment:Assessment[];sensitivity:Sensitivity[];security:SecurityAssessment[]}>('/api/analyze?samples=80',{portfolio,weights:{}});setGraph(r.graph);setDiagnosis(r.diagnosis);setDebt(r.technical_debt);setAssessment(r.assessment);setSensitivity(r.sensitivity);setSecurity(r.security)})}
  async function optimize(){if(!portfolio)return;await guard(async()=>{const req={portfolio,constraints,objective,solver_mode:'auto'};const [p,f]=await Promise.all([api.post<Plan>('/api/optimize',req),api.post<ParetoResult>('/api/pareto',req)]);setPlan(p);setPareto(f)})}
  async function compare(){if(!portfolio)return;await guard(async()=>setScenarios(await api.post<ScenarioComparison[]>('/api/scenarios',{portfolio,scenarios:[{name:'Lift-and-shift-heavy',strategy_bias:{Rehost:10},weights:{}},{name:'Balanced modernization',strategy_bias:{},weights:{}},{name:'Aggressive refactoring',strategy_bias:{Refactor:12},weights:{debt_importance:1.3}},{name:'Budget constrained',strategy_bias:{Rehost:6,Retain:5},weights:{cost_importance:1.3}}]})))}
  async function architectureFor(){if(!app)return;await guard(async()=>setArchitecture(await api.post<Architecture>('/api/architecture',{application:app,strategy:architectureStrategy})))}
  async function costFor(){if(!app)return;await guard(async()=>setCost(await api.post<CostResult>(`/api/cost/${costStrategy}`,{application:app,assumptions:costAssumptions})))}
  async function compareCosts(){if(!app)return;await guard(async()=>setCostComparison(await api.post<CostComparison>('/api/cost-compare',{application:app,assumptions:costAssumptions})))}

  function content(){
    if(!portfolio)return <Empty/>
    switch(active){
      case 'Portfolio Overview': return <><Kpis portfolio={portfolio} graph={graph}/><div className="notice"><b>{portfolio.synthetic?'SYNTHETIC DEMONSTRATION DATA':'USER-PROVIDED DATA'}</b><p>{portfolio.name}</p></div><JsonBlock value={{graph_summary:graph?.analysis?{nodes:graph.analysis.node_count,edges:graph.analysis.edge_count,sccs:graph.analysis.strongly_connected_components.length}:null,plan:plan?.status}}/></>
      case 'Application Inventory': return <Inventory apps={portfolio.applications}/>
      case 'Dependency Graph': return <Dependency graph={graph}/>
      case 'Architecture Risks': return diagnosis?<ArchitectureRiskPanel rows={diagnosis} graph={graph}/>:<Empty/>
      case 'Technical Debt': return debt?<TechnicalDebtPanel rows={debt}/>:<Empty/>
      case 'Modernization Assessment': return assessment?<AssessmentPanel rows={assessment} selected={selected} onSelect={setSelected}/>:<Empty/>
      case 'Decision Sensitivity': return sensitivity?<SensitivityPanel rows={sensitivity} selected={selected} onSelect={setSelected}/>:<Empty/>
      case 'Strategy Comparison': return <><button onClick={compare}>Run scenario comparison</button>{scenarios?<StrategyComparisonPanel rows={scenarios}/>:<Empty/>}</>
      case 'Migration Wave Optimizer': return <><ConstraintEditor value={constraints} onChange={setConstraints}/><label className="field-label">Optimization objective<select aria-label="Optimization objective" value={objective} onChange={e=>setObjective(e.target.value)}><option value="balanced_risk">Balanced risk</option><option value="minimize_execution_risk">Minimize execution risk</option><option value="reduce_operational_risk">Reduce current operational risk</option><option value="cost">Cost exposure</option><option value="debt">Technical debt</option><option value="value">Modernization value</option></select></label><button onClick={optimize}>Generate valid waves</button>{plan?<Waves plan={plan}/>:<Empty/>}</>
      case 'Pareto Frontier': return pareto?<ParetoPanel data={pareto}/>:<Empty/>
      case 'Migration Roadmap': return plan?<Waves plan={plan}/>:<Empty/>
      case 'Target Architecture': return <><div className="action-row"><label className="field-label">Application<select value={app?.application_id||''} onChange={e=>setSelected(e.target.value)}>{portfolio.applications.map(a=><option key={a.application_id} value={a.application_id}>{a.name}</option>)}</select></label><label className="field-label">Strategy<select aria-label="Architecture strategy" value={architectureStrategy} onChange={e=>setArchitectureStrategy(e.target.value as Strategy)}>{strategies.map(strategy=><option key={strategy} value={strategy}>{strategy}</option>)}</select></label><button onClick={architectureFor} disabled={!app}>Generate provider-neutral architecture</button></div>{architecture?<ArchitecturePanel value={architecture}/>:<Empty/>}</>
      case 'Cost Model': return <><CostAssumptionEditor value={costAssumptions} onChange={setCostAssumptions}/><div className="action-row"><label className="field-label">Application<select value={app?.application_id||''} onChange={e=>setSelected(e.target.value)}>{portfolio.applications.map(a=><option key={a.application_id} value={a.application_id}>{a.name}</option>)}</select></label><label className="field-label">Strategy<select aria-label="Cost strategy" value={costStrategy} onChange={e=>setCostStrategy(e.target.value as Strategy)}>{strategies.map(strategy=><option key={strategy} value={strategy}>{strategy}</option>)}</select></label><button onClick={costFor} disabled={!app}>Estimate illustrative cost</button><button onClick={compareCosts} disabled={!app}>Compare all strategies</button></div>{cost?<CostPanel value={cost}/>:null}{costComparison?<CostComparisonPanel value={costComparison}/>:null}{!cost&&!costComparison?<Empty/>:null}</>
      case 'Security / Governance': return security?<SecurityGovernancePanel rows={security}/>:<Empty/>
      case 'Assumptions': return <AssumptionsPanel costAssumptions={costAssumptions} constraints={constraints} synthetic={portfolio.synthetic}/>
    }
  }

  return <div className="shell"><aside><div className="brand"><div className="mark">CM</div><div><b>CloudMorph</b><small>Modernization Decision Support</small></div></div><div className="dataset"><button onClick={()=>loadDemo(100)}>Load 100-app demo</button><button onClick={()=>loadDemo(500)}>500</button><button onClick={()=>loadDemo(1000)}>1,000</button><label className="upload">Import CSV / JSON / YAML<input type="file" accept=".csv,.json,.yaml,.yml" onChange={e=>e.target.files?.[0]&&upload(e.target.files[0])}/></label></div><nav>{sections.map(s=><button className={active===s?'active':''} key={s} onClick={()=>setActive(s)}>{s}</button>)}</nav></aside><main><header className="top"><div><small>ENTERPRISE ESTATE</small><h1>{active}</h1></div><div className="actions"><button disabled={!portfolio||busy} onClick={analyze}>Run analysis</button><button className="primary" disabled={!portfolio||busy} onClick={optimize}>Optimize waves</button></div></header>{error&&<div className="error">{error}</div>}{busy&&<div className="progress">Processing…</div>}<section className="panel">{content()}</section><footer>CloudMorph outputs are decision-support estimates. Synthetic demo data is clearly labeled; generated Terraform is draft-only and never applied.</footer></main></div>
}

function ConstraintEditor({value,onChange}:{value:typeof baseConstraints;onChange:(v:typeof baseConstraints)=>void}){const fields:[keyof Pick<typeof baseConstraints,'max_waves'|'max_effort_per_wave'|'team_capacity_per_wave'|'max_risk_per_wave'|'budget_per_wave'|'max_critical_apps_per_wave'>,string][]=[['max_waves','Max waves'],['max_effort_per_wave','Max effort / wave'],['team_capacity_per_wave','Team capacity / wave'],['max_risk_per_wave','Max risk / wave'],['budget_per_wave','Budget / wave'],['max_critical_apps_per_wave','Critical apps / wave']];return <div className="constraint-grid">{fields.map(([key,label])=><label key={key}>{label}<input type="number" min="0" value={String(value[key])} onChange={e=>onChange({...value,[key]:Number(e.target.value)})}/></label>)}</div>}
function CostAssumptionEditor({value,onChange}:{value:CostAssumptions;onChange:(v:CostAssumptions)=>void}){return <div><div className="notice"><b>ILLUSTRATIVE SAMPLE VALUES</b><p>These are user-editable assumptions, not live AWS/Azure/GCP pricing.</p></div><div className="constraint-grid">{(Object.keys(value) as (keyof CostAssumptions)[]).map(key=><label key={key}>{key}<input type="number" step="0.01" min="0" value={value[key]} onChange={e=>onChange({...value,[key]:Number(e.target.value)})}/></label>)}</div></div>}
