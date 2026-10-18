// Independent graph model; ordinary canvas operations never invoke an AI service.
export const labels={text:'文本',script:'剧本',shot:'分镜 / 提示词',image:'镜头图片',video:'视频',audio:'音色',asset:'参考资产',group:'分组'};
export const newId=()=>`n_${crypto.randomUUID().replaceAll('-','').slice(0,16)}`;
export function newNode(kind,x=80,y=80){return {id:newId(),kind,title:labels[kind],x,y,data:{text:'',...(kind==='shot'||kind==='video'?{duration:8,dialogue:''}:{})}};}
export function connect(graph,source,target){
 if(source===target)throw Error('不能连接自身');
 const a=graph.nodes.find(n=>n.id===source),b=graph.nodes.find(n=>n.id===target);
 if(!a||!b||a.kind==='group'||b.kind==='group')throw Error('请选择有效的输入、输出节点');
 if(graph.edges.some(e=>e.source===source&&e.target===target))return false;
 const visited=new Set();function reaches(id){if(id===source)return true;if(visited.has(id))return false;visited.add(id);return graph.edges.filter(e=>e.source===id).some(e=>reaches(e.target));}
 if(reaches(target))throw Error('不能形成循环依赖');
 graph.edges.push({source,target});return true;
}
export function removeNodes(graph,ids){
 graph.nodes=graph.nodes.filter(n=>!ids.has(n.id));graph.edges=graph.edges.filter(e=>!ids.has(e.source)&&!ids.has(e.target));
 for(const node of graph.nodes)if(ids.has(node.data.group_id))delete node.data.group_id;
}
export function worldPoint(view,x,y){return {x:(x-view.x)/view.zoom,y:(y-view.y)/view.zoom};}
export function zoomAt(view,factor,x,y){const point=worldPoint(view,x,y);const zoom=Math.min(2,Math.max(.2,view.zoom*factor));return {x:x-point.x*zoom,y:y-point.y*zoom,zoom};}
export function dimensions(node){return node.kind==='group'?{w:node.data.width||640,h:node.data.height||430}:{w:244,h:['image','video','asset'].includes(node.kind)?246:190};}
export function curvePath(x1,y1,x2,y2){const c=Math.max(70,Math.abs(x2-x1)*.5);return `M ${x1} ${y1} C ${x1+c} ${y1}, ${x2-c} ${y2}, ${x2} ${y2}`;}
export function wirePath(a,b){const d=dimensions(a),h=dimensions(b);return curvePath(a.x+d.w,a.y+d.h/2,b.x,b.y+h.h/2);}
export function createHistory(limit=50){let past=[],future=[];return {record(g){past.push(structuredClone(g));if(past.length>limit)past.shift();future=[];},undo(g){if(!past.length)return null;future.push(structuredClone(g));return past.pop();},redo(g){if(!future.length)return null;past.push(structuredClone(g));return future.pop();},clear(){past=[];future=[];},canUndo:()=>!!past.length,canRedo:()=>!!future.length};}
