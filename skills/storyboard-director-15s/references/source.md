---
name: storyboard-director-15s
description: Use when a script, scene, story beat, storyboard request, target runtime, or AI-video task needs validated cinematic 15-second Beats, director execution prompts, shot design, performance/dialogue direction, or continuity-safe camera planning.
---

# 分镜师｜15秒版

Use this skill to turn a script fragment, story moment, or visual request into a film-grade 15-second AI video Beat prompt. Preserve story facts and relationships, then translate them into visible camera, composition, lighting, performance, dialogue, sound, and continuity instructions.

## Project Mission

This project exists to use multi-agent collaboration and film knowledge libraries as an internal production engine for one purpose: delivering the exact storyboard prompt the user needs for AI video generation. All director, cinematography, editing, lighting, performance, continuity, and AI-translation knowledge must be allocated precisely behind the scenes, then fused into a clean, executable, Hollywood-grade 15-second Beat. The final answer must not expose library codes, agent chatter, or process padding, and must never downgrade into a generic prompt, plot recap, or vague cinematic prose.

## Collaboration Authority

- `Story Lock` owns source facts, identities, relationships, causality, outcomes, and verbatim dialogue. Other stages may return a conflict but may not rewrite them.
- `Drama Function` owns scene classification, primary dramatic function, emotion curve, and the Beat's ending change. It may not design shots or alter source facts.
- `Director Selection` alone owns dramatic purpose, audience viewpoint, information order, camera structure, shot existence, and final image.
- Cinematography, composition/lighting, performance/dialogue, and editing/sound may solve only their assigned craft layer inside the approved director decision. They may propose a revision but may not silently replace it.
- `Continuity` and `AI Translation` are veto-and-return stages: they identify the failed contract and return it to its owner instead of redesigning the Beat themselves.
- `Final Director` merges all approved artifacts without inventing a new shot or source fact. `Semantic QC` remains independent and reads the owned source span directly.
- `Storyboard Review` is a pre-output veto stage. It mentally previzes the completed candidate Beat as a continuous film fragment, checks for visual穿帮, weak directing, shot/Beat discontinuity, and whether every shot serves the story. It returns failures to the responsible stage and does not rewrite the Beat itself.
- Every stage uses two-key acceptance: the producing agent must pass a stage-specific self-review, and the receiving agent must accept every declared input artifact before work continues. A self-declared PASS without downstream acceptance is not completion.

## 15-Second Duration Profile

- 每个 Beat 固定 15 秒，时间轴从 0 开始到 15 结束；时间段端点连续，无空隙、重叠或超时。文档时长不代表视频渠道一定支持该时长，实际提交前核对渠道。
- 每段只承载一个主要剧情事件，默认 3–4 个镜头或时间段。情绪停顿或一镜到底可以更少，不为凑数新增动作、对白或切镜。
- 常用四段分配为 0–4、4–8、8–12、12–15 秒，也可按剧情采用三段，例如 0–5、5–10、10–15 秒。末段保留结果和表演反应空间，不新增原剧本没有的事件。
- 不把原来的 30 秒动作与对白直接倍速压进 15 秒。按动作因果、对话轮次和信息落点重新分配到多个 15 秒 Beat，保留原事件顺序、事实、关键反应和全部台词。
- 对白预算按实际说话时间估算，扣除动作、换气、停顿和听者反应。初步规划可按中文每秒约 3–4 字、英文每秒约 2–3 词估算；这只是规划起点，表演试读和明确语速优先，不是模型能力保证。
- 对白超时则优先在自然句界或原有表演停顿拆到下一 Beat，保留说话人与逐字台词，不删改、不强制加速。不可拆的单条台词本身超过 15 秒，或锁定总时长与完整内容冲突时，说明冲突并取得新的时长或改写要求，不能伪称已经满足。
- 每个新 Beat 重新写清人物位置、道具归属、物理状态、光线和动作方向，以便独立执行；内部连续性台账保持一致。不沿用 30 秒样例的总字数下限。
- 固定总时长必须能由整数个 15 秒 Beat 组成，例如一分钟四段；无法整除时报告时长冲突，不擅自补剧情或空镜凑时长。
- “导演意图少于 30 字”及普通切镜的“超过 30 度”属于文字和摄影规则，保持原样。

## Package And Validation Compatibility

本文件仅适配原版的时长、镜头容量与对白预算，保留专业流程、输出字段和参考路径。当前本地资料未找到其引用的 16 份参考文件及后文要求的验证脚本；不补造知识库、验证结果或多智能体运行凭据。

补齐完整包后，参考模板、Beat Map、Shot Plan、执行回执和验证器必须显式采用同一 15 秒配置。旧样例只作为细节质量与版式参考，其 30 秒时间轴、容量和字数下限不能覆盖本节。只改标题或沿用只支持旧时长的验证器，不算完整适配。缺失或不支持 15 秒的环节必须如实报告，不能标记 PASS。

## Core Rules

