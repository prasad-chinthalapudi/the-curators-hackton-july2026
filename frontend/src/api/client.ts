import axios from "axios";
import type {OnePager,Readiness,SearchRequest,SearchResponse} from "../types";
export const apiClient=axios.create({baseURL:import.meta.env.VITE_API_BASE_URL??"http://localhost:8000/api",timeout:30000});
export const searchDocuments=async(request:SearchRequest)=>(await apiClient.post<SearchResponse>("/search",request)).data;
export const checkReadiness=async(ids:string[])=>(await apiClient.post<Readiness>("/one-pagers/readiness",{document_ids:ids})).data;
export const generateOnePager=async(ids:string[])=>(await apiClient.post<OnePager>("/one-pagers",{document_ids:ids,title:null})).data;
export const getOnePager=async(id:string)=>(await apiClient.get<OnePager>(`/one-pagers/${id}`)).data;
export const downloadOnePagerPdf=async(id:string)=>{
  const response=await apiClient.get<Blob>(`/one-pagers/${id}/pdf`,{responseType:"blob"});
  const url=URL.createObjectURL(response.data);
  const anchor=document.createElement("a");
  anchor.href=url;
  anchor.download=`${id}-one-pager.pdf`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
};
export const saveKnowledge=async(body:{question:string;answer:string;related_document_ids:string[];contributor:string})=>(await apiClient.post("/knowledge",body)).data;
