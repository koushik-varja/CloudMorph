import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import {
  AssessmentPanel,
  Dependency,
  ParetoPanel,
  StrategyComparisonPanel,
  Waves,
} from './Panels'
import type { GraphResult, ParetoResult, Plan, ScenarioComparison } from '../types'

vi.mock('./GraphView',()=>({
  GraphView:({data}:{data:GraphResult})=><div data-testid="graph-probe" data-nodes={data.nodes.length} data-edges={data.edges.length}>graph received</div>,
}))

describe('decision panels',()=>{
  it('renders modernization assessment scores, recommendation and evidence',()=>{
    render(<AssessmentPanel rows={[{
      application_id:'billing',name:'Billing',scores:{Replatform:82,Refactor:78,Retain:31},recommendation:'Replatform',runner_up:'Refactor',score_margin:4,
      confidence:'LOW',confidence_reason:'close scores under perturbation',reasons:['Shared database raises migration complexity.'],dimensions:{migration_execution_risk:6.2},
    }]} selected="billing" onSelect={()=>{}}/>)
    expect(screen.getByText('Recommended: Replatform · Confidence: LOW')).toBeInTheDocument()
    expect(screen.getByText('Shared database raises migration complexity.')).toBeInTheDocument()
    expect(screen.getByText('82.0')).toBeInTheDocument()
    expect(screen.getByText('78.0')).toBeInTheDocument()
  })

  it('passes dependency graph data through and surfaces SCC counts',()=>{
    const graph:GraphResult={nodes:[{id:'A',name:'A'},{id:'B',name:'B'},{id:'C',name:'C'}],edges:[{source:'A',target:'B',integration_type:'API'},{source:'B',target:'A',integration_type:'API'}],analysis:{node_count:3,edge_count:2,strongly_connected_components:[['A','B']],shared_database_coupling:{shared:['A','B']},metrics:[]}}
    render(<Dependency graph={graph}/>)
    expect(screen.getByText('SCCs 1')).toBeInTheDocument()
    expect(screen.getByText('Shared DBs 1')).toBeInTheDocument()
    expect(screen.getByTestId('graph-probe')).toHaveAttribute('data-nodes','3')
    expect(screen.getByTestId('graph-probe')).toHaveAttribute('data-edges','2')
  })

  it('renders Pareto candidate counts and frontier points',()=>{
    const data:ParetoResult={plans_attempted:36,unique_candidates:31,duplicate_candidates_removed:5,frontier_count:2,axes_note:'true non-dominance',frontier:[
      {status:'FEASIBLE',candidate_label:'Lowest Risk',metrics:{capital_frontload_index:10,execution_risk_early_exposure:2,technical_debt_reduction_priority:7,modernization_value_priority:6}},
      {status:'FEASIBLE',candidate_label:'Lowest Cost',metrics:{capital_frontload_index:5,execution_risk_early_exposure:4,technical_debt_reduction_priority:5,modernization_value_priority:4}},
    ]}
    render(<ParetoPanel data={data}/>)
    expect(screen.getByText('31 unique candidates')).toBeInTheDocument()
    expect(screen.getByText('2 non-dominated')).toBeInTheDocument()
    expect(screen.getByLabelText('Pareto frontier scatter plot').querySelectorAll('circle')).toHaveLength(2)
  })

  it('renders migration wave explanations rather than only application lists',()=>{
    const plan:Plan={status:'FEASIBLE',solver_used:'deterministic_fallback',waves:[{wave:2,applications:['Payments','Billing'],effort:12,risk:8,budget:25000,critical_apps:1,why:['Payments depends on Identity in Wave 1.','Billing is grouped by a shared-database constraint.']}]}
    render(<Waves plan={plan}/>)
    expect(screen.getByText('Why this wave?')).toBeInTheDocument()
    expect(screen.getByText('Payments depends on Identity in Wave 1.')).toBeInTheDocument()
    expect(screen.getByText('Billing is grouped by a shared-database constraint.')).toBeInTheDocument()
  })

  it('renders strategy comparison metrics as cards instead of primary JSON',()=>{
    const rows:ScenarioComparison[]=[{name:'Balanced modernization',strategy_counts:{Rehost:2,Replatform:5,Refactor:3},estimated_first_year_cost:100000,effort_index:42,migration_risk_index:18,technical_debt_reduction_index:27,apps_modernized:8,migration_duration_estimate_waves:3,architecture_complexity_index:1.1,resilience_potential_index:1.4,label:'Estimated indicators'}]
    render(<StrategyComparisonPanel rows={rows}/>)
    expect(screen.getByRole('heading',{name:'Balanced modernization'})).toBeInTheDocument()
    expect(screen.getByText('Estimated first-year cost')).toBeInTheDocument()
    expect(screen.getByText('Debt reduction')).toBeInTheDocument()
    expect(screen.getByText('Apps modernized: 8')).toBeInTheDocument()
    expect(screen.getByText('3 waves')).toBeInTheDocument()
  })
})
