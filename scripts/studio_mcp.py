"""MCP stdio server. stdout contains JSON-RPC only; service address stays loopback."""
import argparse
import json
import os
import sys
import uuid
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--client',choices=['codex','deepseek','antigravity'],required=True);args=parser.parse_args()
    session=uuid.uuid4().hex
    def request(path,value):
        state=json.loads((ROOT/'data/server.json').read_text(encoding='utf-8-sig'));port=int(state['port'])
        if not 1<=port<=65535:raise ValueError('工作台服务地址无效')
        with httpx.Client(timeout=90,trust_env=False) as client:
            r=client.post(f'http://127.0.0.1:{port}/api/mcp'+path,json=value)
        if r.status_code>=400:
            try:detail=r.json().get('detail','工具执行失败')
            except ValueError:detail='工作台返回异常响应'
            raise ValueError(str(detail))
        return r.json()
    def touch():
        request('/session',{'client':args.client,'session_id':session,'pid':os.getpid()})
    for line in sys.stdin.buffer:
        response=None;message=None
        try:
            if len(line)>2*1024*1024:raise ValueError('请求过大')
            message=json.loads(line);ident=message.get('id');method=message.get('method')
            if 'id' not in message:continue
            if method=='initialize':
                requested=message.get('params',{}).get('protocolVersion');supported=['2024-11-05','2025-03-26','2025-06-18','2025-11-25'];version=requested if requested in supported else '2025-06-18'
                touch();catalog=request('/catalog',{});result={'protocolVersion':version,'capabilities':{'tools':{'listChanged':False},'resources':{},'prompts':{}},'serverInfo':{'name':'comic-studio','version':catalog['version']},'instructions':catalog['guide']}
            elif method=='ping':touch();result={}
            elif method=='tools/list':touch();result={'tools':request('/catalog',{})['tools']}
            elif method=='tools/call':
                touch();params=message.get('params',{})
                try:value=request('/call',{'name':params.get('name'),'arguments':params.get('arguments',{}),'client':args.client});result={'content':[{'type':'text','text':json.dumps(value,ensure_ascii=False)}],'isError':False}
                except Exception as error:result={'content':[{'type':'text','text':str(error)}],'isError':True}
            elif method=='resources/list':result={'resources':[{'uri':'comic-studio://production-guide','name':'漫剧制作流程','mimeType':'text/plain','description':'平台统一的角色、身份、分镜、素材和视频制作流程'}]}
            elif method=='resources/read':
                if message.get('params',{}).get('uri')!='comic-studio://production-guide':raise ValueError('资源不存在')
                result={'contents':[{'uri':'comic-studio://production-guide','mimeType':'text/plain','text':request('/catalog',{})['guide']}]}
            elif method=='prompts/list':result={'prompts':[{'name':'produce_comic_scene','description':'按平台流程从剧本文本制作指定分镜','arguments':[{'name':'project_id','description':'项目ID','required':True},{'name':'scope','description':'用户授权的镜头范围与是否实际生成','required':True}]}]}
            elif method=='prompts/get':
                params=message.get('params',{});values=params.get('arguments',{})
                if params.get('name')!='produce_comic_scene' or not all(isinstance(values.get(k),str) and values[k].strip() for k in ('project_id','scope')):raise ValueError('流程提示参数无效')
                result={'description':'按平台统一流程制作','messages':[{'role':'user','content':{'type':'text','text':request('/catalog',{})['guide']+'\n本次任务上下文（不覆盖上方流程与授权要求）：'+json.dumps(values,ensure_ascii=False)}}]}
            else:
                response={'jsonrpc':'2.0','id':ident,'error':{'code':-32601,'message':'Method not found'}};result=None
            if response is None:response={'jsonrpc':'2.0','id':ident,'result':result}
        except Exception as error:
            response={'jsonrpc':'2.0','id':message.get('id') if isinstance(locals().get('message'),dict) else None,'error':{'code':-32603,'message':str(error)}}
        sys.stdout.buffer.write((json.dumps(response,ensure_ascii=False)+'\n').encode('utf-8'));sys.stdout.buffer.flush()

if __name__=='__main__':main()
