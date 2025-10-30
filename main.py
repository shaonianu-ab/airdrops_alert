import requests
import json
import datetime
import time
import random
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from msg_handler import msg_handler

# ======================
# 获取空投数据
# ======================

def get_airdrop_data():
    """从 alpha123.uk 获取空投数据"""
    url = "https://alpha123.uk/api/data?fresh=1"
    headers = {
        "accept": "*/*", 
        "accept-encoding": "gzip, deflate, br, zstd", "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7,en-US;q=0.6", 
        "cache-control": "no-cache", 
        "referer": "https://alpha123.uk/zh/", 
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        print(response.json())
        return response.json()
    except Exception as e:
        print(f"❌ 请求错误: {e}")
        return None


# ======================
# 全局缓存与调度器
# ======================

last_airdrops = {}
scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
init_flag = True


# ======================
# 功能函数
# ======================

def format_to_msg(item):
    token_name = item.get("token") or "未公布"
    amount = item.get("amount") or "未公布"
    time_ = item.get("time") or "未公布"
    type_ = item.get("type")
    ca = item.get("contract_address") or "未知"
    spot_listed = item.get("spot_listed")
    futures_listed = item.get("futures_listed")
    points = str(item.get("points")) or "未公布"

    msg = [f"🚨 **Alpha Airdrop 通知**",
            "",
            f"💠 Symbol: {token_name}",
            f"💰 数量: {amount}",
            f"⏰ 时间: {time_}"]

    if points == "未公布":
        msg.append(f"⚡ 类型: 未公布")
    elif " " not in points:
        if type_ != "tge":
            msg.append(f"⚡ 类型: 空投--先到先得")
        else:
            msg.append(f"⚡ 类型: TGE活动，需要3个BNB参与")
        msg.append(f"⭐ 积分门槛: {points}")
    else:
        msg.append("⚡ 类型: 空投--分段")
        points_split = points.split(" ")
        msg.append(f"⭐ 积分门槛:")
        msg.append(f"   - 前18小时: {max(points_split)}")
        msg.append(f"   - 后6小时: {min(points_split)}")

    msg.append("-" * 20)
    msg.append(f"CA: {ca}")
    msg.append(f"现货上市: {'是' if spot_listed else '否'}")
    msg.append(f"合约上市: {'是' if futures_listed else '否'}")
    msg.append("")
    msg.append("⚠ 上市信息准确性仅截至公告发出时。")
    return "\n".join(msg)


def schedule_airdrop_reminder(item):
    """如果空投时间可解析，则在该时间的前20分钟推送提醒"""
    time_str = item.get("time")
    token = item.get("token", "未知")
    if not time_str:
        return

    try:
        today = datetime.date.today()
        # 处理 24小时制时间
        airdrop_time = datetime.datetime.strptime(time_str, "%H:%M").time()
        airdrop_dt = datetime.datetime.combine(today, airdrop_time)
        reminder_time = airdrop_dt - datetime.timedelta(minutes=20)

        # 若提醒时间已过，则不创建任务
        if reminder_time < datetime.datetime.now():
            return

        trigger = DateTrigger(run_date=reminder_time, timezone="Asia/Shanghai")
        job_id = f"reminder_{token}"

        def send_reminder():
            msg_handler.send_to_wx(f"⏰ 提醒：{token} 空投将在 {time_str} 开始，请注意参与！")

        scheduler.add_job(send_reminder, trigger, id=job_id)
        print(f"✅ 已为 {token} 安排提醒任务（{reminder_time.strftime('%H:%M')}）")

    except Exception as e:
        print(f"⚠ 无法解析时间字段 {time_str} ({token}): {e}")


# ======================
# 主逻辑
# ======================

def show_today_airdrops():
    """每天早上8点推送当天空投并设置提醒"""
    data = get_airdrop_data()
    if not data:
        return

    today = datetime.date.today().isoformat()
    message_lines = [f"📅 **今日预告（{today}）**"]
    found = False

    for item in data.get("airdrops", []):
        if item.get("date") == today:
            found = True
            message_lines.append(format_to_msg(item))
            # schedule_airdrop_reminder(item)

    if not found:
        message_lines.append("🔹 今日暂无空投。")

    msg_handler.send_to_wx("\n\n".join(message_lines))


def monitor_airdrop_updates():
    """每30秒检测更新"""
    global init_flag
    time.sleep(random.randint(5, 15))
    global last_airdrops
    data = get_airdrop_data()
    today = datetime.date.today().isoformat()
    if not data:
        return

    new_airdrops = {}
    for a in data.get("airdrops", []):
        token = a.get("token")
        # 突袭项目token是空字符串
        # if not token:
        #     continue
        if token not in new_airdrops:
            new_airdrops[token] = a
        else:
            # 分段 分数拼接处理 format为msg的时候会被自动分段
            old_points = str(new_airdrops[token].get("points", "")).strip()
            new_points = str(a.get("points", "")).strip()
            if old_points and new_points:
                new_airdrops[token]["points"] = f"{old_points} {new_points}"

    messages = []

    for token, new_item in new_airdrops.items():
        old_item = last_airdrops.get(token, {})
        if not old_item:
            if today == new_item.get("date"):
                msg = format_to_msg(new_item)
                messages.append(msg)
                schedule_airdrop_reminder(new_item)
        else:
            old_points = old_item.get("points", "")
            new_points = new_item.get("points", "")
            if init_flag and today == new_item.get("date") and old_points != "" and new_points != "":
                schedule_airdrop_reminder(new_item)
            if old_points == "" and new_points != "":
                messages.append(format_to_msg(new_item))
                schedule_airdrop_reminder(new_item)

    last_airdrops = new_airdrops
    init_flag = False

    if messages:
        msg_handler.send_to_wx("\n\n".join(messages))


# ======================
# 启动调度器
# ======================

def main():
    global last_airdrops
    last_airdrops = {a["token"]: a for a in (get_airdrop_data() or {}).get("airdrops", [])}

    # 主要任务
    scheduler.add_job(monitor_airdrop_updates, "interval", seconds=20, id="monitor_airdrop")
    scheduler.add_job(show_today_airdrops, "cron", hour=8, minute=0, id="daily_push")

    scheduler.start()
    print("✅ 空投监测系统已启动（含提醒功能）")

    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("\n⏹ 已停止监测。")


if __name__ == "__main__":
    main()