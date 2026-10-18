/* Pure position planning. Never changes cards, references, edges or groups. */
(function(root){
 const categories=[['text','文本与剧本'],['character','角色与身份'],['location','场景'],['prop','道具'],['shot','镜头与图片'],['video','视频'],['audio','音频'],['compose','剪辑合成'],['other','其他']];
 function category(n,M){const k=M.nodeRole(n);return ['text','split'].includes(k)?'text':['shot','txt2img','image'].includes(k)?'shot':categories.some(([key])=>key===k)?k:'other';}
 const compare=(a,b)=>String(a.studioMcpShotKey||a.studioCharacter||a.title||a.id).localeCompare(String(b.studioMcpShotKey||b.studioCharacter||b.title||b.id),'zh-CN',{numeric:true})||String(a.id).localeCompare(String(b.id));
 function plan(nodes,edges,M,measure){
  const ordered=new Map(categories.map(([key])=>[key,[]]));
  for(const n of nodes)ordered.get(category(n,M)).push(n);
  for(const group of ordered.values())group.sort(compare);
  const characters=ordered.get('character'),roots=characters.filter(n=>!n.studioIdentityParentId),placed=new Set(),family=[];
  function visit(n){if(placed.has(n.id))return;placed.add(n.id);family.push(n);for(const c of characters.filter(c=>c.studioIdentityParentId===n.id).sort((a,b)=>Number(!!b.studioIdentityDefault)-Number(!!a.studioIdentityDefault)||compare(a,b)))visit(c);}
  roots.forEach(visit);characters.forEach(visit);ordered.set('character',family);
  const shotOrder=new Map(ordered.get('shot').map((n,i)=>[n.id,i]));
  const incoming=new Map();for(const e of edges||[]){if(e.kind==='flow')continue;if(!incoming.has(e.to))incoming.set(e.to,[]);incoming.get(e.to).push(e.from);}
  const rank=n=>{const seen=new Set();function walk(id){if(seen.has(id))return Infinity;seen.add(id);if(shotOrder.has(id))return shotOrder.get(id);return Math.min(Infinity,...(incoming.get(id)||[]).map(walk));}return walk(n.id);};
  ordered.get('video').sort((a,b)=>rank(a)-rank(b)||compare(a,b));
  const dims=new Map(nodes.map(n=>{const size=measure(n);return [n.id,{width:Math.max(160,Number(size.width)||360),height:Math.max(120,Number(size.height)||520)}];}));
  // Reserve expansion space. Linked shot/video rows use the same pitch.
  const pitch=Math.max(0,...[...ordered.get('shot'),...ordered.get('video')].map(n=>dims.get(n.id).height))+88;
  const moves=[],sections=[];let x=100;
  for(const [key,label]of categories){
   const group=ordered.get(key);if(!group.length)continue;
   const width=Math.max(...group.map(n=>dims.get(n.id).width)),rows=Math.min(5,Math.max(1,group.length)),columns=Math.ceil(group.length/rows);
   const height=['shot','video'].includes(key)?pitch:Math.max(...group.map(n=>dims.get(n.id).height))+88;
   group.forEach((n,i)=>moves.push({id:n.id,x:x+Math.floor(i/rows)*(width+80),y:170+(i%rows)*height}));
   sections.push({key,label,count:group.length,x,y:100,width:columns*width+(columns-1)*80});
   x+=columns*(width+80)+100;
  }
  return {moves,sections};
 }
 const api={plan,category,categories};root.StudioCanvasOrganizer=api;if(typeof module!=='undefined')module.exports=api;
})(globalThis);
