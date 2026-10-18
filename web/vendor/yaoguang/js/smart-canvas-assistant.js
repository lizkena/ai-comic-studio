/* Local canvas tools. Image comments stay on image records; skills stay on nodes. */
(function(){
    'use strict';
    let skills = [];
    let skillError = '';
    let annotation = null;
    let drag = null;
    let previousFocus = null;
    const byId = id => document.getElementById(id);
    const e = value => escapeHtml(String(value ?? ''));
    const dialog = byId('canvasAnnotationDialog');
    const stage = byId('annotationOverlay');
    const input = byId('annotationText');
    const list = byId('annotationList');
    const picker = byId('canvasSkillPicker');
    const skillButton = byId('canvasSkillButton');

    function allImages(){
        return nodes.filter(node => !isSmartGroupNode(node)).flatMap(node => imagesForNode(node));
    }
    function targetImage(){
        const node = nodes.find(item => item.id === annotation?.nodeId);
        const image = node?.images?.[annotation?.index];
        return image && imageForDisplay(image)?.url === annotation?.url ? image : null;
    }
    function notes(){ return Array.isArray(targetImage()?.annotations) ? targetImage().annotations : []; }
    function status(message){ byId('annotationStatus').textContent = message; }
    function selectNote(note){
        annotation.selected = note?.id || '';
        annotation.draft = note ? JSON.parse(JSON.stringify(note)) : null;
        input.value = note?.text || '';
        byId('annotationInclude').checked = note?.includeInGeneration !== false;
        byId('annotationSave').disabled = !note;
        byId('annotationEditor').hidden = !note;
        status(note ? '修改评论后点击“保存评论”。' : '在图片上点击标记位置，或拖拽框选区域。');
        renderNotes();
    }
    function marker(note, number, isDraft=false){
        const r = note.region;
        if(!r) return '';
        const point = note.kind === 'point';
        return `<button type="button" class="annotation-marker ${point ? 'is-point' : ''} ${note.resolved ? 'is-resolved' : ''} ${note.id === annotation?.selected || isDraft ? 'is-active' : ''}" data-annotation-id="${e(note.id || '')}" style="left:${r.x*100}%;top:${r.y*100}%;width:${point ? '0' : r.width*100+'%'};height:${point ? '0' : r.height*100+'%'}" aria-label="标记 ${number}：${e(note.text || '待填写评论')}"><span>${number}</span></button>`;
    }
    function renderNotes(){
        if(!annotation) return;
        const saved = notes();
        stage.innerHTML = saved.filter(note => note.id !== annotation.draft?.id).map(note => marker(note, saved.indexOf(note)+1)).join('');
        if(annotation.draft) stage.insertAdjacentHTML('beforeend', marker(annotation.draft, annotation.selected ? saved.findIndex(note => note.id === annotation.selected)+1 : saved.length+1, true));
        byId('annotationCount').textContent = `${saved.length} 条评论`;
        list.innerHTML = saved.length ? saved.map((note, index) => `<article class="annotation-note ${note.resolved ? 'is-resolved' : ''}">
            <button class="annotation-note-select" type="button" data-select-note="${e(note.id)}"><span class="annotation-number">${index+1}</span><span>${e(note.text)}</span></button>
            <small>${note.resolved ? '已完成 · 不参与生成' : note.includeInGeneration === false ? '仅记录 · 不参与生成' : '待修改 · 生成时附带'}</small>
            <div class="annotation-note-actions"><button type="button" data-resolve-note="${e(note.id)}">${note.resolved ? '重新打开' : '标为完成'}</button><button type="button" data-delete-note="${e(note.id)}">删除</button></div>
        </article>`).join('') : '<p class="annotation-empty">还没有评论。标出需要修改的文字、产品或背景，再写下你的要求。</p>';
        byId('annotationApply').disabled = !saved.some(note => !note.resolved && note.includeInGeneration !== false);
    }
    function openAnnotations(nodeId, index){
        const image = imageForDisplay(nodes.find(node => node.id === nodeId)?.images?.[index]);
        if(!image?.url || mediaKindForItem(image) !== 'image') return;
        previousFocus = document.activeElement;
        annotation = {nodeId, index, url:image.url, selected:'', draft:null};
        byId('annotationImage').src = image.url;
        byId('annotationImage').alt = image.name || '待标记图片';
        byId('annotationTitle').textContent = `标记与评论 · ${image.name || '图片'}`;
        dialog.showModal();
        selectNote(null);
        byId('annotationClose').focus();
    }
    function closeAnnotations(){
        dialog.close();
        annotation = null;
        drag = null;
        previousFocus?.focus?.();
    }
    function point(event){
        const rect = stage.getBoundingClientRect();
        return {x:Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width)),y:Math.max(0,Math.min(1,(event.clientY-rect.top)/rect.height))};
    }
    function updateRegion(end){
        const start = drag.start;
        annotation.draft.region = {x:Math.min(start.x,end.x), y:Math.min(start.y,end.y), width:Math.abs(end.x-start.x), height:Math.abs(end.y-start.y)};
        annotation.draft.kind = annotation.draft.region.width < .012 && annotation.draft.region.height < .012 ? 'point' : 'rect';
        renderNotes();
    }
    stage.addEventListener('pointerdown', event => {
        if(event.button !== 0 || !byId('annotationImage').naturalWidth) return;
        const hit = event.target.closest('[data-annotation-id]');
        const note = hit && notes().find(note => note.id === hit.dataset.annotationId);
        if(note){ selectNote(note); input.focus(); return; }
        event.preventDefault();
        drag = {start:point(event), pointerId:event.pointerId};
        annotation.selected = '';
        annotation.draft = {id:uid('note'),kind:'point',region:{...drag.start,width:0,height:0},text:'',resolved:false,includeInGeneration:true};
        input.value = '';
        byId('annotationInclude').checked = true;
        byId('annotationEditor').hidden = false;
        byId('annotationSave').disabled = false;
        stage.setPointerCapture(event.pointerId);
        renderNotes();
    });
    stage.addEventListener('pointermove', event => { if(drag && event.pointerId === drag.pointerId) updateRegion(point(event)); });
    stage.addEventListener('pointerup', event => {
        if(!drag || event.pointerId !== drag.pointerId) return;
        updateRegion(point(event));
        drag = null;
        stage.releasePointerCapture(event.pointerId);
        status('标记已定位，请填写评论并保存。');
        input.focus();
    });
    stage.addEventListener('pointercancel', () => {drag=null;selectNote(null);});
    function saveNote(){
        const image = targetImage();
        if(!image || !annotation?.draft){status('请先在图片上标记一个位置。');return false;}
        const text = input.value.trim();
        if(!text){status('请填写这处标记的修改意见。');input.focus();return false;}
        pushUndo();
        const next = {...annotation.draft,text:text.slice(0,2000),includeInGeneration:byId('annotationInclude').checked};
        const items = notes().slice();
        const index = items.findIndex(note => note.id === next.id);
        if(index >= 0) items[index] = next; else items.push(next);
        image.annotations = items;
        scheduleSave();
        selectNote(null);
        status('评论已保存到画布。可以继续添加标记。');
        return true;
    }
    byId('annotationSave').addEventListener('click', saveNote);
    byId('annotationCancelDraft').addEventListener('click', () => selectNote(null));
    byId('annotationClose').addEventListener('click', closeAnnotations);
    dialog.addEventListener('cancel', event => {event.preventDefault();closeAnnotations();});
    dialog.addEventListener('keydown', event => {
        // Keep canvas shortcuts (Delete, Ctrl+Z, Space) out of the modal.
        event.stopPropagation();
        if(event.key === 'Escape'){event.preventDefault();closeAnnotations();}
        if((event.ctrlKey || event.metaKey) && event.key === 'Enter'){event.preventDefault();saveNote();}
    });
    list.addEventListener('click', event => {
        const button = event.target.closest('button');
        if(!button) return;
        const id = button.dataset.selectNote || button.dataset.resolveNote || button.dataset.deleteNote;
        const note = notes().find(item => item.id === id);
        if(!note) return;
        if(button.dataset.selectNote){selectNote(note);input.focus();return;}
        const image = targetImage();
        pushUndo();
        image.annotations = button.dataset.deleteNote ? notes().filter(item => item.id !== id) : notes().map(item => item.id === id ? {...item,resolved:!item.resolved} : item);
        scheduleSave();
        selectNote(null);
    });
    byId('annotationApply').addEventListener('click', () => {
        if(annotation.draft && input.value.trim() && !saveNote()) return;
        const current = {...annotation};
        const node = nodes.find(item => item.id === current.nodeId);
        const image = imageForDisplay(targetImage());
        if(!node || !image) return;
        closeAnnotations();
        selectedId = node.id;
        selectedIds = [];
        selectedImage = {nodeId:node.id,index:current.index};
        render();
        updateComposer();
        setPromptCaretToEnd();
        if(!collectMentionedImagesFromPrompt().some(ref => ref.url === image.url)) insertMentionToken({...image,nodeId:node.id,imageIndex:current.index});
        const text = document.createTextNode(' 请根据这张图片的标记评论进行修改。');
        promptInput.appendChild(text);
        setPromptCaretToEnd();
        savePromptDraftForCurrent();
        scheduleSave();
        toast('图片和修改意见已带入，点击运行开始生成');
    });

    async function loadSkills(){
        try {
            const response = await fetch('/api/local-skills');
            if(!response.ok) throw new Error('无法读取本地 Skill');
            skills = (await response.json()).skills || [];
            skillError = '';
        } catch(error){ skillError = error.message; }
        syncSkillControl(selectedNode());
    }
    function syncSkillControl(node){
        const selected = node?.localSkill;
        byId('canvasSkillLabel').textContent = selected?.name || 'Skill';
        skillButton.title = selected ? `${selected.name}：${selected.description || '已启用设计指导'}` : '选择本地设计 Skill';
        skillButton.classList.toggle('has-skill', Boolean(selected));
        if(!picker.hidden) renderSkills();
    }
    function renderSkills(){
        const selected = selectedNode()?.localSkill?.id || '';
        byId('canvasSkillList').innerHTML = `<button type="button" class="canvas-skill-option ${!selected ? 'is-active' : ''}" data-canvas-skill=""><span class="canvas-skill-free">✦</span><span><strong>自由创作</strong><small>仅使用本次提示词和参考图片</small></span></button>` + skills.map(skill => `<button type="button" class="canvas-skill-option ${skill.id === selected ? 'is-active' : ''}" data-canvas-skill="${e(skill.id)}">${skill.cover_url ? `<img src="${e(skill.cover_url)}" alt="">` : '<span class="canvas-skill-free">✦</span>'}<span><strong>${e(skill.name)}</strong><small>${e(skill.description)}</small></span></button>`).join('');
        byId('canvasSkillStatus').textContent = skillError || (!skills.length ? '还没有 Skill，请到首页的 Skills 页面导入。' : '所选 Skill 随当前节点保存，并参与每次生成。');
    }
    function closeSkills(){picker.hidden=true;skillButton.setAttribute('aria-expanded','false');}
    skillButton.addEventListener('click', () => {
        picker.hidden = !picker.hidden;
        skillButton.setAttribute('aria-expanded', String(!picker.hidden));
        if(!picker.hidden){closeMentionPicker();renderSkills();loadSkills();}
    });
    byId('canvasSkillClose').addEventListener('click', () => {closeSkills();skillButton.focus();});
    byId('canvasSkillRefresh').addEventListener('click', loadSkills);
    byId('canvasSkillList').addEventListener('click', event => {
        const button = event.target.closest('[data-canvas-skill]');
        const node = selectedNode();
        if(!button || !node) return;
        const skill = skills.find(item => item.id === button.dataset.canvasSkill);
        pushUndo();
        if(skill) node.localSkill = {id:skill.id,name:skill.name,description:skill.description,content:skill.content};
        else delete node.localSkill;
        closeSkills();syncSkillControl(node);scheduleSave();skillButton.focus();
    });
    picker.addEventListener('keydown', event => {
        event.stopPropagation();
        if(event.key === 'Escape'){closeSkills();skillButton.focus();}
    });
    document.addEventListener('click', event => {if(!event.target.closest('.canvas-skill-control')) closeSkills();});
    byId('canvasMentionButton').addEventListener('mousedown', event => event.preventDefault());
    byId('canvasMentionButton').addEventListener('click', () => {
        closeSkills();
        if(!mentionRange || !promptInput.contains(mentionRange.startContainer)) setPromptCaretToEnd();
        else {promptInput.focus();const sel=window.getSelection();sel.removeAllRanges();sel.addRange(mentionRange);}
        showMentionPicker();
    });
    window.YaoguangCanvas = {
        openAnnotations,loadSkills,syncSkillControl,
        enhanceRequest:(node, request) => YaoguangCanvasContext.enhanceRequest(node,request,allImages())
    };
})();
