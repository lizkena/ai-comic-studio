# 视频动作与运镜

要视频提示词、图生视频方案或真出视频时读。本文做的是把导演意图编译成可执行的文字，不是任何服务的接口手册。

只要提示词就停在文字，不自动出图出片、不代购服务。后端没指定时用中立写法，参数标注待适配（各视频后端能力见 backends.md 视频节）。已加载导演卡时：短提示词必须携带卡内签名的**可见结果**（画幅、遮挡与机位行为、明暗分布、基底现象），lock 数字本身不进短提示词——与静帧的术语纪律同一条；先套卡内「标准视频」句式，再换入本镜动作。

## 第一步：判定帧角色

别信文件名或上一轮的说法，看图本身：

| 帧角色 | 提示词怎么落笔 |
|---|---|
| start | 从该动作的起点启动 |
| mid | 接着当前阶段演，禁止倒带重演 |
| end | 写下一步或原地停留；要完整前序就另配首帧 |
| reference | 只供构图/身份，不能冒充首帧 |

两人手里已经是同一把伞 → 写「握紧—松手」，不写「走近、找伞、递伞」。门已经合上就不能再关一次。人已经回过头，就保持回望或转回去，不许从朝前状态再回一次头。

画幅没露出的脚和手，不算已核验。关键动作压在这些区域时，先补一帧可见的起始状态，或只设计现有构图撑得住的动作。

九宫格/三联等宫格合成图（B 轨交付物或草稿）不能整张当某颗镜头的首帧；转视频前按格拆回独立镜头，或对关键格走 grid.md「B→A 补强」拿到独立高清帧再作首帧。

## 导演控制卡

卡留在内部，别整张塞进短提示词；简单镜头可并字段。

```
shot_id / 来源节拍 / 信息目的
输入：路径；start|mid|end|reference；可见状态
前提：依赖镜、人物/道具 ID、空间假设
节奏：建议剪辑时长；起势→主事件→落点
主体：谁；世界方向与屏幕方向；一个主事件；完成条件
摄影机：站位/拍向/高度；景别
运镜：方式；相对谁；路径；终点构图；何时停
焦点：固定，或一次有意义的转移；与机位运动分开写
环境：必要的雨/风/背景动作，不抢主事件
首态→尾态：数量、持有人、位置、姿态、开合
衔接：出入画方向；动作匹配/视线/重建空间/跳时
后端：已选或未指定；能力已核验/未核验
验收：关键可见证据、失败条件、未知项
```

`planned_duration` 属于剪辑设计；`generation_duration` 是后端交出的实际时长。没有对应接口，就不承诺精确到米、角度、帧、秒。时间顺序优先用「先—随后—最后」表述。

## 运镜：先问目的，再报名词

一段默认一个主事件、一个主运镜；固定机位同样成立。用户要复杂长镜头就按需组合，不硬拆成九镜。

| 方式 | 必须交代 | 不许冒充 |
|---|---|---|
| 固定 locked-off | 机位与拍向稳定；主体可以动 | 画面里万物静止 |
| 推/拉 dolly | 相对主体靠近/远离；收在什么景别 | 变焦 |
| 横移 truck | 沿哪一侧；与主体同向还是各自走；走多远 | 原地摇摄 |
| 摇摄 pan/tilt | 机位不动；从哪个可见目标扫到哪个 | 横移/升降 |
| 升降 pedestal/crane | 机位升或降；拍向变不变；新露出什么 | 拿上摇冒充越墙航拍 |
| 弧线 arc | 绕什么转；从哪侧到哪侧；背面露不露 | 没有定义的「环绕 360°」 |
| 变焦 zoom | 机位钉死、视角收放 | Dolly zoom 是另一套组合 |
| 拉焦 rack focus | 焦点从谁身上换到谁身上；两人都得在画内 | 移机或移物 |
| 手持/跟随 | 谁的视点；距离与落点 | 同时要「完全锁死」又「明显晃动」 |

主体方向挂参照物：「画面中从左向右走」「摄影机在桥近侧平行跟拍」。短提示里把内部 ID 翻译成首帧认得出的位置/服装，不让后端猜 A 是谁 B 是谁。

