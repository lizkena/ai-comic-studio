# 光色层

写光比、色温、光源、调色时读。输入：逐镜摄影卡 + 导演决定书 lock（含档位字段）；输出：每镜光色五项（光源位置与色温 / 综合色三段配比 / 基底 / 高光行为 / 皮肤句）。档位服从决定书，本文不自行改档；导演卡 `lock` 已定数字的以卡为准，本文解释数字为什么长这样。

## 光比表

| 光比 | 场景感 | 典型 |
|---|---|---|
| 2:1 | 平、无阴影、可控舞台 | 韦斯盒、广告回避带 |
| 3:1 | 自然、可读、温和 | 日光戏、李安客厅、侯孝贤 |
| 4:1 | 有立场的日光/实用光 | 张艺谋外景、小丑街道、斯皮尔伯格门廊 |
| 5:1 | 戏剧化、开始有夜 | 斯科塞斯酒吧、希区柯克窗光 |
| 6:1–7:1 | 硬、罪、压迫 | 芬奇走廊、朴赞郁侧光 |
| 8:1+ | 霓虹夜、极端实用光 | 王家卫走廊 |

规则：光比是**结构**不是调味——同一场戏内保持；跨场变化对应剧情刻度。

## 硬源与软源

| | 硬 | 软 |
|---|---|---|
| 来源 | 裸灯泡、直射太阳、射灯 | 大面积、阴天、霓虹管、窗纱后 |
| 效果 | 硬边影、高光比 | 边界渐变、包络 |
| 用途 | 轮廓、张力的边 | 染色、包络、氛围 |

常见错误：指望霓虹管给硬影——霓虹是线状软源，只负责染色勾边；要硬边用裸灯泡或招牌直射。

## 色温锚点

| K | 光 | 情绪 |
|---|---|---|
| 1800–2000 | 烛/火焰 | 古老、亲密 |
| 2700–2800 | 钨丝、灯笼 | 暖家、怀旧、亚洲室内 |
| 3200 |钨丝灯（标称）| 标准暖室内 |
| 4500 | 黄昏/晨光 | 过渡、愁绪 |
| 5600 | 日光 | 中性外景 |
| 6500+ | 荧光、阴天、青天 | 冷、制度、病态 |

混温是语言不是错误：钨丝内 + 青窗外 = 内外两个世界（王家卫、小丑都在用）。但**一场戏内主光逻辑只有一个**——其余是点缀，不许五五开。

## 材料色 vs 滤色

颜色必须由画面里的实物承担：布、墙、服装、灯笼、粮食。

- 材料色白天成立；滤色（后期拉色）白天就穿帮。
- 检验法：关掉这盏灯/拿走这块布，颜色还在吗？在 = 材料色；不在 = 滤色，重做。
- 张艺谋的红是染布和漆墙，不是红灯；王家卫的绿是霓虹污染墙面——污染也要有墙面这个载体。

## 综合色配比（70/20/10）

设计期用三段配比：主色场 / 阴影或中性 / 点缀。

- 主色 ≥60% 才叫「场」；30–50% 是「主导色」不是色场。
- 点缀 ≤10% 才有重音作用；两处点缀已饱和。
- 配比是**内部纪律**，保证跨镜一致与换卡测试可判读；跨镜色场漂移时回此表对账。

发射翻译（写进提示词时）：删掉数字，换成 **6–9 个按主导度排序的具体色名列表**，每个色名挂在真实材料上，可保留一句面积锚。数字留给设计，色名给模型——主流后端对 `warm amber fallen leaves, deep red leaf drift in shadow, dark moss green shade closing the far end` 这类色名+材料有强先验，对 `50/30/20` 没有任何先验。

```
Palette: desaturated jade green, moss green, olive, smoky mint, dark pine, muted brown violet
```

一个色名一个材料，不写 `colorful cinematic`。同场多镜共用同一条色名列表，只改材料状态。

## 高光与皮肤

- 高光滚落：柔、贵、现代——默认「电影感」其实是廉价柔光。
- 高光硬切：胶片直出、有骨头——张艺谋外景、芬奇湿面。
- 皮肤写法对照：`natural skin texture` 好；`flawless glowing skin` 除非广告，否则毁掉一切写实基底。
- 颗粒：细不均 = 35mm 真感；粗 = 16mm 纪录；均匀 = 数码噪点（错）。

## 基底现象链（发射配方）

`substrate` 不是标签，是一条**可见现象链**。每张卡的基底在发射时扩成 6–7 个独立可见现象，整链附在提示词尾部收束风格；行话参数（`medium-low microcontrast` 类）留在设计层，不发射。

现象链零件表（每卡选 6–7 项，按卡基底拼装）：

| 类别 | 可见现象（发射用语） |
|---|---|
| 年代+载体 | `early 2000s 35mm theatrical frame` / `1990s Hong Kong film print` / `1990s print LUT` / `16mm TV transfer` |
| 色彩密度 | `strong photochemical color density` / `dye-like color thickness, adjacent tones bleeding into each other` |
| 高光行为 | `warm halation on highlights` / `gently clipped highlights, no hard digital cut` / `highlights blooming slightly` |
| 暗部行为 | `colored blacks, never pure black` / `thick dense shadows holding texture` |
| 光学柔度 | `visible lens softness, pores and fabric fibers not razor sharp` / `slight optical softness of an old lens` |
| 空气层 | `atmospheric haze, distant detail fading through air` |
| 颗粒 | `organic grain heavier in shadows and midtones, highlights cleaner` / `fine uneven grain` |
| 通道互染 | `subtle dye-channel blending` / `green spike kept in shadows and highlights`（数字 LUT 卡） |
| 皮肤 | `unretouched skin, real pores` / `lived-in skin, faint fatigue` |

拼装规则：载体句开头、皮肤句居中或靠后、颗粒句收尾；一张卡一条链，跨镜不换链。

## 静帧光色编译顺序

光源位置与色温 → 色名列表（6–9 色名+材料，面积锚一句）→ 基底现象链 → 高光行为（已在链内）→ 皮肤句（已在链内）。五项齐才是一条完整的光色描述，缺项就是给模型留随机空间；发射前对照本表逐项打勾。
