# QQDigest

[English](README.md) | [中文](README_ch.md)

通过 NapCat 监听 QQ 群消息，定时调用 DeepSeek API 从闲聊中提取有价值信息，并将结果私聊发送给指定 QQ。

## 功能特性

- 通过 WebSocket 实时监听 NapCat 的群消息事件
- 所有消息持久化到本地 SQLite 数据库
- 每日定时（可配置）调用 DeepSeek API 提取过去 24 小时群聊中的有价值信息（学习、竞赛、技术等内容，过滤闲聊）
- 提取结果通过 NapCat HTTP API 以私聊形式发送
- WebSocket 断线自动重连
- 全程异步（asyncio）

## 架构说明

```
main.py          — 入口文件，组装各模块，启动 Collector 和定时任务
collector.py     — WebSocket 客户端，解析 OneBot v11 JSON，存入数据库
db.py            — SQLite 异步封装，提供插入和按时间范围查询
summarizer.py    — 调用 DeepSeek Chat Completions API，从消息中提取高价值信息（学习、竞赛、技术方向），过滤闲聊
sender.py        — 通过 NapCat HTTP API 发送私聊消息
config.yaml      — 配置文件（群号、目标 QQ、API Key、定时时间等）
```

## 环境要求

- Python 3.10+
- NapCat（已启动，WebSocket 端口 3001，HTTP 端口 3000）
- DeepSeek API Key

## 安装与部署

```bash
# 1. 克隆 / 进入项目
cd QQDigest

# 2. 安装依赖
pip install websockets aiohttp apscheduler pyyaml

# 3. 创建配置文件
cp config.example.yaml config.yaml
# 编辑 config.yaml，填入 api_key、group_id、target_qq

# 4. 确保 NapCat 已启动

# 5. 运行
python main.py
```

程序启动后会立即开始监听消息，并执行一次总结（方便测试），之后每天在配置的时间自动执行。

## 配置项说明

| 配置项 | 说明 |
|---|---|
| `napcat.ws_url` | NapCat WebSocket 地址（监听消息事件）|
| `napcat.http_url` | NapCat HTTP API 地址（发送消息）|
| `group_id` | 要监听的 QQ 群号 |
| `target_qq` | 接收每日总结的 QQ 号 |
| `deepseek.api_key` | DeepSeek API 密钥 |
| `deepseek.model` | 模型名称（默认 `deepseek-chat`）|
| `deepseek.base_url` | API 基础地址（默认 `https://api.deepseek.com`）|
| `schedule.time` | 每日定时总结时间（HH:MM，24 小时制）|
| `schedule.timezone` | 时区（默认 `Asia/Shanghai`）|
| `database.path` | SQLite 数据库文件路径 |

## 注意事项

- `config.yaml` 已加入 `.gitignore`，其中包含 API Key，**切勿提交到仓库**
- 使用 `config.example.yaml` 作为模板，复制后填写真实配置
- 数据库文件 `data/messages.db` 同样被 gitignore
- 启动时会自动执行一次过去 24 小时的总结，如不需要可移除 `main.py` 中对应的调用
- WebSocket 断线后每 5 秒自动重连

## 测试

```bash
pip install pytest pytest-asyncio aiosqlite
pytest
```