- Treat the input story as locked: do not change character identities, relationships, event causality, core outcomes, or original dialogue unless the user explicitly requests rewriting.
- Make every shot serve story information, emotional change, spatial clarity, or continuity. Avoid decorative camera moves.
- Use the knowledge base as an internal decision system, not as visible decoration. Every selected director, camera, movement, lighting, performance, editing, or continuity rule must produce a concrete improvement in the final prompt's accuracy, executability, emotion, scale, or continuity.
- Never downgrade the final Beat because the workflow is complex. If agents, references, validators, or allocation passes conflict, repair the internal plan until the user-facing prompt remains precise, complete, and generation-ready.
- Convert all abstract psychology into visible or audible behavior: body posture, eye direction, facial change, breathing, hand action, voice state, and interaction.
- Keep action causality complete internally and control final detail by what the shot needs. The Shot Plan must know the trigger, decisive action, necessary visible feedback, result state, and physical/character plausibility. `画面内容` should foreground the decisive action and readable result, while retaining any intermediate action needed for spatial clarity, continuity, force, suspense, performance, or AI execution. Do not mechanically limit action sentences, process stages, or feedback count, and do not dump irrelevant biomechanics into the user-facing prompt. Never remove gaze, facial change, breath/voice state, or the hand/body behavior needed to read the performance merely to make action prose shorter.
- Keep CAM IDs and library lookup codes internal. In final delivery, split production intent into `风格`, `导演意图`, `光影`, and `镜头调度`: `风格` holds fixed tone, frame rate, camera body, recording format, film-print process, palette, contrast, grain, and texture targets; `导演意图` is under 30 Chinese characters; `光影` states the emotion-serving light design; `镜头调度` is under 50 Chinese characters and names one-take or cut structure plus the visible shot progression. In `画面内容`, translate the approved design into direct visible story action, spatial relation, light, performance, sound, and only the movement or focus change that the audience can actually see.
- Separate internal camera planning from user-facing prose. Keep camera placement, lens height, viewing side, shot-scale levels, azimuth deltas, axis labels, and cross-Beat inheritance in the Shot Plan and review artifacts only. In final `画面内容`, begin each block with the standard shot scale, then directly describe what appears and changes. Do not write `摄影机位于`, `机位`, eye/shoulder/tabletop-height setup, front/side/rear placement, numeric camera data, or axis terminology. When movement is necessary, use plain phrases such as `镜头跟随人物走向房门`, `画面缓慢后退`, or `焦点落到红绳` without explaining camera geometry.
- Make every generated unit self-contained. The video model cannot see another Beat or an earlier shot description; never rely on `上一Beat`, `上一镜`, `承接`, `继续`, `同前`, or similar state inheritance language when the current visible state can be stated directly.
- Keep one 15-second Beat focused on one main dramatic event, with 1-2 supporting pieces of information and a continuous 0-15 second timeline.
- Default output mode is `full_density_clean_delivery`: provide the complete director execution Beat in the user-approved field format without exposing internal agent reasoning. Do not compress it into a short generic generation prompt. Use `director_review` only if the user asks for analysis, rationale, audit, or review.

## User-Approved Seedance 2.0 Format Lock

- Use this fixed section order for clean delivery: `这场戏是`, `风格`, `导演意图`, `光影`, `镜头调度`, `主要主体`, `场景视觉锁定`, `画面内容`, `声音`, `禁止项`.
- `这场戏是` must appear immediately after the BEAT title. Use `references/10-scene-type-taxonomy.json` and write `大类｜子类：剧作功能一句话。` The category must be specific, such as `人物出场戏｜群像埋点`, `大场面戏｜巨物显现`, `动作戏｜救援动作`, `追逐戏｜空中围堵`, `信息戏｜危险规则发现`, or `余波收束戏｜代价确认`. It must not become a plot summary.
- `风格` must preserve the user's locked tone exactly when one exists. For this project, do not replace the locked tone: `24帧诺兰式科幻悬疑电影质感，完全写实的真人实拍电影质感，真实演员的皮肤毛孔与发丝肌理，影调参考《降临》的冷峻克制与美式暗黑厚重神性。整体低饱和冷灰、铅蓝、暗青色调，黑位深，阴影厚，高光柔和压低。`
- Put camera and film process in `风格`, not a separate equipment section, when equipment is needed: camera body, recording format, lens family if useful, film stock or grain, and print process.
- `导演意图` must answer the emotional/audience purpose only, under 30 Chinese characters. Do not use it for shot choreography, plot summary, or long rationale.
- `导演意图` must contain a clear emotion, such as fear, unease, coldness, pressure, loss, relief, intimacy, suspicion, or sacrifice. Avoid theme-only concepts such as `秩序失衡`, `真相显现`, or `关系变化` unless the emotion is also explicit.
- `光影` must be concise but specific: main light, abnormal light, black-level/highlight behavior, and how it serves the Beat emotion. Before writing it, select a logic from `references/09-lighting-logic-library.json` according to scene type, scene function, space source, relationship state, information state, and emotional result.
- `镜头调度` must be under 50 Chinese characters. It must state `一镜到底`, `伪一镜到底`, or `切镜头/多镜头`, then the visible camera route or cut logic. Write it as an action chain, not a noun list: `先...，再切...，最后...`. Before writing it, select a director logic from `02-director-knowledge-base.json` and an editing logic from `03-camera-and-edit-library.json`.
- `主要主体` lists only characters, source-grounded entities, and actual props that must be locked. Do not list scenery, materials, texture details, VFX, light effects, weather, clouds, metal skin, rivets, wake, black sea, or other elements already covered by scene assets or the timeline.
- `场景视觉锁定` must include location, spatial relationship, environment dynamics, background crowd or environmental blocking when present, abnormal state, and non-changing constraints. It must contain enough motion cues to prevent static generation, such as cloud drift, crowd movement, cabin service movement, water motion, lighting rhythm, or machinery state. It must not include camera movement.
- `画面内容` is the Seedance 2.0 prompt body: timestamped natural-language white-description, directly visualizable, concrete, and free of internal directing analysis. Use the simplest precise natural language: short sentences, clear subjects, visible verbs, plain spatial relations, and no decorative or abstract phrasing. Every sentence must be something the model can see or hear: position, action, speed, light, expression, gaze, prop state, environment motion, sound, or dialogue. Emotion must be carried by visible results, not explained.
- Treat `references/12-model-facing-event-grammar.json` as the mandatory final-language contract. First choose one mutually exclusive framing branch. An objective shot uses `当前景别 → 当前可见状态与必要画面位置 → 主体动作 → 接触/反馈/结果 → 表演与视听变化`. A literal first-person or traversal view uses `视点拥有者/载体 → 眼前目标及其画面占幅 → 视线或运动轨迹 → 沿途变化 → 最终落点`; it must not be assigned `大特写/特写/近景/中景/全景/远景/大全景`. Preserve event order, but never invent an entry, contact, reaction, camera move, or viewpoint merely to fill a pattern.
- When movement, entry, exit, pursuit, contact, gaze, or a reveal depends on direction, use plain screen-space words such as `画面左侧`, `画面右侧`, `画面中央`, `前景`, `背景`, `画面深处`, `画外`, or a concrete opening such as a door, window, or aisle. State the start, direction, and endpoint needed to make the event executable. Do not translate this into camera geography.
- Write physical action with clear visible cause-and-effect: who does what, what visibly responds, and what state follows. Keep preparation, contact, force, displacement, or recovery when any of them is necessary to understand or generate the shot; omit only steps that add no story, spatial, emotional, or execution value. Acting remains explicit and is not treated as removable action detail.
- In `画面内容`, do not state camera placement or axis design. Prefer direct visual description. Use `镜头` or `画面` only when a visible move, reframing, focus change, or cut result must be controlled; otherwise start with the subject and action.
- If a person speaks in `画面内容`, write eye direction, gaze target, facial change, body/hand action, pre-speech state, post-speech state, voice strength, pace, and tone change. Dialogue must be attached to visible acting.
- `画面内容` must not use explanation words such as `让观众感到`, `表达`, `象征`, `暗示`, `证明`, `服务情绪`, `建立尺度锚点`, `传递压迫感`, or `形成巨物恐惧`.
- `声音` contains environment, machinery, action, breathing, dialogue, silence, and sound transitions. Do not add music.
- `禁止项` must be exactly: `绝对禁止生成BGM和字幕；禁止越轴。` Add extra prohibitions only if the user explicitly asks or a known model failure risk requires it.

