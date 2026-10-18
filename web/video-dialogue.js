const time=n=>`${String(Math.floor(n/60)).padStart(2,'0')}:${(n%60).toFixed(2).padStart(5,'0').replace(/\.00$/,'')}`;
export function dialogueText(seg){
 if(typeof seg.dialogue_text==='string')return seg.dialogue_text;
 return (seg.shots||[]).flatMap(sh=>{const lines=(sh.dialogue||'').split('\n').filter(x=>x.trim());return lines.map((line,i)=>`${time(Number(sh.start||0)+(Number(sh.end??seg.duration)-Number(sh.start||0))*i/lines.length)}–${time(Number(sh.start||0)+(Number(sh.end??seg.duration)-Number(sh.start||0))*(i+1)/lines.length)} ${line.trim()}`);}).join('\n');
}
const seconds=s=>s.split(':').reduce((n,x)=>n*60+Number(x),0);
export function parseDialogue(text,duration){
 let end=0;
 return text.split('\n').filter(x=>x.trim()).map((line,i)=>{
  const m=line.trim().match(/^(\d+:\d+(?:\.\d+)?)\s*[–—-]\s*(\d+:\d+(?:\.\d+)?)\s+([^：:\n]+)[：:]\s*(.+)$/);
  if(!m)throw Error(`第 ${i+1} 行请使用“00:00–00:02 角色：台词”格式`);
  const start=seconds(m[1]),stop=seconds(m[2]);
  if(!(start>=end&&stop>start&&stop<=Number(duration)+.001))throw Error(`第 ${i+1} 行时间应在镜头时长内，且不能重叠`);
  end=stop;return {start,end:stop,speaker:m[3].trim(),text:m[4].trim()};
 });
}
export function autoDialogue(text,duration){
 const lines=text.split('\n').map(x=>x.replace(/^\s*\d+:\d+(?:\.\d+)?\s*[–—-]\s*\d+:\d+(?:\.\d+)?\s*/,'').trim()).filter(Boolean);
 const total=lines.reduce((n,x)=>n+x.length,0);let at=0;
 return lines.map((line,i)=>{const start=at;at=i===lines.length-1?Number(duration):Math.round((at+Number(duration)*line.length/total)*100)/100;return `${time(start)}–${time(at)} ${line}`;}).join('\n');
}
export function referenceMarkup(text,assets,esc){
 const names=[...assets].filter(a=>a.name).sort((a,b)=>b.name.length-a.name.length),labels={character:'角色',location:'场景',prop:'道具'};
 const pattern=names.map(a=>a.name.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('|');
 if(!pattern)return esc(text);
 const re=new RegExp(pattern,'g');let at=0,out='';
 for(const match of text.matchAll(re)){const a=names.find(a=>a.name===match[0]);out+=esc(text.slice(at,match.index))+`<span class="wf-inline-ref ${esc(a.kind)}" data-asset-id="${esc(a.id)}" data-label="${labels[a.kind]||'资产'}" title="${esc(labels[a.kind]+'：'+a.name+(a.voice?' · 音色已绑定':''))}">${esc(a.name)}</span>`;at=match.index+match[0].length;}
 return out+esc(text.slice(at));
}
