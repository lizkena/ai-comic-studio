from . import domain, store


def make_sample():
    p=domain.project_new({'name':'雾港来信','source':'在终年被雾笼罩的港口，一位能听见旧信声音的邮递员，收到了未来的自己寄来的一封信。','settings':{'genre':'悬疑 / 奇幻','style':'东方幻想 · 电影感动漫','episode_duration':40}})
    p['sample']=True
    p['outputs']['direction']={'logline':'一封来自未来的信，让年轻邮递员决定走进一座即将消失的灯塔。','theme':'选择与记忆','genre':'悬疑 / 奇幻','conflict':'相信预言逃离港口，还是留下来救回失踪的父亲。','synopsis':'凌晨四点，林舟在邮袋里找到一封没有邮戳的信。信上的字迹与自己相同，日期却是三天之后。远处废弃灯塔突然亮起，信里传来父亲的声音。','constraints':['全片发生于雾港','角色不超过三人']}
    c={'id':store.uid('character'),'name':'林舟','aliases':['邮递员'],'goal':'找到失踪的父亲','secret':'能听见旧信里的声音','relationships':'与父亲多年失联','arc':'从被动送信变为主动选择','description':'年轻男性，黑发，深灰长外套，斜挎旧邮袋','variants':[{'id':store.uid('variant'),'name':'雾港 / 日常','description':'深灰长外套，旧皮邮袋'}]}
    p['outputs']['characters']={'characters':[c]}
    location={'id':store.uid('location'),'name':'雾港码头','description':'潮湿石板、旧码头与远处灯塔，冷青色雾气中有琥珀色灯光'}
    p['outputs']['world']={'locations':[location],'organizations':[],'rules':['旧信保留写信人当时的声音'],'props':[{'id':store.uid('prop'),'name':'未来来信','description':'泛黄信纸，无邮戳，未来日期'}]}
    chapter={'id':store.uid('chapter'),'title':'第一章 · 无邮戳的信','content':'天还没亮，雾港的石板路就已经湿透了。林舟摸索着邮袋里的最后一封信，指尖触到一个陌生的日期。\n\n三天之后。\n\n他停下脚步。信封里的声音轻轻响起：“不要去灯塔。”可那是父亲的声音。\n\n港口尽头，一束光缓缓划过浓雾。废弃了十年的灯塔，亮了。','summary':'林舟发现未来来信，听见父亲的声音。','character_states':'林舟：疲惫转为警觉；父亲：仅声音出现'}
    p['outputs']['novel']={'outline':[{'title':chapter['title'],'summary':chapter['summary']}],'chapters':[chapter]}
    episode={'id':store.uid('episode'),'title':'第01集 · 无邮戳的信','scenes':[]}
    for i,(title,action,line) in enumerate([('雾中的邮递员','林舟沿潮湿码头前行，手指收紧邮袋肩带。',''),('来自未来','林舟拆开信封，日期特写。远处传来钟声。','不要去灯塔。'),('灯塔亮起','林舟抬头望向灯塔，停顿后转身迈向港口尽头。',''),('选择','邮袋撞上腰侧，他穿过雾气。灯塔的暖光掠过面颊。','我会找到你。')]):
        scene={'id':store.uid('scene'),'title':title,'location':location['name'],'time':'凌晨','interior':'外','goal':'推动悬念','conflict':'信件的警告与寻找父亲的愿望','turn':'灯塔突然亮起','duration':10,'source_chapters':[chapter['id']],'action':action,'dialogue':[{'character':'林舟','text':line}] if line else [],'sound':'海浪、风与远处钟声','transition':'切'}
        episode['scenes'].append(scene)
    p['outputs']['script']={'episodes':[episode]}
    domain.derive_assets(p)
    for i,scene in enumerate(episode['scenes']):
        segment={'id':store.uid('segment'),'title':f'{i+1:02d} · '+scene['title'],'scene_id':scene['id'],'episode_id':episode['id'],'duration':10,'character_ids':[c['id']],'variant_ids':[c['variants'][0]['id']],'location_id':location['id'],'prop_ids':[],'continuity':bool(i),'previous_id':p['segments'][-1]['id'] if i else None,'tail_shot':True,'seed':42,'prompt':scene['action']+' 冷青色雾气，琥珀色灯塔光线。','shots':[{'start':0,'end':5,'size':'中景','camera':'缓慢跟拍','action':scene['action'],'dialogue':'','sound':scene['sound']},{'start':5,'end':9,'size':'特写','camera':'固定','action':'眼神、手部细节','dialogue':scene['dialogue'][0]['text'] if scene['dialogue'] else '','sound':'海浪'},{'start':9,'end':10,'size':'中全景','camera':'固定','action':'关系镜，人物位于画面左侧，朝向灯塔，码头栏杆在前景','dialogue':'','sound':'风'}],'status':'draft','versions':[],'current_version':None}
        p['segments'].append(segment)
    p['outputs']['storyboard']={'segments':p['segments']}
    p['outputs']['performance']={'beats':[{'id':store.uid('beat'),'scene_id':episode['scenes'][1]['id'],'character_id':c['id'],'breath':'短暂屏息后浅呼吸','gaze':'先看日期，再移向灯塔','weight':'重心从后脚移向前脚','hands':'指尖缓慢捏紧信纸','rhythm':'停顿两拍','subtext':'他希望警告是错的'}]}
    p['stage_status']={key:'draft' for key in p['outputs']}
    return p
