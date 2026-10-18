// Detect explicit chapter numbers only; unnumbered/duplicate titles need manual ordering.
export function chapterNumber(title){
 const value=String(title||'').normalize('NFKC').replace(/^\s*#{1,6}\s*/, '').trim();
 const match=value.match(/^第\s*([0-9]+|[零〇一二两三四五六七八九十百千万]+)\s*[章回]/);
 if(!match)return null;
 const number=match[1];
 if(/^\d+$/.test(number)){const n=Number(number);return Number.isSafeInteger(n)?n:null;}
 const digits={零:0,〇:0,一:1,二:2,两:2,三:3,四:4,五:5,六:6,七:7,八:8,九:9};
 if(!/[十百千万]/.test(number))return Number([...number].map(x=>digits[x]).join(''));
 const units={十:10,百:100,千:1000};let total=0,section=0,digit=0;
 for(const char of number){
  if(char in digits)digit=digits[char];
  else if(char==='万'){total+=(section+digit)*10000;section=0;digit=0;}
  else{section+=(digit||1)*units[char];digit=0;}
 }
 return total+section+digit;
}

export function chapterOrderStatus(chapters){
 const numbered=chapters.map(c=>({id:c.id,number:chapterNumber(c.title)}));
 if(numbered.some(c=>c.number===null))return {sortable:false,changed:false,message:'部分标题没有明确章号，可用上移 / 下移调整顺序。'};
 if(new Set(numbered.map(c=>c.number)).size!==numbered.length)return {sortable:false,changed:false,message:'检测到重复章号，请用上移 / 下移调整，或编辑章节标题。'};
 const ids=[...numbered].sort((a,b)=>a.number-b.number).map(c=>c.id);
 const changed=ids.some((id,index)=>id!==chapters[index].id);
 return {sortable:true,changed,ids,message:changed?'检测到章号顺序不一致，可点击“按章号排序”，也可手动上移 / 下移。':'当前顺序与标题章号一致，也可手动上移 / 下移。'};
}

export function moveChapter(chapters,id,delta){
 const ids=chapters.map(c=>c.id),index=ids.indexOf(id),next=index+delta;
 if(index<0||next<0||next>=ids.length)return null;
 [ids[index],ids[next]]=[ids[next],ids[index]];
 return ids;
}