## Instruction Priority

When references conflict, use this order:

1. The user's explicit instructions and user-approved examples.
2. This file's `15-Second Duration Profile` for duration, timeline, capacity, and timing-related template or validator configuration.
3. `references/07-full-density-format-example.md` for detail quality and field format, adapted to the source span owned by the 15-second Beat.
4. This `SKILL.md` for remaining rules.
5. The remaining knowledge-base references.

## Mandatory Runtime Gates

1. For every multi-Beat or duration-based script, complete the source-unit ledger and whole-script Beat Map before drafting Beat 001, even when only Beat 001 will be shown. Use `references/11-allocation-precision-workflow.json` to assign every atomic source unit to exactly one Beat, classify `scene_type`, set `capacity_budget`, and write Beat-specific `must_include` and `must_exclude` boundaries. A separate allocation auditor must check source-unit coverage, ownership, per-Beat capacity, dialogue timing, scene-type precision, climax distribution, and ending capacity; record the result in `project.allocation_audit`.
2. Run `scripts/validate_beat_map.py`. It must verify unique source ownership, source-unit ledger coverage, exact duration, scene-type classification, capacity budget, complete allocation audit coverage, exact router output, and a full module-read receipt for every Beat.
3. For every Beat, infer people and dialogue from the parsed source, then run `scripts/route_modules.py` with `--has-people` and/or `--has-dialogue` as applicable. Read every returned module in full and record the same Beat-specific applied decision in both `module_application` and `module_read_receipt`. A module path or generic claim is not proof of use. Unknown tags fail. Every full Beat must route and read `02-director-knowledge-base.json` and `03-camera-and-edit-library.json`; director shot selection may not be invented without the library.
4. Before final prose, build and pass the internal Shot Plan through `scripts/validate_shot_plan.py`.
5. Save the full-density draft temporarily and pass it through `scripts/validate_beat.py`.
6. Run `Storyboard_Review_Agent` on the completed candidate Beat before final output. It must mentally previz the full 0-15 second segment and adjacent Beat carry-in/carry-out when present; check visual穿帮, director artistry, shot service to story, camera motivation, axis/screen-direction/eyeline/action/prop/light/sound continuity, action trigger-feedback-result plausibility, Beat-to-Beat continuity, concise action wording, preserved acting, and AI-video executability. A non-PASS result blocks delivery and returns the draft to the responsible owner; after repair, rerun Shot Plan, Beat validation, and Storyboard Review.
7. Create separate stage artifacts for Story Lock, Drama Function, Director Selection, Cinematography, Composition/Lighting, Performance/Dialogue, Editing/Sound, Continuity, AI Translation, Final Director, Storyboard Review, independent Semantic QC, and Deterministic QC before receipt materialization. Every artifact must include stage-specific `deliverables`, producer `self_review`, receiver `upstream_acceptance`, a real orchestration `producer_run_id`, ISO start/completion timestamps, exact inputs, decision, and handoff. The receiver must directly read and accept every declared source, Beat Map, dependency, Shot Plan, final Beat, or ledger artifact required by its stage; summaries are not substitutes. Preserve raw completed run IDs in `collaboration-log.json`, and exact first/last Shot Plan states in `continuity-ledger.json`. `scripts/materialize_execution_receipt.py` may only hash and bind pre-existing artifacts; it must never generate evidence from receipt claims. Then run `scripts/validate_execution_receipt.py`; a missing stage, incomplete professional deliverable, failed self-review, rejected handoff, changed hash, unbacked run ID, broken dependency, or non-independent QC blocks delivery.
8. Run `scripts/validate_delivery.py` as the only final delivery gate. It must cross-check the same Beat ID, source span, routed knowledge files, structure, shot count, time ranges, shot scales, ordered event-flow cues, screen-space/action/result/prop/light/performance cues, source-fact evidence, final image, verbatim dialogue, continuity ledger, Storyboard Review PASS artifact, artifact paths, and hashes across all delivery files.
9. Treat validators, source script, approved BEAT 005 benchmark and manifest, routing result, continuity ledger, and Storyboard Review PASS artifact as locked. Never weaken a rule, omit a gate, or change source facts to make a draft pass.
10. If a runtime command is unavailable, locate a working Python runtime and rerun it. Do not silently replace a failed gate with self-assurance.

## Reference Routing

Read only the references needed for the request:

