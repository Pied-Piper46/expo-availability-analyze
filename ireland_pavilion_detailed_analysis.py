#!/usr/bin/env python3
"""
アイルランドパビリオン詳細分析スクリプト

各アイルランドパビリオン（C060, C063, C066）の解放パターンを詳細分析：
- 曜日別解放パターン
- 日付別解放分布
- 時系列での解放傾向
- 解放の規則性や特徴の分析
"""

import json
import argparse
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import statistics
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import rcParams
import seaborn as sns

# フォント設定
plt.rcParams['font.family'] = ['DejaVu Sans', 'sans-serif']
rcParams['axes.unicode_minus'] = False

# パビリオン情報
PAVILION_INFO = {
    'C060': {
        'name': 'アイルランド生演奏',
        'color': '#ff6b6b'
    },
    'C063': {
        'name': 'アイルランドバンドライブ',
        'color': '#4ecdc4'
    },
    'C066': {
        'name': 'アイルランド生演奏なし',
        'color': '#45b7d1'
    }
}

def load_data():
    """JSONLファイルからデータを読み込み"""
    try:
        with open('availability_log.jsonl', 'r', encoding='utf-8') as file:
            data = [json.loads(line) for line in file]
        print(f"✅ {len(data)}件のデータを読み込みました")
        return data
    except FileNotFoundError:
        print("❌ availability_log.jsonl ファイルが見つかりません")
        return []
    except Exception as e:
        print(f"❌ データ読み込みエラー: {e}")
        return []

def parse_timestamp(timestamp_str):
    """タイムスタンプをパース（UTC → JST変換）"""
    try:
        utc_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        jst_time = utc_time + timedelta(hours=9)
        return jst_time
    except:
        return None

def analyze_weekday_patterns(release_data):
    """曜日別解放パターンを分析"""
    weekday_patterns = {}

    for pavilion_code, releases in release_data.items():
        weekday_counts = defaultdict(int)
        weekday_times = defaultdict(list)

        for release in releases:
            weekday = release['date'].weekday()  # 0=月曜日, 6=日曜日
            weekday_counts[weekday] += 1
            weekday_times[weekday].append(release['time_slot'])

        weekday_patterns[pavilion_code] = {
            'counts': dict(weekday_counts),
            'times': dict(weekday_times)
        }

    return weekday_patterns

def analyze_temporal_trends(release_data):
    """時系列での解放傾向を分析"""
    temporal_trends = {}

    for pavilion_code, releases in release_data.items():
        # 日付別集計
        daily_counts = defaultdict(int)
        weekly_counts = defaultdict(int)
        monthly_counts = defaultdict(int)

        for release in releases:
            date = release['date']
            daily_counts[date.strftime('%Y-%m-%d')] += 1

            # 週の開始日（月曜日）を計算
            week_start = date - timedelta(days=date.weekday())
            weekly_counts[week_start.strftime('%Y-%m-%d')] += 1

            monthly_counts[date.strftime('%Y-%m')] += 1

        temporal_trends[pavilion_code] = {
            'daily': dict(daily_counts),
            'weekly': dict(weekly_counts),
            'monthly': dict(monthly_counts)
        }

    return temporal_trends

def analyze_release_regularity(release_data):
    """解放の規則性を分析"""
    regularity_analysis = {}

    for pavilion_code, releases in release_data.items():
        # 解放日の間隔を計算
        release_dates = sorted([r['date'] for r in releases])
        intervals = []

        for i in range(1, len(release_dates)):
            interval = (release_dates[i] - release_dates[i-1]).days
            intervals.append(interval)

        # 時間帯の分析
        time_patterns = defaultdict(int)
        for release in releases:
            time_patterns[release['time_slot']] += 1

        # 連続解放日の分析
        consecutive_days = []
        current_streak = 1

        for i in range(1, len(release_dates)):
            if (release_dates[i] - release_dates[i-1]).days == 1:
                current_streak += 1
            else:
                if current_streak > 1:
                    consecutive_days.append(current_streak)
                current_streak = 1

        if current_streak > 1:
            consecutive_days.append(current_streak)

        regularity_analysis[pavilion_code] = {
            'intervals': intervals,
            'interval_stats': {
                'mean': statistics.mean(intervals) if intervals else 0,
                'median': statistics.median(intervals) if intervals else 0,
                'mode': statistics.mode(intervals) if intervals else 0,
                'std': statistics.stdev(intervals) if len(intervals) > 1 else 0
            },
            'time_patterns': dict(time_patterns),
            'consecutive_days': consecutive_days,
            'max_consecutive': max(consecutive_days) if consecutive_days else 1
        }

    return regularity_analysis

