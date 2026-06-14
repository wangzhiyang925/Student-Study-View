"""统计与报告生成：把打卡数据汇总成文字 / HTML 报告。"""
from datetime import date, timedelta

from . import database as db


def _range_for(frequency):
    today = date.today()
    if frequency == "weekly":
        start = today - timedelta(days=6)
    else:  # daily
        start = today
    return start.isoformat(), today.isoformat()


def build_student_report(user, frequency="daily"):
    """生成单个学生的报告，返回 (纯文本, HTML)。"""
    start, end = _range_for(frequency)
    summary = db.subject_summary(user["id"], start, end)
    streak = db.streak_days(user["id"])
    period = "本周" if frequency == "weekly" else "今日"

    total_times = sum(v["times"] for v in summary.values())
    total_minutes = sum(v["minutes"] for v in summary.values())

    icons = {"语文": "📚", "数学": "🔢", "英语": "🔤"}

    # 纯文本
    lines = [f"【{user['display_name']}】{period}学习报告（{start} ~ {end}）", ""]
    for subj in db.SUBJECTS:
        s = summary[subj]
        lines.append(f"  {icons[subj]} {subj}：打卡 {s['times']} 次，共 {s['minutes']} 分钟")
    lines.append("")
    lines.append(f"  合计：打卡 {total_times} 次，学习 {total_minutes} 分钟")
    lines.append(f"  连续打卡：{streak} 天 🔥")
    text = "\n".join(lines)

    # HTML
    rows_html = ""
    for subj in db.SUBJECTS:
        s = summary[subj]
        rows_html += (
            f"<tr><td style='padding:8px 14px;font-size:16px'>{icons[subj]} {subj}</td>"
            f"<td style='padding:8px 14px;text-align:center'>{s['times']} 次</td>"
            f"<td style='padding:8px 14px;text-align:center'>{s['minutes']} 分钟</td></tr>"
        )
    html = f"""
    <div style="font-family:'Microsoft YaHei',sans-serif;max-width:520px;margin:auto;
                border:3px solid #FFD166;border-radius:16px;overflow:hidden">
      <div style="background:#FF6B6B;color:#fff;padding:18px;text-align:center">
        <div style="font-size:22px;font-weight:bold">🌟 {user['display_name']} 的{period}学习报告</div>
        <div style="font-size:13px;opacity:.9">{start} ~ {end}</div>
      </div>
      <table style="width:100%;border-collapse:collapse;background:#FFF9F0">
        <tr style="background:#FFE6A7">
          <th style="padding:10px 14px;text-align:left">科目</th>
          <th style="padding:10px 14px">打卡次数</th>
          <th style="padding:10px 14px">学习时长</th>
        </tr>
        {rows_html}
      </table>
      <div style="background:#06D6A0;color:#fff;padding:14px;text-align:center;font-size:15px">
        合计打卡 <b>{total_times}</b> 次 · 学习 <b>{total_minutes}</b> 分钟 · 连续 <b>{streak}</b> 天 🔥
      </div>
      <div style="padding:12px;text-align:center;color:#888;font-size:12px">
        继续加油，每天进步一点点！—— 学习小管家
      </div>
    </div>
    """
    return text, html


def build_overview_report(frequency="daily"):
    """生成所有学生的汇总报告（管理员/家长视角），返回 (文本, HTML)。"""
    students = db.list_students()
    start, end = _range_for(frequency)
    period = "本周" if frequency == "weekly" else "今日"

    text_parts = [f"全体学生{period}学习汇总（{start} ~ {end}）", "=" * 30]
    html_blocks = []
    if not students:
        text_parts.append("（暂无学生记录）")
    for stu in students:
        t, h = build_student_report(stu, frequency)
        text_parts.append("")
        text_parts.append(t)
        html_blocks.append(h)

    html = f"""
    <div style="background:#F0F7FF;padding:16px">
      <h2 style="font-family:'Microsoft YaHei';color:#118AB2;text-align:center">
        📊 全体学生{period}学习汇总
      </h2>
      {''.join(f'<div style="margin:14px 0">{b}</div>' for b in html_blocks)
        or '<p style="text-align:center;color:#888">暂无学生记录</p>'}
    </div>
    """
    return "\n".join(text_parts), html