- `references/01-core-director.json`: always read for full Beat rules, priority order, camera-structure requirement, timeline rules, and final quality gate.
- `references/06-output-template.json`: always read before final delivery; it defines the required final section order and forbidden sections.
- `references/02-director-knowledge-base.json`: always read for a full Beat; use it to select dramatic viewpoint, scene-directing logic, shot type, composition, emotional-memory patterns, empty shots, symbolic details, audience information order, and final image logic.
- `references/03-camera-and-edit-library.json`: always read for a full Beat; use it to select shot scale, movement, reaction/action/insert coverage, editing logic, cut rhythm, cut triggers, continuity editing, and cross-Beat editing.
- `references/03-camera-library-full.json`: read when more detailed CAM-based options are useful; translate all choices into visible language.
- `references/03-camera-library-advanced.json`: read for opening/closing shots, advanced shot sizes, angles, and composition options.
- `references/03-light-color-special.json`: read for lighting, color, subjective views, depth/atmosphere, symbolic shots, and special pressure visuals.
- `references/09-lighting-logic-library.json`: always read before final delivery; use it to choose scene-specific lighting logic for dialogue, confrontation, secrecy, power imbalance, intimacy, isolation, aircraft cabin order, cockpit pressure, command centers, tarmac aftermath, home memory, underwater rescue, glass reflections, action danger, empty spaces, evidence reveals, giant pressure, and hidden threat.
- `references/10-scene-type-taxonomy.json`: always read before final delivery; use it to classify `这场戏是` with a precise scene category and subtype before writing style, director intent, lighting, and camera blocking.
- `references/11-allocation-precision-workflow.json`: mandatory for every multi-Beat, duration-based, or preview-from-full-script project. Use it to build the source-unit ledger, Beat ownership matrix, scene-type assignment, capacity budget, must-include/must-exclude boundaries, and independent allocation audit before routing modules.
- `references/12-model-facing-event-grammar.json`: always read in full before writing or reviewing `画面内容`; use it to convert the approved Shot Plan into ordered, screen-readable, model-executable event prose.
- `references/04-performance-and-dialogue.json`: read whenever people, emotion, acting, body behavior, or dialogue appears.
- `references/05-multi-agent-workflow.json`: always read for every full Beat. It defines the thirteen-stage specialist pipeline, stage-specific deliverables, producer self-review, receiver acceptance, failure return loop, and final convergence gate.
- `references/07-full-density-format-example.md`: always read before final delivery. It is the approved density, bracket format, terminology, and detail benchmark.
- `references/08-long-script-orchestration.md`: mandatory for every multi-Beat or duration-based script project. It defines allocation, routing, state, camera-continuity, and validation gates.

For small non-Beat requests, read `01-core-director.json`, `06-output-template.json`, plus the one most relevant domain reference. For every complete Beat, also read `05-multi-agent-workflow.json`; for a complete scene-to-Beat conversion with characters and dialogue, read `01`, `02`, `03-camera-and-edit-library`, `04`, `05`, and `06`.

## Workflow

1. Parse the story facts.
   Identify the core event, central character, goal, conflict, information release, and ending change. Do not design shots yet.

2. Allocate the source precisely when the input belongs to a longer script.
   Build the `source_unit_ledger`, assign each unit to one Beat, select `scene_type`, write `capacity_budget`, and lock `must_include` and `must_exclude` before any camera design. If the user asks to preview only one Beat, still complete this internal allocation pass first.

3. Select the Beat function.
   Choose one primary function such as world establishment, character introduction, relationship change, information reveal, clue discovery, power conflict, danger escalation, action conflict, rescue, emotional release, twist, or setup/payoff.
   The Drama Function artifact must be accepted by the Director before camera design begins.

4. Decide the camera structure.
   The final `镜头调度` field must state one of:
   - `一镜到底；...`
   - `伪一镜到底；...`
   - `切镜头；...` or `多镜头；...`

5. Design viewpoint and information release.
   Decide what the audience sees first, what remains hidden, how information becomes visible, and what the final emotional or narrative landing image is.

6. Run the internal Director Shot Selection Pass.
   Select each shot from the routed director, camera/edit, lighting, and performance knowledge before applying numeric continuity rules. For every shot, lock:
   - `shot_type`: establishing, performance, dialogue, reaction, action, action-insert, object-detail, environmental-empty, detail-empty, symbolic-detail, scale-reveal, or transition.
   - `dramatic_purpose`: what changes in the audience's knowledge, expectation, emotion, or spatial understanding.
   - `knowledge_basis`: exact `references/<file>:<concept>` citations that caused this choice.
   - `source_anchor`: the script action, object, space, sound, or line that legally supports the image.
   - `shot_selection_reason`: why this shot scale, viewpoint, and duration are more expressive than staying in the previous coverage.
   - `audiovisual_intent`: the visible and audible emotional effect.
   - `cut_trigger`: the action, reaction, sound, information change, gaze, light change, or spatial change that motivates the cut.
   - `metaphor_or_empty_basis`: source-grounded meaning for an empty or symbolic shot; use `none` only for ordinary coverage.
   - `information_before` and `information_after`: what the audience knows immediately before the shot and the exact new information after it.
   - `removal_test`: what story, emotion, or spatial clarity is lost if the shot is removed.
   - `alternative_rejected`: the strongest plausible alternative shot and why it serves this moment less well.
   - `action_logic`: the internal trigger, decisive action, necessary visible feedback, result state, and plausibility basis. This remains internal; only its essential visible result enters the final prompt.
   - `model_facing_contract`: exact ordered `event_flow_cues`, `screen_space_cues`, `action_cues`, `result_cues`, and verbatim `source_fact_cues`, plus applicable entry/exit, contact, feedback, movement/focus, prop, light, performance, and sound cues. Never create `camera_cues`; camera placement, lens height, camera side, and axis labels stay in internal fields and cannot be required as user-facing prose. `event_flow_cues` must appear in final prose in the declared order.

   Do not select a shot merely to satisfy scale or angle math. First choose the dramatically correct image, then place it so continuity rules pass. If a correct choice cannot pass without breaking axis or action, redesign the coverage instead of substituting an arbitrary shot.

   Empty shots and symbolic inserts are optional, not a quota. Their default count is zero. Use one only when it is the strongest way to express time, absence, aftermath, threat, memory, or a source-grounded relationship, and when ordinary action/performance coverage would be weaker. They fail when decorative, generic, repetitive, or unsupported. Never add one merely because the library contains it.

7. Express the production design at two levels.
   In `风格`, preserve useful production terminology and visual references. In `画面内容`, expand every choice into visible subject scale, movement, spatial relation, focus behavior, light behavior, performance, and the information revealed or changed. Keep camera viewpoint, height, side, and axis geometry internal.
   For each multi-shot time block, write the shot scale first, such as `远景。` or `人物近景。` Then describe the visible content directly. Do not state where the camera is or how many scale levels or degrees it changed.

