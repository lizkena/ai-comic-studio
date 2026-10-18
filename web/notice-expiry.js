// A notice's lifetime starts once, not again on every poll or render.
export function createNoticeExpiry({storage,now=Date.now,schedule=setTimeout,onExpire=()=>{},duration=15000}){
 const key='comic-notice-deadlines';let deadlines={};const timers=new Set();
 try{deadlines=JSON.parse(storage.getItem(key)||'{}');if(!deadlines||Array.isArray(deadlines)||typeof deadlines!=='object')deadlines={};}catch{}
 function persist(){try{storage.setItem(key,JSON.stringify(deadlines));}catch{}}
 function visible(identity){
  if(!Number.isFinite(deadlines[identity])){deadlines[identity]=now()+duration;persist();}
  const remaining=deadlines[identity]-now();
  if(remaining<=0)return false;
  if(!timers.has(identity)){
   timers.add(identity);schedule(()=>{timers.delete(identity);onExpire();},remaining);
  }
  return true;
 }
 return {visible};
}
