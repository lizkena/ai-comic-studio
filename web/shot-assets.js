// Mirror reference selection in domain.bundle for the per-shot asset overview.
export function shotAssetSummary(project,segment){
 const ids=[...(segment.character_ids||[]),...(segment.location_id?[segment.location_id]:[]),...(segment.prop_ids||[])];
 const variants=segment.variant_ids||[];
 const items=[...new Set(ids)].map(id=>{
  const asset=project.assets.find(a=>a.id===id);
  if(!asset)return {id,name:'资产关联已失效',kind:'missing',file:null,missing:true};
  const candidates=(asset.references||[]).filter(r=>!r.variant_id||variants.includes(r.variant_id));
  const chosen=variants.flatMap(v=>{const matches=candidates.filter(r=>r.variant_id===v);return matches.length?[matches.at(-1)]:[];});
  const references=chosen.length?chosen:candidates.length?[candidates.at(-1)]:[];
  return {id,name:asset.name,kind:asset.kind,description:asset.description,references,file:references[0]?.file,missing:!references.length};
 });
 const previous=segment.continuity?project.segments.find(s=>s.id===segment.previous_id):null;
 const version=previous?.versions?.find(v=>v.id===previous.current_version);
 const frame=segment.continuity?(version?.tail_accepted?(project.settings.white_mode?version.white_accepted&&version.white:version.tail):null):(segment.images||[]).find(i=>i.id===segment.current_image)?.file;
 return {items,missing:items.filter(x=>x.missing),frame,continuity:!!segment.continuity};
}
