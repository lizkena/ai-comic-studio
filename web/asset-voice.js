export const voiceLabel = asset => asset.voice ? '音色已绑定' : '音色未绑定';

export function bindVoice(project, asset, sound) {
 if (asset.kind !== 'character') throw Error('只有角色可以绑定音色');
 const file=sound?.file||null;
 if (asset.voice===file) return false;
 asset.voice=file;
 asset.voice_library_id=sound?.id||'';
 asset.voice_library_version=sound?.version||null;
 delete asset.voice_profile;
 asset.version=(asset.version||0)+1;
 for (const segment of project.segments) {
  if (segment.character_ids?.includes(asset.id)) segment.status='stale';
 }
 return true;
}

export function voicePanel(asset, sounds, esc, icon) {
 const selected=sounds.find(x=>x.file===asset.voice);
 return `<section class="wf-voice-binding"><div class="row between"><h3>音色绑定</h3><span class="wf-voice-status ${asset.voice?'ready':''}">${icon(asset.voice?'check':'mic')}${voiceLabel(asset)}</span></div><label for="wf-voice-select">绑定音色</label><div class="wf-voice-controls"><select id="wf-voice-select" data-flow-voice="${esc(asset.id)}"><option value="">未绑定</option>${asset.voice&&!selected?`<option value="current" selected>已绑定声音素材</option>`:''}${sounds.map(x=>`<option value="${esc(x.id)}" ${selected?.id===x.id?'selected':''}>${esc(x.name)}</option>`).join('')}</select><button data-flow="voice-preview" data-id="${esc(asset.id)}" ${asset.voice?'':'disabled'}>试听音色</button><button data-flow="voice-clear" data-id="${esc(asset.id)}" ${asset.voice?'':'disabled'}>解除音色绑定</button></div><div id="wf-voice-audio">${asset.voice?`<audio controls preload="none" src="/media/${encodeURIComponent(asset.voice)}" aria-label="角色音色试听"></audio>`:''}</div><label class="wf-upload">${icon('folder')}上传音色素材<input type="file" data-flow-voice-upload="${esc(asset.id)}" accept="audio/wav,audio/mpeg,audio/mp4,audio/ogg"></label><p class="help">声音仅作角色音色参考，角色对白由 H3 生成。</p></section>`;
}