8. Direct performance and dialogue.
   Bind each emotional state to visible body behavior, eye targets, facial change, breathing, one relevant hand/body action, voice state, and listener reaction. Preserve user-provided dialogue unless asked to rewrite. Keep these acting beats even when physical action wording is compressed.

9. Build the continuous timeline.
   Cover exactly 0-15 seconds with continuous, non-overlapping segments. Default to 3-4 segments, allowing fewer for a motivated hold or one-take. Never add cuts merely to meet a quota.

10. Build and validate the internal Shot Plan.
   Before writing the final Beat, lock a Beat-level `directorial_concept` and a per-shot `director_design`. At the scene, Beat, and shot scopes, three independent director proposals must debate and a Lead Director must select one coherent story-first design through the structured `director_debate` contract. Every selected shot must then prove its story task, audience gain, emotional change, chosen viewpoint, framing strategy, cut-or-hold motivation, and concrete removal consequence before photography is assigned. Then lock `viewpoint_type`, `viewpoint_subject`, `viewpoint_reason`, the mutually exclusive objective/subjective framing branch, `action_logic`, spatial axis, camera side, screen direction, eyelines, subject action start/end, prop state, light state, damage state, cut reason, and transition. Objective shots require `shot_scale`; literal first-person, object POV, FPV, and macro FPV require `framing_target`, `frame_occupancy`, `gaze_or_travel_path`, and `viewpoint_endpoint`, while `shot_scale` and `shot_scale_level` must be null. Each shot must also carry structured `continuity_state_in/out`; adjacent values must match exactly. The action result becomes the next shot's starting truth. Run `scripts/validate_shot_plan.py`. Do not expose the Shot Plan in clean delivery.

11. Run the quality gate.
   Check story preservation, director-design proof for the Beat and every shot, correct mutually exclusive framing branch, an opening objective shot scale or an opening literal viewpoint label, ordered event flow, explicit screen direction when movement depends on it, clear entry/exit boundaries, action contact and result, full production specification, visible acting, purposeful movement, meaningful composition/light, complete timeline, no visible camera-placement or axis jargon, no abstract psychology, no CAM numbers, no BGM, no subtitles, and no invented plot facts. Reject any subjective block that also carries an objective shot scale. Compare density against `references/07-full-density-format-example.md` and restore omitted source details before delivery.

12. Run the pre-output Storyboard Review gate.
   Before delivering to the user, internally screen the completed Beat as if watching the actual 15-second movie clip. Check whether anything visually穿帮, whether each action has a credible trigger, necessary feedback and usable result state, whether the camera choices feel director-led rather than template-led, whether every shot and cut helps tell the story, whether character/object/light/sound states remain continuous, whether Beat-to-Beat carry-in/carry-out is clean, and whether the model-facing language stays concise without losing acting. If it fails, return the exact failed contract to the owning stage and repair before output. Do not expose this review in clean delivery unless the user asks.

13. Run final convergence.
   Delivery requires all thirteen stage artifacts, all stage-specific deliverables, all producer self-reviews, all receiver acceptances, Storyboard Review PASS, independent Semantic QC PASS, deterministic validator PASS, verified hashes, and an empty unresolved-conflict list. Return any failure to the earliest responsible stage, then rerun every affected downstream acceptance and gate. Never let Final Director conceal an upstream omission.

## Full-Density Delivery Standard

- Treat the user-approved `BEAT 005` in `references/07-full-density-format-example.md` as the locked minimum detail and natural-language visual-description benchmark, not a special-case maximum.
- Preserve all story-bearing actions, reactions, props, lines, physical changes, light changes, and sound cues from the source passage assigned to the Beat.
- `风格` must specify frame rate, cinematic mode, live-action texture, visual reference, palette, contrast, grain, camera body, recording format, film-print or finishing texture, and any user-locked tone. Do not silently change the user's locked tone.
- `导演意图` must be under 30 Chinese characters and state the audience/emotional effect, not camera mechanics.
- `光影` must specify the Beat's main light, abnormal or practical light, black-level/highlight behavior, and emotional purpose. It must follow a selected plot/scene/emotion lighting logic from `09-lighting-logic-library.json`, not only for people but for every kind of scene.
- `镜头调度` must be under 50 Chinese characters and state one-take or cut structure plus the visible camera route or cut logic. It must follow a selected scene-directing logic and editing logic, not a noun list.
- Named directors, films, cameras, recording formats, film stocks, print processes, and standard lighting terms are allowed when they define the visual target. Never use a name as a substitute for the concrete visible result.
- `画面内容` normally uses four continuous time blocks such as `0–4`, `4–8`, `8–12`, and `12–15`; default to 3-4 blocks, allowing fewer for a motivated hold or one-take. Each objective block begins with its standard shot scale. Each literal first-person/POV block instead begins with the named viewpoint, then states the visible target, its size or occupied area in the frame, the gaze/travel path, visible changes, and endpoint; never add an objective shot scale to that block. Then directly describe composition, movement, light, action, performance, environment/background motion, information change, and dialogue/listener reaction when present. Do not write camera placement, camera height, viewing side, axis, or angle. Use simple, precise, executable natural language.
- Within each independent shot, describe events in playback order. Establish the current visible state before movement; state an entry before contact; state contact before feedback; state feedback before the resulting endpoint. Use screen-left/right, foreground/background, depth, off-screen space, or a concrete doorway/window/aisle only when they remove ambiguity. Do not force every shot to contain every event type.
- Do not automatically narrate the full internal action chain. In final prose, foreground `主体 + 关键动作 + 反馈/结果`, then retain as many intermediate actions as the shot genuinely needs for continuity, space, force, suspense, performance, or model execution. There is no fixed sentence count or feedback quota. Preserve the performance beat: gaze target, facial change, breath or voice state, and relevant hand/body behavior.
- Keep director reasoning out of `画面内容`. Cut reasons, dramatic purpose, information strategy, and why a shot was chosen belong in the internal Shot Plan or the short `导演意图`. The final timeline must contain only what the video model can render or hear; implement the reason through the actual cut point and image order instead of sentences such as `切镜发生在`, `这个镜头只负责`, `为了表现`, or `建立联系`.
- Aim for 4-6 readable visual states across the 15 seconds, without inventing events or speeding performance merely to meet a quota. A visual state may be a framing change, action result, focus shift, light change, reaction, spatial change, or revealed fact.
- Preserve dialogue verbatim unless the user requests rewriting. Bind every line to action, gaze, breathing, voice state, and reaction.
- `声音` must retain the scene's full environment, machinery, movement, breathing, dialogue, silence, and sound transitions. Do not summarize several specific cues as generic ambience.
- By default, `禁止项` is exactly: `绝对禁止生成BGM和字幕；禁止越轴。` Add further restrictions only when continuity or model failure risk genuinely requires them.
- Longer is not automatically better. Every detail must control story, image, performance, sound, continuity, or generation behavior.
- Density is measured per section against the source units assigned to this 15-second Beat and the benchmark's detail quality, not its original total word count or original-length section floors. Each section must retain its applicable source detail; padding cannot hide omitted facts.

