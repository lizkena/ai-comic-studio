export function createMcpSettings({state,api,esc,icon,render,toast}){
 let data=null,busy=false;
 async function load(){data=await api('/mcp/status');}
 function view(){
  const rows=data?.clients||[];
  return `<main class="content"><div class="stagehead"><div><div class="eyebrow mb">WORKSPACE MCP</div><h1>工作台 MCP</h1><p class="help">让外部智能体读取画布、编辑卡片、连接素材并提交制作任务。</p></div><button class="ghost small" data-action="mcp-refresh">${icon('refresh')}刷新状态</button></div><div class="mcp-client-list">${rows.map(c=>{
   const label=c.connected?'已连接':c.configured?'已配置 · 等待客户端刷新':'未连接';
   return `<article class="mcp-client-card"><div class="mcp-client-heading"><div><h2>${esc(c.name)}</h2><p class="help">${c.installed?'已检测到客户端':c.id==='antigravity'&&data.downloaded?'官方安装包已下载，待安装':'尚未检测到客户端'}</p></div><div class="mcp-client-actions"><span class="mcp-status ${c.connected?'connected':''}" role="status">${esc(label)}</span><button data-action="mcp-configure" data-client="${c.id}" ${busy?'disabled':''}>${c.configured?'更新配置':'连接'}</button></div></div><details><summary>配置与连接说明</summary><p class="help">连接按钮只添加本工作台，不覆盖其他 MCP。保存后请在客户端刷新 MCP 或重启客户端，实际握手后才会显示已连接。</p><p class="help">配置位置：${esc(c.path)}</p><pre class="mcp-config">${esc(c.config)}</pre><button class="ghost small" data-action="mcp-copy" data-client="${c.id}">复制配置</button></details></article>`;
  }).join('')||'<p>正在读取客户端状态…</p>'}</div><section class="panel mt"><h3>可以让智能体做什么</h3><p class="help">读取项目与素材、创建角色/身份/场景/道具/镜头卡、修改提示词和连线。图片及视频生成会使用本平台配置的渠道；仅在你明确要求实际生成时提交，并查询真实结果回填。</p><p class="help">MCP 服务仅连接本机工作台，不需要把模型 API 密钥复制给客户端。</p></section>${data?.downloaded?'<section class="panel mt"><h3>Google Antigravity</h3><p class="help">官方 Windows x64 安装包已保存。安装并登录后，在客户端刷新工作台 MCP 配置。</p><a class="mcp-download" href="/api/mcp/installer" download>下载 Antigravity 安装包</a></section>':''}</main>`;
 }
 async function action(name,el){
  if(name==='mcp-refresh'){await load();render();return;}
  const client=el.dataset.client;
  if(name==='mcp-copy'){await navigator.clipboard.writeText(data.clients.find(c=>c.id===client).config);toast('配置已复制');return;}
  if(name==='mcp-configure'){
   busy=true;render();
   try{const result=await api('/mcp/configure/'+client,'POST',{});await load();toast(result.message);}
   finally{busy=false;render();}
  }
 }
 setInterval(async()=>{if(state().page!=='mcp'||busy)return;try{const previous=JSON.stringify(data);await load();if(previous!==JSON.stringify(data))render();}catch{}},5000);
 return {view,load,action};
}