def create_weekday_visualization(weekday_patterns):
    """曜日別解放パターンの可視化"""
    weekdays_jp = ['月', '火', '水', '木', '金', '土', '日']

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle('曜日別解放パターン分析', fontsize=16, fontweight='bold')

    for idx, (pavilion_code, data) in enumerate(weekday_patterns.items()):
        ax = axes[idx]

        # データ準備
        weekday_counts = [data['counts'].get(i, 0) for i in range(7)]
        color = PAVILION_INFO[pavilion_code]['color']

        # 棒グラフ作成
        bars = ax.bar(weekdays_jp, weekday_counts, color=color, alpha=0.7)

        # 値をバーの上に表示
        for bar, count in zip(bars, weekday_counts):
            if count > 0:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                       str(count), ha='center', va='bottom', fontweight='bold')

        ax.set_title(f'{PAVILION_INFO[pavilion_code]["name"]} ({pavilion_code})')
        ax.set_ylabel('解放回数')
        ax.set_xlabel('曜日')
        ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    plt.savefig('ireland_weekday_patterns.png', dpi=300, bbox_inches='tight')
    print("✅ 曜日別パターン図を保存: ireland_weekday_patterns.png")

def create_temporal_visualization(temporal_trends):
    """時系列可視化"""
    fig, axes = plt.subplots(3, 1, figsize=(15, 12))
    fig.suptitle('アイルランドパビリオン 時系列解放傾向', fontsize=16, fontweight='bold')

    for pavilion_code, data in temporal_trends.items():
        color = PAVILION_INFO[pavilion_code]['color']
        label = f'{PAVILION_INFO[pavilion_code]["name"]} ({pavilion_code})'

        # 月別トレンド
        monthly_data = data['monthly']
        if monthly_data:
            months = sorted(monthly_data.keys())
            counts = [monthly_data[month] for month in months]

            axes[0].plot(months, counts, marker='o', linewidth=2,
                        markersize=6, color=color, label=label)

    axes[0].set_title('月別解放回数トレンド')
    axes[0].set_ylabel('解放回数')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    axes[0].tick_params(axis='x', rotation=45)

    # 各パビリオンの詳細な日別トレンド
    for idx, (pavilion_code, data) in enumerate(temporal_trends.items()):
        if idx < 2:  # C060とC063のみ（C066は別途）
            ax = axes[idx + 1]
            daily_data = data['daily']

            if daily_data:
                dates = sorted(daily_data.keys())
                counts = [daily_data[date] for date in dates]
                date_objs = [datetime.strptime(date, '%Y-%m-%d') for date in dates]

                color = PAVILION_INFO[pavilion_code]['color']
                ax.plot(date_objs, counts, marker='o', linewidth=2,
                       markersize=4, color=color, alpha=0.7)
                ax.fill_between(date_objs, counts, alpha=0.2, color=color)

                ax.set_title(f'{PAVILION_INFO[pavilion_code]["name"]} - 日別解放パターン')
                ax.set_ylabel('解放回数')
                ax.grid(True, alpha=0.3)
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                ax.tick_params(axis='x', rotation=45)

    plt.tight_layout()
    plt.savefig('ireland_temporal_trends.png', dpi=300, bbox_inches='tight')
    print("✅ 時系列トレンド図を保存: ireland_temporal_trends.png")