## Camera Grammar And Continuity Gate

- Establish one spatial master before close coverage: character positions, entrances/exits, environmental anchors, danger direction, and the action axis.
- Preserve the 180-degree axis internally. If coverage must change side, first use a neutral shot to re-establish space and screen direction. Do not expose axis terminology or camera-side instructions in `画面内容`.
- Lock screen direction. A subject moving left-to-right remains left-to-right across cuts unless the turn is shown and motivated.
- Match eyelines by target, height, and screen side. A look off-screen must cut to the corresponding target direction or a deliberate withheld reveal.
- Match action across cuts at the same physical phase. Do not repeat, skip, reverse, or teleport an action.
- Every action must have a readable trigger, proportionate visible feedback, and a clear result state. Check gravity, inertia, contact, support, available space, prop condition, injury, character ability, knowledge, and motivation internally. Final prose prioritizes the decisive action and useful feedback, while retaining any process needed to make the action understandable and executable.
- On every ordinary objective-to-objective cut, change shot scale by at least one level. Same-scale cuts fail. Use this locked order: `大特写(1) → 特写(2) → 近景(3) → 中近景(4) → 中景(5) → 中全景(6) → 全景(7) → 远景(8) → 大全景(9)`; the absolute level difference must be `>=1`. A cut into or out of a literal first-person/POV/traversal view is governed by viewpoint motivation, eyeline, facing direction, target occupancy, and transition continuity instead; never invent a shot-scale value just to satisfy this numeric gate.
- On every ordinary objective-to-objective cut, change the camera's horizontal azimuth by strictly more than `30°`. Exactly `30°` fails. A cut into or out of literal first-person/POV/traversal framing is judged by motivated viewpoint change, eyeline, body/object orientation, and spatial handoff rather than an invented objective camera-angle delta. Record applicable numeric geometry only in the internal Shot Plan. Final prose states only the resulting visible composition and action. This rule never permits 越轴.
- Validated match edits are the only exception to the shot-scale and `>30°` rules. Record the technical exception and numeric proof in the Shot Plan. In final prose, express the match as a visible cut at the same action phase, shape, movement direction, gaze target, or composition; do not expose internal grading language. Axis, direction, action, prop, light, and damage continuity still apply.
- Carry character position, body orientation, hand occupancy, prop ownership/state, wardrobe, injury, blood, debris, door/window state, light direction, shadow, weather, and damage through every cut.
- Every cut must have one explicit reason: information, reaction, action, viewpoint, spatial clarification, time change, or emotional change. Decorative cuts fail.
- The shot-scale and `>30°` rules are post-selection continuity gates, not a shot-design engine. A technically valid cut still fails when its Shot Plan lacks a routed knowledge basis, source anchor, dramatic purpose, audiovisual intent, and concrete cut trigger.
- Use environmental empty shots, detail empty shots, and symbolic details only when `metaphor_or_empty_basis` identifies a source object, space, sound, action, or established motif and the removal test proves the Beat loses information or emotion without it. Zero such shots is fully valid. Never add one solely to appear cinematic or to demonstrate library usage.
- One-take camera paths require continuous spatial anchors. Fake one-takes require a named occluder and identical state on both sides of the hidden cut.
- The internal Shot Plan is a locked execution contract. If final prose contradicts it, repair the prose; do not silently change the plan.

## Final Output Format

Use this fixed order and bracket style for `full_density_clean_delivery`:

```markdown
BEAT ###｜场景·核心事件｜15秒结构

【这场戏是】
[大类｜子类：剧作功能一句话。Use references/10-scene-type-taxonomy.json.]

【风格】
[Frame rate, locked tone, live-action texture, visual reference, camera body, recording format, lens/film stock/print process if useful. Never change user-locked tone.]

【导演意图】
[No more than 30 Chinese characters. Emotional/audience purpose only.]

【光影】
[Emotion-serving light design: main light, abnormal/practical light, black level, shadow, highlight behavior.]

【镜头调度】
[No more than 50 Chinese characters. State one-take/fake one-take/cut structure and the clear camera route or cut logic.]

【主要主体】
[Characters, key entities, and actual source-grounded props only. Do not list scenery, textures, VFX, light effects, clouds, metal skin, rivets, wake, or elements already covered by scene assets and visual timeline.]

【场景视觉锁定】
[Location, time, spatial structure, environment dynamics, background crowd/environment blocking, subject starting positions, abnormal state, and non-changing spatial constraints. Include motion cues so the scene does not freeze. Do not include camera movement here.]

【画面内容】
【0-...秒】...
【...-...秒】...
【...-15秒】...

【声音】
[Environment sound, action sound, machinery, breathing, and dialogue. Do not include BGM.]

【禁止项】
绝对禁止生成BGM和字幕；禁止越轴。
```

Do not add independent props sections, CAM numbers, internal agent analysis, unsupported references, or pure camera-term lists. Do not remove purposeful style, camera, recording, finishing, composition, or lighting language merely to shorten the prompt.

### Story-Service Hard Gate

