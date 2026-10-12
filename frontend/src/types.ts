export type Strategy='Rehost'|'Replatform'|'Refactor'|'Replace'|'Retain'|'Retire'

export type AppRecord = {
  application_id:string; name:string; business_domain:string; business_criticality:string;
  technical_debt_score:number; migration_effort:number; migration_risk:number; migration_cost:number;
  dependencies:{target:string;integration_type:string;synchronous:boolean}[]; [key:string]:unknown;
}
export type Portfolio={name:string;applications:AppRecord[];synthetic:boolean}
export type GraphMetric={application_id:string;in_degree:number;out_degree:number;betweenness:number;dependency_depth:number;blast_radius:number;articulation_like:boolean}
export type GraphResult={nodes:{id:string;name:string}[];edges:{source:string;target:string;integration_type:string}[];analysis:{node_count:number;edge_count:number;strongly_connected_components:string[][];shared_database_coupling:Record<string,string[]>;metrics:GraphMetric[]}}
export type Wave={wave:number;applications:string[];effort:number;risk:number;migration_execution_risk?:number;current_operational_risk?:number;budget:number;critical_apps:number;why?:string[]}
export type Plan={status:string;objective?:string;solver?:string;solver_used?:string;reason?:string;conflict_hints?:string[];waves?:Wave[];metrics?:Record<string,number|string>;why?:string;candidate_label?:string}
export type Assessment={application_id:string;name:string;scores:Record<string,number>;recommendation:string;runner_up:string;score_margin:number;confidence:string;confidence_reason:string;decision_stability?:string;recommendation_distribution?:Record<string,number>;most_influential_factors?:string[];reasons:string[];dimensions:Record<string,number>}
export type Sensitivity={application_id:string;recommendation_distribution:Record<string,number>;decision_stability:string;most_influential_factors:string[];method:string}
export type ParetoResult={plans_attempted:number;unique_candidates:number;duplicate_candidates_removed:number;frontier_count:number;frontier:Plan[];axes_note:string}
export type Architecture={application_id:string;strategy:string;pattern:string;components:{id:string;label:string;why:string}[];warnings:string[];provider_neutral?:boolean;governance_note?:string}
export type CostResult={label:string;strategy:string;monthly_run_cost_estimate:number;migration_effort_cost_estimate:number;annualized_first_year_estimate:number;assumptions:Record<string,number>;formula?:string}
export type CostComparison={current_estate_monthly_input:number;alternatives:CostResult[];assumption_label:string}
export type Diagnosis={application_id:string;severity:string;current_operational_risk:number;migration_execution_risk:number;evidence:string[]}
export type TechnicalDebt={application_id:string;technical_debt_index:number;input_debt_score:number;factors:Record<string,number>;weights:Record<string,number>;evidence:string[];formula:string}
export type ScenarioComparison={name:string;strategy_counts:Record<string,number>;estimated_first_year_cost:number;effort_index:number;migration_risk_index:number;technical_debt_reduction_index:number;apps_modernized:number;migration_duration_estimate_waves:number;architecture_complexity_index:number;resilience_potential_index:number;label:string;modernization_value_index?:number}
export type SecurityControl={control:string;status:string;evidence:string}
export type SecurityAssessment={application_id:string;controls:SecurityControl[];regulatory_tags:string[];disclaimer:string}
