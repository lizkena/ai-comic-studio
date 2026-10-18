export const VOICE_CATEGORIES={
 gender:{label:'性别',values:['男声','女声','中性声']},
 age:{label:'年龄段',values:['儿童','少年','青年','中年','老年']},
 language:{label:'语言',values:['普通话','粤语','四川话','东北话','英语','日语','其他']},
 style:{label:'音色风格',values:['自然','温柔','清亮','低沉','浑厚','沙哑','活泼','沉稳']}
};
export function voiceCategory(asset,key){
 const spec=VOICE_CATEGORIES[key],tags=asset.tags||[];
 const value=tags.find(x=>x.startsWith(spec.label+'：'))?.slice(spec.label.length+1);
 if(value)return value;
 return spec.values.find(x=>tags.includes(x))||'未标注';
}
export function voiceSummary(asset){return Object.keys(VOICE_CATEGORIES).map(key=>voiceCategory(asset,key));}
export function matchesVoice(asset,filters){return Object.entries(filters).every(([key,value])=>!value||asset.kind==='audio'&&voiceCategory(asset,key)===value);}
export function setVoiceCategories(tags,values){
 const labels=Object.values(VOICE_CATEGORIES).map(x=>x.label+'：');
 const legacy=Object.entries(values).flatMap(([key])=>VOICE_CATEGORIES[key].values);
 return [...(tags||[]).filter(t=>!labels.some(x=>t.startsWith(x))&&!legacy.includes(t)),...Object.entries(values).filter(([,value])=>value&&value!=='未标注').map(([key,value])=>VOICE_CATEGORIES[key].label+'：'+value)];
}
