import time

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register


@register(
    "astrbot_plugin_reply_limiter",
    "miling",
    "按 UMO 会话隔离的唤醒回复忙锁：同会话上一条回复发送后才允许下一条",
    "1.8.1",
)
class ReplyLimiterPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.config = config or {}

        self.enabled = bool(self.config.get("enabled", True))
        self.wake_only = bool(self.config.get("wake_only", True))
        self.wake_keywords = self._load_set("wake_keywords", ["astrbot"])
        self.silent_block = bool(self.config.get("silent_block", True))
        self.block_reply = str(self.config.get("block_reply", ""))
        self.lock_timeout_seconds = int(self.config.get("lock_timeout_seconds", 180))
        self.lock_scope = str(self.config.get("lock_scope", "umo")).strip().lower()

        # 只认 UMO。管理员也直接填这里。
        self.whitelist = self._load_set("whitelist", [])
        self.global_blacklist = self._load_set("global_blacklist", [])

        # lock_key -> locked_at，默认按 UMO 会话隔离忙锁
        self.locks = {}

    def _load_set(self, key: str, default):
        return {str(x).strip() for x in self.config.get(key, default) if str(x).strip()}

    def _umo(self, event: AstrMessageEvent) -> str:
        try:
            umo = getattr(event, "unified_msg_origin", None)
            if umo:
                return str(umo)
        except Exception:
            pass

        try:
            platform_id = str(event.get_platform_id() or "default")
        except Exception:
            platform_id = "default"

        try:
            group_id = str(event.get_group_id() or "")
        except Exception:
            group_id = ""

        if group_id:
            return f"{platform_id}:GroupMessage:{group_id}"

        try:
            sender_id = str(event.get_sender_id())
        except Exception:
            sender_id = ""
        return f"{platform_id}:FriendMessage:{sender_id}"

    def _sender_id(self, event: AstrMessageEvent) -> str:
        try:
            return str(event.get_sender_id())
        except Exception:
            return ""

    def _lock_key(self, event: AstrMessageEvent, umo: str) -> str:
        if self.lock_scope == "umo":
            return umo
        if self.lock_scope == "global":
            return "global"
        sender_id = self._sender_id(event)
        return f"{umo}:{sender_id}" if sender_id else umo

    def _is_wake_trigger(self, event: AstrMessageEvent) -> bool:
        try:
            if bool(getattr(event, "is_at_or_wake_command", False)):
                return True
        except Exception:
            pass

        try:
            text = (event.message_str or event.get_message_str() or "").strip()
        except Exception:
            text = ""
        return bool(text and any(k and k in text for k in self.wake_keywords))

    def _is_whitelisted(self, umo: str) -> bool:
        if umo in self.whitelist:
            self._unlock(umo)
            return True
        return False

    def _is_blacklisted(self, umo: str) -> bool:
        return umo in self.global_blacklist

    def _expire_locks(self):
        now = time.time()
        timeout = max(1, self.lock_timeout_seconds)
        expired = [key for key, locked_at in self.locks.items() if now - locked_at > timeout]
        for key in expired:
            logger.warning(f"[reply_limiter] lock expired key={key}")
            self.locks.pop(key, None)

    def _is_busy(self, key: str) -> bool:
        self._expire_locks()
        return key in self.locks

    def _lock(self, event: AstrMessageEvent, key: str):
        self.locks[key] = time.time()
        try:
            event.set_extra("_reply_limiter_locked_key", key)
        except Exception:
            pass

    def _unlock(self, key: str):
        if key:
            self.locks.pop(key, None)

    @filter.event_message_type(filter.EventMessageType.ALL, priority=98)
    async def limit_reply_count(self, event: AstrMessageEvent):
        if not self.enabled:
            return

        if self.wake_only and not self._is_wake_trigger(event):
            return

        umo = self._umo(event)

        if self._is_whitelisted(umo):
            return

        if self._is_blacklisted(umo):
            logger.warning(f"[reply_limiter] blacklist blocked umo={umo}")
            if not self.silent_block and self.block_reply:
                yield event.plain_result(self.block_reply)
            event.stop_event()
            return

        key = self._lock_key(event, umo)
        if not self._is_wake_trigger(event):
            if self._is_busy(key):
                logger.warning(f"[reply_limiter] busy blocked key={key} umo={umo}")
                if not self.silent_block and self.block_reply:
                    yield event.plain_result(self.block_reply)
                event.stop_event()
                return

        self._lock(event, key)

    @filter.after_message_sent()
    async def unlock_after_sent(self, event: AstrMessageEvent):
        if not self.enabled or not self.locks:
            return

        try:
            locked_key = str(event.get_extra("_reply_limiter_locked_key", ""))
        except Exception:
            locked_key = ""

        self._unlock(locked_key)
