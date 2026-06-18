# astrbot_plugin_reply_limiter

按 UMO 会话隔离的唤醒回复忙锁插件。

## 功能

- 只限制唤醒消息，普通聊天不处理
- 默认按 UMO 会话隔离忙锁
- 同群 A 忙时，B 再 @ 也静默
- 同一会话始终只跟一个人对话
- 唤醒消息可绕过忙锁直接进入
- 白名单 UMO 不受限制，管理员也填白名单
- 支持 UMO 黑名单
- 支持超时自动解锁

## UMO 格式

只使用 UMO。用系统自带 `/sid` 获取。

私聊：

```text
default:FriendMessage:<user_id>
```

群聊：

```text
default:GroupMessage:<group_id>
```

## 配置

```json
{
  "enabled": true,
  "wake_only": true,
  "wake_keywords": ["弥灵"],
  "silent_block": true,
  "block_reply": "",
  "lock_timeout_seconds": 180,
  "lock_scope": "umo",
  "whitelist": [],
  "global_blacklist": []
}
```

## 字段说明

- `enabled`：启用插件。
- `wake_only`：只限制唤醒消息。
- `wake_keywords`：唤醒词兜底。
- `silent_block`：拦截时静默。
- `block_reply`：非静默拦截提示。
- `lock_timeout_seconds`：自动解锁秒数。
- `lock_scope`：忙锁范围，默认 `umo`；可选 `global`、`sender`。
- `whitelist`：UMO 白名单，管理员也填这里。
- `global_blacklist`：UMO 黑名单。

## 指令

无。
