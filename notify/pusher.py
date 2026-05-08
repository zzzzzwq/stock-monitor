"""消息推送（企业微信 / 钉钉 webhook）"""
import json
import logging
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


def push_wechat(webhook_url: str, content: str, at_mobiles: list[str] = None) -> bool:
    """推送到企业微信机器人"""
    if not webhook_url:
        return False
    body = {
        "msgtype": "markdown",
        "markdown": {"content": content},
    }
    if at_mobiles:
        body["markdown"]["mentioned_mobile_list"] = at_mobiles
    try:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            resp = json.loads(r.read())
            if resp.get("errcode") == 0:
                return True
            logger.error(f"企业微信推送失败: {resp}")
            return False
    except Exception as e:
        logger.error(f"企业微信推送异常: {e}")
        return False


def push_dingtalk(webhook_url: str, content: str, at_mobiles: list[str] = None) -> bool:
    """推送到钉钉机器人"""
    if not webhook_url:
        return False
    body = {
        "msgtype": "markdown",
        "markdown": {"title": "盯盘分析", "text": content},
    }
    if at_mobiles:
        body["at"] = {"atMobiles": at_mobiles}
    try:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            resp = json.loads(r.read())
            if resp.get("errcode") == 0:
                return True
            logger.error(f"钉钉推送失败: {resp}")
            return False
    except Exception as e:
        logger.error(f"钉钉推送异常: {e}")
        return False


def push(config: dict, title: str, content: str) -> bool:
    """同时推送到所有配置的webhook"""
    ok = True
    wechat_url = config.get("notify", {}).get("wechat_webhook", "")
    dingtalk_url = config.get("notify", {}).get("dingtalk_webhook", "")
    at_mobiles = config.get("notify", {}).get("at_mobiles", [])

    full_content = f"# {title}\n\n{content}"

    if wechat_url:
        if not push_wechat(wechat_url, full_content, at_mobiles):
            ok = False
    if dingtalk_url:
        if not push_dingtalk(dingtalk_url, full_content, at_mobiles):
            ok = False
    return ok
