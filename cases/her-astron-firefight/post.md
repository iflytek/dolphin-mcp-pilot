# 帖子文案（掘金/CSDN 通用版）— 2026-08-22 发布用

> 掘金版：直接用本文。CSDN 版：标题后加「| DolphinScheduler + MCP 实战」，正文不变。
> 发布前：真实链接回填 cases/README.md 的 channels。

---

## 标题

凌晨三点，我一句话让 AI 接管了 DolphinScheduler 救火（自然语言运维实战）

## 正文

凌晨 3 点，手机震动：日结 ETL 挂了。

以前这种时候，我要爬起来开电脑、登录 DolphinScheduler 控制台、翻实例列表、
找失败任务、点开日志慢慢看、定位原因、再手动重跑。一套下来十五分钟起步，
困意全消，血压拉满。

这次不一样。我只在对话里打了一句话：

> 「我日结的 ETL 好像挂了，帮我查一下今天凌晨失败的实例，看看是哪个任务、为什么失败，能修复就直接重跑。」

然后看着 Agent 自己干活：

1. 一键拉失败日志 —— 命中 fire-drill-v2 实例 id:5（FAILURE），定位到 flaky_step
2. 直接修脚本 —— ds_update_task_param，一行命令把 exit 1 改成成功命令
3. 触发新运行 —— 实例 id:6，SUCCESS

全程没碰浏览器，十分钟内 FAILURE → SUCCESS。

顺手还干了一件事：又打了一句话，让它建了个每天早上 8 点跑的日报工作流
（MySQL 拉昨日数据 → 汇总 → 推企业微信），同样秒建秒上线。

这就是 dolphin-mcp-pilot 干的事：把 DolphinScheduler 的 53+ 个操作封装成 MCP 工具，
AI Agent 用自然语言就能驱动——查实例、看日志、重跑、建工作流、管调度，全都能聊着干。

【环境参考】
- DolphinScheduler 3.4.2 standalone（2C4G 低配 VPS 实测可跑，内存钳制 1.6G）
- dolphin-mcp-pilot 0.3.0（MCP 2.0，HTTP 模式）
- MCP 宿主：OpenClaw

【附上实操截图】
（插入截图：自然语言请求 / 工具调用结果 / 失败→成功 before-after）

【踩坑记录，帮后来人省时间】
DS 3.4.x 改了 API 路径：process-definition → workflow-definition、
start-process-instance → start-workflow-instance、process-instances → workflow-instances，
字段 processDefinitionCode → workflowDefinitionCode。
用 3.4.x 的记得同步适配，不然会踩一堆 404/字段不存在的坑。

一句话总结：以前是「人学会用控制台」，现在是「让 AI 学会用控制台」。
会说话，就会运维了。

#DolphinScheduler #MCP #AI运维 #自然语言运维 #效率工具 #开源
