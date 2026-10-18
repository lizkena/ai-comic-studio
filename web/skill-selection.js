// These stages mirror the backend workflow task routes, not the navigation tab.
export function workflowSkillStages(area,tab='source',entry='novel'){
 if(area==='novel')return tab==='chapters'?[['novel','章节大纲'],['script','剧本']]:tab==='setup'?[['direction','剧本设定']]:entry==='script'?[['script','剧本']]:entry==='idea'?[['direction','故事设定'],['novel','小说续写']]:[['direction','剧本设定']];
 if(area==='script')return [['script','剧本']];
 if(area==='storyboard')return [['storyboard','分镜'],['assets','生图提示词']];
 if(area==='prompts')return [['assets','生图提示词'],['storyboard','视频提示词']];
 if(area==='images')return [['assets','生图']];
 if(area==='video')return [['storyboard','镜头描述']];
 return [];
}
export function usableSkills(skills,stage){return skills.filter(x=>x.stage===stage&&x.availability!=='缺少工具');}
export function selectedSkill(skills,stage,binding){
 const list=usableSkills(skills,stage);
 // Keep invalid saved bindings explicit: displaying a different default would lie
 // about what the backend will execute. The user can choose a valid replacement.
 return binding?list.find(x=>x.id===binding):list.find(x=>x.is_default)||list[0];
}
export function skillOptions(skills,stage,binding,esc){
 const list=usableSkills(skills,stage),selected=selectedSkill(skills,stage,binding);
 const invalid=binding&&!selected?`<option value="${esc(binding)}" selected disabled>原技能不可用，请重新选择</option>`:'';
 return invalid+list.map(x=>`<option value="${esc(x.id)}" ${selected?.id===x.id?'selected':''}>${esc(x.name)}</option>`).join('')||'<option value="">暂无可用技能</option>';
}
