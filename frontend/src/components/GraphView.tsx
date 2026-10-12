import { useMemo, useState } from 'react'
import { Background, Controls, ReactFlow, type Edge, type Node } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import type { GraphResult } from '../types'

export function GraphView({data}:{data:GraphResult}){
  const [selected,setSelected]=useState<string>()
  const sccByNode=useMemo(()=>{const out=new Map<string,number>();data.analysis.strongly_connected_components.forEach((group,i)=>group.forEach(id=>out.set(id,i)));return out},[data])
  const connected=useMemo(()=>new Set(data.edges.filter(e=>selected&&(e.source===selected||e.target===selected)).flatMap(e=>[e.source,e.target])),[data,selected])
  const nodes=useMemo<Node[]>(()=>data.nodes.map((n,i)=>({id:n.id,position:{x:(i%8)*170,y:Math.floor(i/8)*105},data:{label:n.name||n.id},className:selected===n.id?'graph-selected':connected.has(n.id)?'graph-connected':sccByNode.has(n.id)?'graph-scc':''})),[data,selected,connected,sccByNode])
  const edges=useMemo<Edge[]>(()=>data.edges.map((e,i)=>({id:`e${i}`,source:e.source,target:e.target,label:e.integration_type,animated:Boolean(selected&&(e.source===selected||e.target===selected))})),[data,selected])
  const metric=data.analysis.metrics.find(m=>m.application_id===selected)
  const scc=selected===undefined?undefined:data.analysis.strongly_connected_components[sccByNode.get(selected)??-1]
  return <div><div className="graph" data-testid="dependency-graph" data-node-count={data.nodes.length} data-edge-count={data.edges.length}><ReactFlow nodes={nodes} edges={edges} fitView minZoom={0.1} onNodeClick={(_,node)=>setSelected(node.id)}><Background/><Controls/></ReactFlow></div>{selected&&<div className="notice"><b>{selected}</b><p>Selected dependencies are highlighted. {scc?.length?`SCC migration coupling group: ${scc.join(', ')}`:'Not part of a multi-application SCC.'}</p>{metric&&<div className="chips"><span>in-degree {String(metric.in_degree)}</span><span>out-degree {String(metric.out_degree)}</span><span>blast radius {String(metric.blast_radius)}</span><span>depth {String(metric.dependency_depth)}</span></div>}</div>}</div>
}
