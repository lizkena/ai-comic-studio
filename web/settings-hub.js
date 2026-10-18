export function createSettingsHub({state, icon, render, api, apiView, h3View}) {
  const sections = [['appearance','外观','eye'],['api','模型 API','cloud'],['h3','本地 H3','chip']];
  function view() {
    const section = state().settingsSection || 'appearance';
    return `<main class="content settings-hub"><div class="stagehead"><div><div class="eyebrow mb">WORKSPACE SETTINGS</div><h1>设置</h1><p class="help">管理工作台外观、模型服务与本地视频引擎。</p></div></div>
      <div class="settings-layout"><nav class="settings-menu" aria-label="设置栏目">${sections.map(([id,name,symbol]) => `<button data-action="settings-section" data-section="${id}" class="${section === id ? 'active' : ''}" ${section === id ? 'aria-current="page"' : ''}>${icon(symbol)}${name}</button>`).join('')}</nav>
      <section class="settings-detail" aria-label="${sections.find(x => x[0] === section)?.[1] || '外观'}">${section === 'api' ? apiView() : section === 'h3' ? h3View() : appearance()}</section></div></main>`;
  }
  function appearance() {
    const selected = window.comicTheme.get();
    return `<h2>外观</h2><p class="help mb">选择日间或夜间模式，立即应用到整个工作台，下次打开时保留。</p><div class="theme-options" role="group" aria-label="日夜模式">${[['light','日间模式','适合明亮环境'],['dark','夜间模式','适合低光环境'],['system','跟随系统','自动跟随 Windows 外观']].map(([id,name,note]) => `<button class="theme-option ${selected === id ? 'selected' : ''}" data-action="theme-select" data-theme="${id}" aria-pressed="${selected === id}"><span class="theme-preview preview-${id}" aria-hidden="true"><span></span><span></span><span></span></span><strong>${name}</strong><span class="help">${note}</span>${selected === id ? `<span class="theme-selection">${icon('check')}当前选择</span>` : '<span class="theme-selection">点击切换</span>'}</button>`).join('')}</div><div class="notice info mt">主题仅保存在当前工作台窗口的本机配置中，不会更改模型、密钥或项目内容。</div>`;
  }
  async function select(section) {
    if (!sections.some(x => x[0] === section)) return;
    if (state().settingsSection === 'api') {
      state().toolDraft = {ffmpeg:document.getElementById('ffmpeg-path')?.value ?? state().settings.ffmpeg,ffprobe:document.getElementById('ffprobe-path')?.value ?? state().settings.ffprobe};
    }
    state().settingsSection = section;
    render();
    if (section === 'h3') {
      const [hardware, deployment, service] = await Promise.all([api('/hardware'),api('/deployment'),api('/deployment/service/status')]);
      Object.assign(state(), {hardware,deploy:deployment,h3Service:service});
      if (state().page === 'settings' && state().settingsSection === 'h3') render();
    }
  }
  function theme(value) {window.comicTheme.set(value);render();}
  return {view, select, theme};
}
