"""自动盯盘分析工具 — 主入口

启动 APScheduler 定时任务 + Flask 健康检查服务。

用法:
  python main.py                    # 正常启动（后台调度 + Flask）
  python main.py --test-slot=0830   # 测试单个时间点的分析
  python main.py --dry-run          # 立即执行所有时间点（用于测试）
  python main.py --migrate-config   # 将 config.json 持仓迁移到数据库
"""
import argparse
import json
import logging
import sys
import codecs

# 确保stdout支持UTF-8（Windows GBK兼容）
if sys.stdout.encoding and sys.stdout.encoding.upper() != "UTF-8":
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "replace")
if sys.stderr.encoding and sys.stderr.encoding.upper() != "UTF-8":
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "replace")
import threading
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from models import init_db, get_session
from models.user import User
from models.holding import Holding
from scheduler.jobs import JOB_REGISTRY
from web.app import app, init_status, record_run

# 日志配置
class _Utf8StreamHandler(logging.StreamHandler):
    """UTF-8安全控制台输出"""
    def __init__(self):
        super().__init__(sys.stdout)
    def emit(self, record):
        try:
            super().emit(record)
        except UnicodeEncodeError:
            msg = self.format(record).encode("utf-8", "replace").decode("utf-8", "replace")
            self.stream.write(msg + self.terminator)
            self.flush()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        _Utf8StreamHandler(),
        logging.FileHandler("logs/stock-monitor.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")


def load_config(path: str = "config/config.json") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def migrate_config_to_db():
    """将 config.json 中的持仓数据迁移到数据库"""
    config = load_config()
    session = get_session()
    try:
        # 检查是否已有用户
        existing = session.query(User).first()
        if existing:
            logger.info("数据库已有用户，跳过迁移")
            return

        # 创建默认用户
        user = User(nickname="默认用户")
        session.add(user)
        session.flush()

        # 迁移持仓
        holdings = config.get("holdings", [])
        for h in holdings:
            holding = Holding(
                user_id=user.id,
                code=h["code"],
                name=h["name"],
                market=h["market"],
                shares=h["shares"],
                cost_per_share=h["cost_per_share"],
                related_boards=json.dumps(h.get("related_boards", []), ensure_ascii=False),
            )
            session.add(holding)

        session.commit()
        logger.info(f"迁移完成: 1 个用户, {len(holdings)} 个持仓")
    except Exception as e:
        session.rollback()
        logger.error(f"迁移失败: {e}")
        raise
    finally:
        session.close()


def run_slot_direct(config: dict, slot_id: str):
    """直接运行单个时间点的分析（用于测试）"""
    job_func = JOB_REGISTRY.get(slot_id)
    if not job_func:
        logger.error(f"未知的时间点: {slot_id}")
        logger.info(f"可用时间点: {', '.join(sorted(JOB_REGISTRY.keys()))}")
        return
    logger.info(f"直接运行 [{slot_id}] ...")
    job_func(config)
    logger.info(f"[{slot_id}] 执行完成")


def run_all_slots(config: dict):
    """运行所有时间点（用于 --dry-run）"""
    for slot_id in sorted(JOB_REGISTRY.keys()):
        logger.info(f"{'='*40}")
        logger.info(f"执行 [{slot_id}]")
        run_slot_direct(config, slot_id)


def start_scheduler(config: dict) -> BackgroundScheduler:
    """启动APScheduler"""
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    schedules = config.get("schedules", {})
    enabled = schedules.get("enabled_slots", [])
    cron_exprs = schedules.get("cron_expressions", {})

    for slot_id in enabled:
        if slot_id not in JOB_REGISTRY:
            logger.warning(f"未知时间点: {slot_id}, 跳过")
            continue
        cron = cron_exprs.get(slot_id)
        if not cron:
            logger.warning(f"时间点 {slot_id} 无cron配置, 跳过")
            continue

        def make_job(sid):
            def job_wrapper():
                logger.info(f"触发定时任务 [{sid}]")
                JOB_REGISTRY[sid]()  # 多用户版不再需要 config 参数
                record_run(sid)
            return job_wrapper

        scheduler.add_job(
            func=make_job(slot_id),
            trigger=CronTrigger.from_crontab(cron),
            id=f"slot_{slot_id}",
            name=f"Analysis-{slot_id}",
            misfire_grace_time=300,
            coalesce=True,
        )
        logger.info(f"注册任务 [{slot_id}] {cron}")

    scheduler.start()
    logger.info(f"调度器已启动, 共 {len(enabled)} 个定时任务")
    return scheduler


def start_flask(config: dict):
    """在独立线程中启动Flask"""
    host = config.get("web", {}).get("host", "0.0.0.0")
    port = config.get("web", {}).get("port", 8080)

    def run():
        app.run(host=host, port=port, debug=False, use_reloader=False)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    logger.info(f"Flask 已启动 http://{host}:{port}")
    return t


def main():
    parser = argparse.ArgumentParser(description="自动盯盘分析工具")
    parser.add_argument("--test-slot", help="测试单个时间点 (如 0830)")
    parser.add_argument("--dry-run", action="store_true", help="立即运行所有时间点")
    parser.add_argument("--config", default="config/config.json", help="配置文件路径")
    parser.add_argument("--migrate-config", action="store_true", help="将 config.json 持仓迁移到数据库")
    args = parser.parse_args()

    config = load_config(args.config)

    # 初始化数据库
    init_db()
    logger.info("数据库初始化完成")

    # 迁移旧配置
    if args.migrate_config:
        migrate_config_to_db()
        return

    # 检查webhook是否配置（仅提醒）
    wechat_url = config.get("notify", {}).get("wechat_webhook", "")
    dingtalk_url = config.get("notify", {}).get("dingtalk_webhook", "")
    if not wechat_url and not dingtalk_url:
        logger.info("全局 webhook 未配置（多用户可各自配置）")

    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    init_status(start_time)

    if args.test_slot:
        run_slot_direct(config, args.test_slot)
        return

    if args.dry_run:
        run_all_slots(config)
        return

    # 正常启动
    logger.info(f"启动盯盘工具 {start_time}")
    scheduler = start_scheduler(config)
    start_flask(config)

    try:
        scheduler._event.wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("正在关闭...")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
