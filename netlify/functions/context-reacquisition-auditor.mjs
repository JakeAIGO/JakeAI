import { auditCompression } from '../../auditor-core.mjs';

const headers = {
  'content-type':'application/json; charset=utf-8',
  'cache-control':'no-store',
  'access-control-allow-origin':'*',
  'access-control-allow-headers':'content-type,authorization,x-jakeai-entitlement',
  'access-control-allow-methods':'POST,OPTIONS'
};
export async function handler(event){
  if(event.httpMethod==='OPTIONS') return {statusCode:204,headers,body:''};
  if(event.httpMethod!=='POST') return {statusCode:405,headers,body:JSON.stringify({error:'POST_REQUIRED'})};
  let body;
  try{ body=JSON.parse(event.body||'{}'); }catch{ return {statusCode:400,headers,body:JSON.stringify({error:'INVALID_JSON'})}; }
  if(!body.baseline||!body.candidate) return {statusCode:422,headers,body:JSON.stringify({error:'BASELINE_AND_CANDIDATE_REQUIRED'})};
  const result=auditCompression(body);
  return {statusCode:200,headers,body:JSON.stringify(result)};
}