手绘/动画照旧区分相机意图与角色动作，不因几个摄影术语就被改成真人或三维。

## 短提示词编译

图生视频只写首帧之后发生的事，不复述画面里已有的脸、房间、画风。常规 3–6 句：

```
[一个主摄影机行为，带方向与目标；固定就先写锁定。]
[首帧认得出的主体，从当前阶段完成一个主事件。]
[一条必要的空间/道具连续事实。]
[必要的焦点安排或轻微环境运动。]
[可见的落点或结束状态。]
```

文生视频另补必要的外观与场景。导演意图（压迫、暧昧、释然）要翻译成看得见的距离、停顿、构图；不许拿 `cinematic camera movement` 顶替设计。

约束写成事实句：「the single umbrella ends in the right-hand traveler's hand」。后端支持时才另给负面字段。

## 剪辑

一颗镜头内部状态可以随动作演化，但不得靠换脸、凭空添物、重建建筑来「完成」动作。

- 交接：原持有人 → 双手共同接触 → 接收人独持；尾帧里交出方必须空手
- 行走：脚要落地、路径要通得过去；位移不许靠背景整体平移
- 相机推近时，人不该突然放大或朝镜头冲刺
- 拉焦不该把后景的人挪进前景，也不该抹掉前景物
- 九颗分镜各自独立生成再剪；换机位就是切镜，不拿相邻两颗不同机位的图当同镜首尾去插值

每个切点核对：位置与持有物、视线、出入画方向、动作阶段、光线与时间。匹配剪辑允许短促重叠，但不许完整重演交接或开门。跨轴要么重建空间、要么连续越轴。刻意跳切/倒叙按用户设计标注。

**J/L cut**：声音先于画面入场（J），或画面切走后声音拖尾（L）。写法：`audio of the next scene begins 1s before the cut` / `his footsteps continue 1s over the next shot`。用在换场的呼吸与信息前置；同场紧张段落不用。

**动作匹配重叠上限**：切点两侧动作重叠 ≤30%——抬手切到手已举过半，可以；完整重演一遍开门，不行。写法：`match cut on the mid-swing of the arm`。

**whip pan**：两端必须是预先设计好的落幅，不是甩出去的补救。写法：`whip pan from his face to the doorway; motion blur only in the middle 20%; both end frames fully composed`。落幅即下一镜首帧。

音效、对白、音乐，只在被要求或原故事需要时补。原对白扛着关键剧情时，不因「纯视觉」而删除。

没生成过视频，只能标「提示词已检查，运动未验证」。

## 写法对照

### mid：从共同接触继续

输入：两人手里已经各握着同一只木盒的一端。

> Locked medium close-up from the table's end. The diner in the nearer seat takes the full weight of the wooden box with both hands. The diner across the table lets her fingertips leave the lid and rests her open palm flat on the wood. One box, four hands, then two. The camera does not move.

禁：起身去拿、先收回再交、凭空多出第二只盒子。

### 推近 ≠ 拉焦

推近（人原地不动）：

> The camera glides forward about one slow pace toward the boy at the workbench, tightening from a medium shot to a medium close-up. He stays on his stool and turns his head from the half-built kite to the tools at his elbow. Focus holds on his face throughout.

拉焦（机位钉死）：

> Locked framing: a chipped teacup fills the near ground, the old woman already seated in soft focus beyond it. Focus travels from the cup's rim to her face as she sets down her needlework. Neither the cup nor the woman changes position. The camera never leaves its mark.

后景主体压根不在首帧里时，先修首帧，别指望拉焦把他「生成」出来。

### 单图室内：同侧小位移

输入只有厨房正面一图。

> Keeping to the front of the kitchen it can actually see, the camera drifts a short distance to its left and eases to a stop on the father ladling soup for the two children. The range hood stays above the stove; the doorway stays at the far right. The move ends while every wall still belongs to the visible side.

用户点名要 180° 环绕时，不许悄悄拿本例顶替；先标注缺背面依据。

## 交付

1. 整段轴线/节奏各一句
2. 每镜一张导演卡 + 一条独立可复制的短提示词；九镜不共用一句运镜
3. 已定参数、待适配项、风险；写明是「提示词检查」还是「已生成并检查」
