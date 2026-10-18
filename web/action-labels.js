import {dialogueText} from './video-dialogue.js?v=20261007-video-editor';
// Labels describe the next operation, independently of how existing content was made.
const filled=value=>typeof value==='string'&&!!value.trim();
const hasImage=obj=>!!(obj?.kind?obj.references:obj?.images)?.some(r=>r.file);
const hasVideo=obj=>!!obj?.versions?.some(v=>v.file);
const episodeFor=(p,c)=>p.outputs?.script?.episodes?.find(ep=>ep.source_chapters?.includes(c?.id)||ep.scenes?.some(sc=>sc.source_chapters?.includes(c?.id)));
const batchLabel=(objects,hasContent,noun)=>objects.length&&objects.every(hasContent)?'重新生成'+noun:objects.some(hasContent)?'生成 / 更新'+noun:'生成'+noun;
const ACTIONS=new Set(['video-prompt','video-generate','generate-video','prompts-one','prompts','image-one','generate-image','images-generate','outline-one','outlines-generate','script-one','scripts-generate','breakdown','setup','story','continue','chapters-generate','dialogue-time','white','compose']);

export function actionInfo(p,name,{id='',targets=[],scope='所选'}={}){
 if(!ACTIONS.has(name))return null;
 const chapters=p.outputs?.novel?.chapters||[];
 const obj=[...(p.assets||[]),...(p.segments||[])].find(x=>x.id===id),chapter=chapters.find(c=>c.id===id);
 const text=(label,busy,stage,target_ids=[id])=>({label,busy,stage,target_ids});
 const media=(label,busy,kind)=>({label,busy,kind,target_ids:[id]});
 if(name==='video-prompt')return text(filled(obj?.prompt)?'重新生成镜头描述':'生成镜头描述','正在生成镜头描述…','wf_video_prompt');
 if(name==='video-generate'||name==='generate-video')return {...media(hasVideo(obj)?'重新生成视频':'生成视频','正在生成视频…','video'),disabled:!filled(obj?.prompt)};
 if(name==='prompts-one')return text(filled(obj?.image_prompt)?'重新生成生图提示词':'生成生图提示词','正在生成生图提示词…','wf_prompts');
 if(name==='prompts')return text(batchLabel(targets,x=>filled(x.image_prompt),'所选生图提示词'),'正在生成所选生图提示词…','wf_prompts',targets.map(x=>x.id));
 if(name==='image-one'||name==='generate-image'){
  const noun={character:'角色图',location:'场景图',prop:'道具图'}[obj?.kind]||'镜头图片';
  return {...media((hasImage(obj)?'重新生成':'生成')+noun,'正在生成'+noun+'…','image'),disabled:!filled(obj?.image_prompt)};
 }
 if(name==='images-generate')return {label:batchLabel(targets,hasImage,scope+'图片')+`（${targets.length}项）`,busy:'正在生成'+scope+'图片…',kind:'image',target_ids:targets.map(x=>x.id)};
 if(name==='outline-one')return text(filled(chapter?.summary)?'重新整理本章大纲':'整理本章大纲','正在整理本章大纲…','wf_chapters');
 if(name==='outlines-generate')return text(targets.length&&targets.every(c=>filled(c.summary))?'重新整理所选大纲':targets.some(c=>filled(c.summary))?'整理 / 更新所选大纲':'整理所选大纲','正在整理所选大纲…','wf_chapters',targets.map(x=>x.id));
 if(name==='script-one')return text(episodeFor(p,chapter)?.scenes?.length?'重新生成本章剧本':'生成本章剧本','正在生成本章剧本…','wf_script');
 if(name==='scripts-generate')return text(batchLabel(targets,c=>!!episodeFor(p,c)?.scenes?.length,'所选剧本'),'正在生成所选剧本…','wf_script',targets.map(x=>x.id));
 if(name==='breakdown')return text(p.segments?.some(s=>s.episode_id===id)?'重新拆分本集分镜与资产':'拆分本集分镜与资产','正在拆分本集分镜与资产…','wf_breakdown');
 if(name==='setup')return text(filled(p.outputs?.production_setup?.synopsis)||p.outputs?.production_setup?.characters?.length?'重新分析剧本设定':'分析剧本设定','正在分析剧本设定…','wf_setup',[]);
 if(name==='story')return text(chapters.some(c=>filled(c.content))?'重新生成故事正文':'从灵感生成故事正文','正在生成故事正文…','wf_story',[]);
 if(name==='continue')return text('续写新章节','正在续写新章节…','wf_continue',[]);
 if(name==='chapters-generate')return text(chapters.length?'AI 重新分章与大纲':'AI 拆分章节与大纲','正在拆分章节与大纲…','wf_chapters',[]);
 if(name==='dialogue-time')return {label:obj&&/^\s*\d+:\d+/.test(dialogueText(obj))?'重新分配台词时间':'生成台词时间戳'};
 if(name==='white'){
  const version=obj?.versions?.find(v=>v.id===obj.current_version);
  return media(version?.white?'重新生成尾帧白模':'生成尾帧白模','正在生成尾帧白模…','white');
 }
 if(name==='compose')return {label:p.artifacts?.some(a=>a.file&&!a.type?.startsWith('library_')&&(!id||a.episode_id===id))?'重新拼接导出成片':'拼接导出成片',busy:'正在拼接导出…',kind:'assembly',target_ids:[id]};
 return null;
}

export function ownsAction(info,job){
 if(!info||!job||!info.stage&&!info.kind)return false;
 if(info.stage&&job.stage!==info.stage||info.kind&&job.kind!==info.kind)return false;
 if(!info.target_ids?.length)return !job.target_id&&!job.target_ids?.length;
 const targets=job.target_ids||(job.stage==='wf_prompts'?job.workflow_options?.target_ids||[]:[job.target_id]);
 return targets.some(id=>info.target_ids.includes(id));
}

export function actionDisplay(info,job){
 if(!job)return info.label;
 if(!ownsAction(info,job))return '等待相关任务完成';
 if(job.status==='queued')return info.label+'（排队中）';
 if(job.status==='waiting_dependency')return info.kind==='video'?'等待前段视频完成':'等待前序任务完成';
 if(job.status==='submitting')return info.label+'（提交中）';
 return info.busy;
}

export function labelMarkup(original,label){
 // Preserve an existing decorative icon while replacing only the action text.
 return (original.match(/^\s*<svg\b[\s\S]*?<\/svg>/)?.[0]||'')+label;
}