def generate_detailed_report(weekday_patterns, temporal_trends, regularity_analysis, release_data):
    """詳細分析レポートを生成"""

    report = """
# アイルランドパビリオン詳細分析レポート

## 📊 基本統計情報

"""

    for pavilion_code in ['C060', 'C063', 'C066']:
        if pavilion_code in release_data:
            releases = release_data[pavilion_code]
            total = len(releases)

            # 期間計算
            dates = [r['date'] for r in releases]
            period_start = min(dates).strftime('%Y年%m月%d日')
            period_end = max(dates).strftime('%Y年%m月%d日')
            period_days = (max(dates) - min(dates)).days + 1

            report += f"""
### {PAVILION_INFO[pavilion_code]['name']} ({pavilion_code})
- **総解放回数**: {total}回
- **分析期間**: {period_start} ～ {period_end} ({period_days}日間)
- **平均解放頻度**: {total/period_days*7:.1f}回/週
"""

    report += "\n## 📅 曜日別解放パターン分析\n"

    weekdays_jp = ['月', '火', '水', '木', '金', '土', '日']
    for pavilion_code, data in weekday_patterns.items():
        report += f"\n### {PAVILION_INFO[pavilion_code]['name']} ({pavilion_code})\n"

        counts = data['counts']
        total_releases = sum(counts.values())

        report += "| 曜日 | 解放回数 | 割合(%) |\n|------|----------|----------|\n"

        for i, weekday in enumerate(weekdays_jp):
            count = counts.get(i, 0)
            percentage = (count / total_releases * 100) if total_releases > 0 else 0
            report += f"| {weekday}曜日 | {count}回 | {percentage:.1f}% |\n"

        # 特徴的なパターンの分析
        if counts:
            max_day = max(counts, key=counts.get)
            min_day = min(counts, key=counts.get) if min(counts.values()) > 0 else None

            report += f"\n**特徴**:\n"
            report += f"- 最も解放が多い曜日: {weekdays_jp[max_day]}曜日 ({counts[max_day]}回)\n"

            if min_day is not None:
                report += f"- 最も解放が少ない曜日: {weekdays_jp[min_day]}曜日 ({counts[min_day]}回)\n"

    report += "\n## ⏰ 解放の規則性分析\n"

    for pavilion_code, analysis in regularity_analysis.items():
        report += f"\n### {PAVILION_INFO[pavilion_code]['name']} ({pavilion_code})\n"

        intervals = analysis['intervals']
        stats = analysis['interval_stats']

        if intervals:
            report += f"""
**解放間隔の統計**:
- 平均間隔: {stats['mean']:.1f}日
- 中央値: {stats['median']:.1f}日
- 最頻値: {stats['mode']:.1f}日
- 標準偏差: {stats['std']:.1f}日

**連続解放分析**:
- 最大連続解放日数: {analysis['max_consecutive']}日
- 連続解放パターン: {analysis['consecutive_days'][:5]}... (上位5つ)
"""

        # 時間帯パターン
        time_patterns = analysis['time_patterns']
        if time_patterns:
            sorted_times = sorted(time_patterns.items(), key=lambda x: x[1], reverse=True)
            report += "\n**主要解放時間帯**:\n"
            for time_slot, count in sorted_times[:3]:
                percentage = count / sum(time_patterns.values()) * 100
                report += f"- {time_slot}: {count}回 ({percentage:.1f}%)\n"

    report += "\n## 🔍 パビリオン間比較\n"

    # 総解放回数比較
    totals = {code: len(releases) for code, releases in release_data.items()}
    sorted_totals = sorted(totals.items(), key=lambda x: x[1], reverse=True)

    report += "\n**解放回数ランキング**:\n"
    for i, (code, total) in enumerate(sorted_totals, 1):
        report += f"{i}. {PAVILION_INFO[code]['name']} ({code}): {total}回\n"

    # 特徴的なパターンの要約
    report += "\n## 📋 主要な発見事項\n"

    # C060の特徴
    if 'C060' in release_data:
        c060_weekday = weekday_patterns['C060']['counts']
        dominant_weekday = max(c060_weekday, key=c060_weekday.get)
        report += f"\n**{PAVILION_INFO['C060']['name']}**:\n"
        report += f"- 最も活発なパビリオン（{len(release_data['C060'])}回解放）\n"
        report += f"- {weekdays_jp[dominant_weekday]}曜日に集中的に解放される傾向\n"

    # C063の特徴
    if 'C063' in release_data:
        report += f"\n**{PAVILION_INFO['C063']['name']}**:\n"
        report += f"- 解放頻度が限定的（{len(release_data['C063'])}回のみ）\n"
        report += f"- 特別なイベント性の可能性\n"

    # C066の特徴
    if 'C066' in release_data:
        report += f"\n**{PAVILION_INFO['C066']['name']}**:\n"
        report += f"- 中程度の解放頻度（{len(release_data['C066'])}回）\n"
        report += f"- 生演奏なしの代替オプション\n"

    return report

def main():
    """メイン実行関数"""
    print("🎭 アイルランドパビリオン詳細分析を開始...")

    # データ読み込み
    data = load_data()
    if not data:
        return

    # アイルランドパビリオンのリリースデータを抽出
    target_pavilions = ['C060', 'C063', 'C066']
    release_data = defaultdict(list)

    for entry in data:
        if entry.get('pavilion_code') in target_pavilions and entry.get('status') == 0:
            timestamp = parse_timestamp(entry['timestamp'])
            if timestamp:
                release_data[entry['pavilion_code']].append({
                    'date': timestamp.date(),
                    'time': timestamp.time(),
                    'time_slot': entry['time_slot'],
                    'timestamp': timestamp
                })

    print(f"📊 分析対象データ:")
    for code in target_pavilions:
        count = len(release_data[code])
        print(f"  - {PAVILION_INFO[code]['name']} ({code}): {count}回")

    # 分析実行
    print("\n🔍 分析を実行中...")
    weekday_patterns = analyze_weekday_patterns(release_data)
    temporal_trends = analyze_temporal_trends(release_data)
    regularity_analysis = analyze_release_regularity(release_data)

    # 可視化
    print("\n📈 可視化を作成中...")
    create_weekday_visualization(weekday_patterns)
    create_temporal_visualization(temporal_trends)

    # レポート生成
    print("\n📝 詳細レポートを生成中...")
    report = generate_detailed_report(weekday_patterns, temporal_trends, regularity_analysis, release_data)

    with open('ireland_pavilion_detailed_report.md', 'w', encoding='utf-8') as f:
        f.write(report)

    print("✅ 詳細分析完了!")
    print("📁 生成ファイル:")
    print("  - ireland_weekday_patterns.png (曜日別パターン)")
    print("  - ireland_temporal_trends.png (時系列トレンド)")
    print("  - ireland_pavilion_detailed_report.md (詳細レポート)")

if __name__ == "__main__":
    main()