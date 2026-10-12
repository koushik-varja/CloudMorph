import type { Portfolio } from './types'

async function request<T>(path:string, init?:RequestInit):Promise<T>{
  const response = await fetch(path, init)
  if(!response.ok){ throw new Error(`${response.status}: ${await response.text()}`) }
  return response.json() as Promise<T>
}
export const api = {
  demo: (size:number) => request<Portfolio>(`/api/demo/${size}`),
  upload: async (file:File) => { const body=new FormData(); body.append('file', file); const r=await request<{portfolio:Portfolio}>('/api/portfolio/import',{method:'POST',body}); return r.portfolio },
  post: <T>(path:string, body:unknown) => request<T>(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
}