Before the Story-Service Hard Gate, run a three-director proposal debate at all three scopes: every scene, every Beat, and every shot. Persist scene debates in `scene_design_ledger`, Beat debates in `directorial_concept.director_debate`, and shot debates in `director_design.director_debate`.

1. `director_a_story_clarity` proposes a complete design led by source facts, causal clarity, information order, and spatial comprehension.
2. `director_b_performance_emotion` proposes a complete design led by character behavior, relationship, tension, and emotional timing without changing the source facts.
3. `director_c_visual_execution` proposes a complete design led by cinematic image, sound, lighting, movement, editing, and AI-video executability without turning technique into the story.

Each director gives a complete proposal at the level the moment genuinely needs, plus one concrete story benefit and one risk. The discussion records the real point of disagreement; a simple connective shot may need only a concise comparison, while a major reveal, performance turn, action passage, or viewpoint change needs deeper examination. Do not impose a fixed word count, checklist length, camera-technique quota, or identical discussion shape on every shot.

Final arbitration belongs to `Nolan_Style_Lead_Director`: prioritize source accuracy and causal clarity, controlled information architecture, readable real space and physical consequence, human stakes under pressure, restrained performance, large-scale image grounded in story, continuity, production coherence, and AI executability. Do not use nonlinear structure, concealment, spectacle, subjective POV, or technical complexity unless the current source event requires it. `诺兰式` is a decision discipline and concrete audiovisual result, never a substitute label. Select one coherent primary proposal; do not average incompatible ideas. Borrow a detail only when it preserves the selected proposal's viewpoint, information order, emotional line, and continuity.

The hard requirement is meaningful choice, not paperwork: three genuinely different proposals, at least one concrete comparison, one selected director, a story-first selection reason, and a final coherence/previz check. Repeated wording, generic approval language, visual spectacle outranking story, or an unresolved contradiction fails. These are production contracts, not user-facing chain-of-thought; clean delivery still shows only the selected final Beat.

Every shot, hidden cut, camera path, viewpoint, focus change, empty image, symbol, light change, and sound cue must serve the owned story event. Technique is selected only after story purpose is clear. For each Shot Plan entry, answer all of the following before continuity checks:

- Which exact source fact, action, reaction, relationship, danger, decision, or consequence does this shot make visible?
- What new information or emotional weight exists after the shot that did not exist before it?
- Why must the cut occur at this visible action, look, sound, reveal, or state change; or why must the camera remain continuous here?
- What concrete story loss occurs if the shot is removed?
- Which plausible alternative was rejected, and why is the chosen audiovisual method more precise for this moment?

A shot fails when its only justification is a different scale, visual variety, cinematic style, knowledge-base coverage, technical novelty, spectacle, or “高级感”. POV, FPV, macro FPV, one-take, fake one-take, empty shots, inserts, metaphors, and advanced movements have no quota. If removal causes no meaningful loss of story information, action clarity, performance weight, spatial comprehension, time pressure, or thematic relation, delete or redesign the shot.

### Viewpoint Assignment Gate

Assign a viewpoint type before photography and before writing every shot. Viewpoint is a dramatic decision, not decorative vocabulary. The Director Agent must first record `viewpoint_type`, `viewpoint_subject`, and `viewpoint_reason`, including why the audience must see the event this way and what would be lost with the most plausible alternative. The Cinematography Agent may execute that decision but may not change an objective view into POV merely for variety. Keep ordinary objective camera placement internal; only name a viewpoint in final prose when the image is literally a source-grounded first-person, object, traversal, reflection, screen, or surveillance view and the model must know it to render the shot correctly.

- `objective`: the default external camera. Use when the audience must compare subjects, read geography, see the character from outside, or remain emotionally independent. It requires a concrete shot scale whose extent describes the visible framing target.
- `character_pov`: a named character's literal first-person visual field. It does not take an objective shot scale. State whose POV it is, what the character sees, how much of the frame the target occupies, where the gaze starts, how it shifts, and where it stops. A source-grounded hand, body edge, or held object may enter the bottom or edge of the view. Do not show the POV character's face or external body unless a reflection or screen is visibly established.
- `object_pov`: a source-grounded view attached to or aligned with an important object. State the object and its physical direction. Do not invent an impossible sentient viewpoint merely for novelty.
- `fpv_flythrough`: FPV or FPV drone-style continuous traversal for speed, pursuit, narrow-space passage, or force-path visualization. State the entry space, every visible obstacle or turn, stable travel direction, and final landing composition. FPV does not excuse teleportation, axis confusion, collision, or weightless camera movement in a physically constrained scene.
- `macro_fpv`: a micro-scale FPV path close to a source-grounded surface or mechanism, such as metal texture, a crack, liquid edge, instrument, or prop detail. State the surface anchor, travel direction, focus transition, scale reveal, and endpoint. Preserve material geometry; do not let macro travel deform the object or become an unsupported microscopic fantasy.
- `voyeur_observer`: a distant, obstructed, monitor, reflection, or surveillance viewpoint used when observation, concealment, or power distance is the story fact.

POV, FPV, and macro FPV have no quota. Use them only when the removal test shows that an objective camera would lose essential information, embodiment, speed, pressure, or scale. For every selected subjective or traversal view, lock the target, frame occupancy, gaze/travel path, endpoint, screen direction, body/object orientation, occlusion, speed, focus, light direction, and the exact transition into and out of the view. In final prose, write explicit phrases such as `江临主观视角。父亲手中的照片占据画面中央……`, `FPV穿越机视角……`, or `微距FPV视角……`; never leave the viewpoint implied by `跟随拍摄`. `特写，江临主观视角`、`江临主观视角，特写` and every other subjective-view-plus-objective-scale combination are hard failures.

Before approval, the Storyboard Review Agent must mentally render the first and last frame of every shot and answer: who owns the view, what is visibly framed, why this view is necessary now, what changes during the shot, and what exact state is handed to the next shot. Generic answers such as “增强代入感”, “更电影化”, “丰富景别”, or “服务情绪” fail. If a shot has no specific audience gain or removal consequence, delete or redesign it.

### Model-Facing Natural-Language Shot Description

Read `references/12-model-facing-event-grammar.json` in full. Use the applicable parts of this order for every independent shot in `画面内容`:

