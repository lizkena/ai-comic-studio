(function(root){
    'use strict';
    const percent = value => Math.round(Math.max(0, Math.min(1, Number(value) || 0)) * 100);
    function annotationText(note){
        const r = note.region || {};
        const location = note.kind === 'point'
            ? `位置 (${percent(r.x)}%, ${percent(r.y)}%)`
            : `区域：左上 (${percent(r.x)}%, ${percent(r.y)}%)，右下 (${percent((Number(r.x)||0)+(Number(r.width)||0))}%, ${percent((Number(r.y)||0)+(Number(r.height)||0))}%)`;
        return `${location}：${String(note.text || '').trim()}`;
    }
    function enhanceRequest(node, request, images){
        const sections = [];
        const skill = node?.localSkill;
        if(skill?.content) sections.push(`设计 Skill：${skill.name || '本地技能'}\n将以下技能作为本次创作的设计指导；以用户本次要求为准，直接输出生成结果。\n${skill.content}`);
        const comments = [];
        (request.refs || []).forEach((ref, index) => {
            const image = (images || []).find(item => item.url === ref.url || item.originalLocalUrl === ref.url);
            const notes = (image?.annotations || []).filter(note => note.text?.trim() && !note.resolved && note.includeInGeneration !== false);
            if(notes.length) comments.push(`图${index + 1}（${ref.name || '参考图'}）\n${notes.map((note, i) => `${i + 1}. ${annotationText(note)}`).join('\n')}`);
        });
        if(comments.length) sections.push(`图片修改意见：坐标以原图左上角为原点，按图片宽高百分比描述。按标记修改对应区域，未提及区域尽量保留。标记编号和框线仅用于说明，不要绘制到结果中。\n${comments.join('\n\n')}`);
        if(!sections.length) return request;
        return {...request, prompt:[...sections, `本次创作要求：\n${request.prompt || '请按所选技能和图片修改意见完成创作。'}`].join('\n\n')};
    }
    function mentionQuery(text){
        // Works after Chinese prose; whitespace ends the current search.
        const direct = String(text || '').match(/@([^@\s]{0,60})$/);
        return direct ? direct[1] : null;
    }
    const api = {annotationText, enhanceRequest, mentionQuery};
    if(typeof module !== 'undefined' && module.exports) module.exports = api;
    else root.YaoguangCanvasContext = api;
})(typeof window !== 'undefined' ? window : globalThis);