```text
客观镜头：[当前景别]。[当前可见状态]。[关键动作]。[必要的接触、反馈、结果与表演]。[必要的画面、焦点、光线或声音变化]。
第一人称/遍历视点：[明确视点]。[眼前目标及画面占幅]。[视线或运动从哪里经过哪里]。[沿途可见变化]。[最终落点与结果]。
```

This is an event order, not a sentence quota. Omit inapplicable steps, but never reverse cause and result or hide a needed direction. For an interaction, keep the readable chain `发起者 → 对象 → 接触/作用 → 反馈 → 结果`. For entry or exit, name the screen edge or concrete opening and the endpoint. For a gaze, name the target or established off-screen direction. Use `随后`, `接着`, or an action trigger only when they clarify real temporal order.

Begin an objective shot with `大全景。`, `中景。`, or another standard scale. Begin a literal first-person/traversal shot with its explicit viewpoint and never add a standard scale, for example: `江临主观视角。空白照片占据大部分画面，父亲右脸的位置只剩浅灰纸面。视线从照片边缘移到空白处，停住。` Do not write internal comparison or camera-placement prose such as `摄影机位于`, `保持眼平`, `景别由大全景跨越五级`, `相对上一镜改变40°`, `保持在动作轴A侧`, or `承接上一Beat末镜`.

Cross-Beat continuity remains mandatory internally, but restate inherited facts directly in the new Beat: current character position, current prop state, current injury, current light direction, current danger direction, and current movement direction.

Final prose must be independently executable without exposing technical camera geometry. Prefer phrases such as `父亲走向房门，镜头平稳跟随`, `画面从门缝白光缓慢落到桌上的照片`, or `焦点从杯壁水珠转到红绳死结`. Do not write `摄影机位于`, camera height, front/side/rear placement, lens location, measurements, coordinates, angles, axis labels, or camera-side comparisons.

Translate internal camera shorthand into visible results. `固定镜头` becomes `画面保持不动`; follow or pan instructions become `画面跟随人物移动` or `画面跟着视线转向目标`; a match cut is written as the same visible action continuing across two scales. Do not describe where the camera body is located.

Do not narrate editorial analysis inside `画面内容`. For example, replace `切镜发生在男人的手进入时，这个镜头只负责表现照料` with the directly renderable sequence: `男人的手从画面右侧进入，把热牛奶放到桌上。` The time-block boundary already defines the cut.

## Director Review Mode

When the user asks for review, rationale, or audit, add a brief `导演审核` section before the final clean Beat with:

- `剧情功能`
- `镜头结构选择`
- `信息释放顺序`
- `构图与光影目的`
- `表演执行重点`
- `质量检查`

Keep this concise and still provide the final clean Beat after it.

## Batch Beat Generation

For long scripts or multiple Beats:

- Read `references/08-long-script-orchestration.md` and complete the whole-script Beat Map before drafting Beat 001.
- Read `references/11-allocation-precision-workflow.json` and complete `source_unit_ledger`, `scene_type`, `capacity_budget`, `must_include`, and `must_exclude` for every Beat before routing modules.
- Work in batches of 3-5 Beats.
- Build a continuity ledger for characters, props, space direction, action axis, screen direction, eyelines, injuries, light state, and danger source.
- Maintain cross-Beat inheritance: character position, prop state, danger direction, light state, and focus state.
- Run module routing, Beat Map validation, Shot Plan validation, final Beat validation, hash-bound execution receipt validation, and unified delivery validation. A failed gate blocks delivery.
- Require all thirteen stage contracts to pass producer self-review and receiver acceptance. A downstream agent may not repair or silently reinterpret an upstream artifact; it must reject and return it.
- Run the internal Storyboard Review gate before every user-facing Beat. It must mentally previz the candidate Beat and pass visual穿帮, director artistry, story-service, continuity, and AI-executability checks before output.
- Write and validate one structured execution receipt per Beat. It must prove every specialist stage passed, Storyboard Review passed, independent Semantic QC examined the source directly, continuity was updated, and the batch retained the approved density benchmark.
- If later Beats become generic, start a fresh batch context from the persisted visual bible, Beat Map, continuity ledger, and routed modules; do not continue in a saturated context.

## Failure Recovery

If the draft contains abstract phrasing such as `他意识到`, `她很害怕`, `命运压力`, or `情绪爆发`, replace it with visible behavior.

If the draft contains purposeful production shorthand such as `伦勃朗光` or `权力构图`, retain it in `风格` or `光影` only when it defines the visible result, and add concrete subject placement, light source, shadow relation, and spatial pressure in `画面内容`. Keep camera height and axis geometry internal. Remove unsupported labels and CAM IDs; never delete useful terminology merely to shorten the Beat.

If final `画面内容` prose contains `摄影机位于`, `机位`, camera height, front/side/rear placement, `上一Beat`, `上一镜`, `承接`, `相对上一`, `A侧`, `B侧`, `轴线`, `景别跨越几级`, or similar internal bookkeeping, rewrite the sentence as the current shot scale plus direct visible content. Avoid `继续` as a state shortcut; restate the action and direction directly. Preserve the word only when it is locked source dialogue.

If movement, entry, exit, contact, pursuit, or an off-screen look is ambiguous, rewrite it with the minimum screen-space information needed to execute it: start, direction or boundary, interaction, feedback, and endpoint. If the prose lists the result before its cause, mixes several independent actions into one long sentence, or omits the state needed by the next shot, split and reorder it before validation.

If the draft repeats the same push-in, side/back light, half-lit face, or generic cinematic phrasing without story purpose, choose a new visual strategy based on the Beat function.

If the pre-output Storyboard Review finds visual穿帮, weak director artistry, discontinuous shots, broken Beat-to-Beat state, unclear camera motivation, or any shot that does not serve the story, do not deliver the draft. Return to the responsible stage, repair the plan and prose, then rerun the review.

If the draft is materially shorter or less specific than `references/07-full-density-format-example.md`, check the assigned source passage line by line and restore omitted story actions, physical states, production design, sound cues, and performance reactions. Do not solve density problems by adding empty adjectives.
