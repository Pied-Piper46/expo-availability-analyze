#!/usr/bin/env python3
"""
アイルランドパビリオン修正版分析スクリプト

15分間隔での重複除去を実装し、より実用的な解放予測分析を実行
- 同一パビリオンで15分以内の解放は1回の解放イベントとして扱う
- ユーザー視点での実用的な解放タイミング分析
- 予測に役立つ解放パターンの抽出
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

def preprocess_releases_for_prediction(data, interval_minutes=15):
    """
    予測用の解放データ前処理
    同一パビリオンで15分以内の解放を1回の解放イベントとして扱う
    """
    target_pavilions = ['C060', 'C063', 'C066']
    raw_releases = defaultdict(list)

    # まず生データを収集
    for entry in data:
        if entry.get('pavilion_code') in target_pavilions and entry.get('status') == 0:
            timestamp = parse_timestamp(entry['timestamp'])
            if timestamp:
                raw_releases[entry['pavilion_code']].append({
                    'timestamp': timestamp,
                    'time_slot': entry['time_slot'],
                    'date': timestamp.date(),
                    'time': timestamp.time()
                })

    # 時系列でソート
    for pavilion_code in raw_releases:
        raw_releases[pavilion_code].sort(key=lambda x: x['timestamp'])

    print(f"📊 生データ統計:")
    for code in target_pavilions:
        count = len(raw_releases[code])
        print(f"  - {PAVILION_INFO[code]['name']} ({code}): {count}回（重複除去前）")

    # 15分間隔での重複除去
    filtered_releases = defaultdict(list)
    removed_count = defaultdict(int)

    for pavilion_code, releases in raw_releases.items():
        if not releases:
            continue

        last_release_time = None

        for release in releases:
            current_time = release['timestamp']

            # 前回解放から15分経過していれば有効な解放とする
            if (last_release_time is None or
                (current_time - last_release_time).total_seconds() >= interval_minutes * 60):

                filtered_releases[pavilion_code].append(release)
                last_release_time = current_time
            else:
                removed_count[pavilion_code] += 1

    print(f"\n🔧 15分間隔重複除去結果:")
    for code in target_pavilions:
        original = len(raw_releases[code])
        filtered = len(filtered_releases[code])
        removed = removed_count[code]
        reduction_rate = (removed / original * 100) if original > 0 else 0

        print(f"  - {PAVILION_INFO[code]['name']} ({code}):")
        print(f"    原データ: {original}回 → 修正後: {filtered}回")
        print(f"    除去: {removed}回 ({reduction_rate:.1f}%削減)")

    return filtered_releases

def calculate_corrected_distribution(release_data):
    """修正版確率分布を計算"""
    pavilion_distributions = {}

    # 15分単位の時間ラベルを生成
    time_labels = []
    for hour in range(10, 20):  # 10:00-19:45
        for minute in [0, 15, 30, 45]:
            start_time = f"{hour:02d}:{minute:02d}"
            end_hour = hour if minute < 45 else hour + 1
            end_minute = minute + 15 if minute < 45 else 0
            end_time = f"{end_hour:02d}:{end_minute:02d}"
            time_labels.append(f"{start_time}~{end_time}")

    for pavilion_code, releases in release_data.items():
        if not releases:
            continue

        total_releases = len(releases)
        distribution = {}

        # 各時間帯での解放回数をカウント
        time_counts = defaultdict(int)

        for release in releases:
            time_obj = release['time']
            hour = time_obj.hour
            minute = time_obj.minute

            # 15分単位に丸める
            interval_minute = (minute // 15) * 15

            if 10 <= hour < 20:  # 営業時間内のみ
                start_time = f"{hour:02d}:{interval_minute:02d}"
                end_hour = hour if interval_minute < 45 else hour + 1
                end_minute = interval_minute + 15 if interval_minute < 45 else 0

                if end_hour < 20:  # 20:00未満まで
                    end_time = f"{end_hour:02d}:{end_minute:02d}"
                    time_range = f"{start_time}~{end_time}"
                    time_counts[time_range] += 1

        # 確率分布を計算
        for time_label in time_labels:
            count = time_counts.get(time_label, 0)
            percentage = (count / total_releases * 100) if total_releases > 0 else 0

            distribution[time_label] = {
                'count': count,
                'percentage': percentage
            }

        pavilion_distributions[pavilion_code] = {
            'pavilion_name': PAVILION_INFO[pavilion_code]['name'],
            'total_releases': total_releases,
            'distribution': distribution,
            'time_labels': time_labels
        }

    return pavilion_distributions

def create_comparison_visualization(original_data, corrected_data):
    """修正前後の比較可視化"""
    fig, axes = plt.subplots(3, 2, figsize=(20, 15))
    fig.suptitle('解放データ修正前後の比較分析', fontsize=16, fontweight='bold')

    pavilion_codes = ['C060', 'C063', 'C066']

    for idx, pavilion_code in enumerate(pavilion_codes):
        # 修正前のデータ
        if pavilion_code in original_data:
            orig_releases = original_data[pavilion_code]
            orig_hourly = defaultdict(int)
            for release in orig_releases:
                hour = release['time'].hour
                if 10 <= hour < 20:
                    orig_hourly[hour] += 1
        else:
            orig_hourly = {}

        # 修正後のデータ
        if pavilion_code in corrected_data:
            corr_releases = corrected_data[pavilion_code]
            corr_hourly = defaultdict(int)
            for release in corr_releases:
                hour = release['time'].hour
                if 10 <= hour < 20:
                    corr_hourly[hour] += 1
        else:
            corr_hourly = {}

        hours = list(range(10, 20))
        orig_counts = [orig_hourly.get(h, 0) for h in hours]
        corr_counts = [corr_hourly.get(h, 0) for h in hours]

        color = PAVILION_INFO[pavilion_code]['color']

        # 修正前
        ax1 = axes[idx, 0]
        bars1 = ax1.bar(hours, orig_counts, color=color, alpha=0.7)
        ax1.set_title(f'{PAVILION_INFO[pavilion_code]["name"]} - 修正前')
        ax1.set_ylabel('解放回数')
        ax1.set_xlabel('時間帯')
        ax1.grid(axis='y', alpha=0.3)

        # 値をバーの上に表示
        for bar, count in zip(bars1, orig_counts):
            if count > 0:
                ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                        str(count), ha='center', va='bottom', fontsize=9)

        # 修正後
        ax2 = axes[idx, 1]
        bars2 = ax2.bar(hours, corr_counts, color=color, alpha=0.7)
        ax2.set_title(f'{PAVILION_INFO[pavilion_code]["name"]} - 修正後（15分重複除去）')
        ax2.set_ylabel('解放回数')
        ax2.set_xlabel('時間帯')
        ax2.grid(axis='y', alpha=0.3)

        # 値をバーの上に表示
        for bar, count in zip(bars2, corr_counts):
            if count > 0:
                ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                        str(count), ha='center', va='bottom', fontsize=9)

        # Y軸の範囲を揃える
        max_y = max(max(orig_counts) if orig_counts else 0,
                   max(corr_counts) if corr_counts else 0)
        ax1.set_ylim(0, max_y * 1.2)
        ax2.set_ylim(0, max_y * 1.2)

    plt.tight_layout()
    plt.savefig('ireland_comparison_before_after.png', dpi=300, bbox_inches='tight')
    print("✅ 修正前後比較図を保存: ireland_comparison_before_after.png")

def analyze_weekday_patterns_corrected(release_data):
    """修正版曜日別解放パターンを分析"""
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

def generate_corrected_report(corrected_distributions, weekday_patterns, release_data, original_totals):
    """修正版詳細レポートを生成"""

    report = """
# アイルランドパビリオン修正版分析レポート
## 15分間隔重複除去による実用的解放予測分析

### 📊 データ修正効果

この分析では、**同一パビリオンで15分以内の解放を1回の解放イベント**として扱うことで、
より実用的な解放タイミング予測を可能にしました。

#### 修正前後の比較

| パビリオン | 修正前 | 修正後 | 削減率 | 削減理由 |
|------------|--------|--------|--------|----------|
"""

    for pavilion_code in ['C060', 'C063', 'C066']:
        if pavilion_code in release_data:
            original = original_totals.get(pavilion_code, 0)
            corrected = len(release_data[pavilion_code])
            reduction = original - corrected
            reduction_rate = (reduction / original * 100) if original > 0 else 0

            report += f"| {PAVILION_INFO[pavilion_code]['name']} ({pavilion_code}) | {original}回 | {corrected}回 | {reduction_rate:.1f}% | 短時間での連続解放除去 |\n"

    report += "\n### 🎯 修正後の解放時間確率分布\n"

    for pavilion_code, data in corrected_distributions.items():
        pavilion_name = data['pavilion_name']
        total_releases = data['total_releases']
        distribution = data['distribution']

        # 確率の高い時間帯TOP3を取得
        sorted_times = sorted(
            [(time, stats) for time, stats in distribution.items() if stats['percentage'] > 0],
            key=lambda x: x[1]['percentage'],
            reverse=True
        )

        report += f"\n#### {pavilion_name} ({pavilion_code})\n"
        report += f"**修正後総解放回数**: {total_releases}回\n\n"

        report += "| 解放時間帯 | 回数 | 確率(%) |\n|------------|------|--------|\n"

        for time_range, stats in sorted_times[:10]:  # TOP10表示
            report += f"| {time_range} | {stats['count']}回 | {stats['percentage']:.1f}% |\n"

        if sorted_times:
            top_time = sorted_times[0]
            report += f"\n**最頻出解放時間**: {top_time[0]} ({top_time[1]['percentage']:.1f}%)\n"

    report += "\n### 📅 修正後曜日別パターン\n"

    weekdays_jp = ['月', '火', '水', '木', '金', '土', '日']
    for pavilion_code, data in weekday_patterns.items():
        report += f"\n#### {PAVILION_INFO[pavilion_code]['name']} ({pavilion_code})\n"

        counts = data['counts']
        total_releases = sum(counts.values())

        report += "| 曜日 | 解放回数 | 割合(%) |\n|------|----------|----------|\n"

        for i, weekday in enumerate(weekdays_jp):
            count = counts.get(i, 0)
            percentage = (count / total_releases * 100) if total_releases > 0 else 0
            report += f"| {weekday}曜日 | {count}回 | {percentage:.1f}% |\n"

    report += "\n## 🚀 予測への活用方法\n\n"

    report += """
### 解放予測の精度向上

修正後のデータを使用することで以下の利点があります：

1. **ノイズ除去**: 短時間での重複解放を除去し、真の解放タイミングを抽出
2. **ユーザー視点**: 15分以内の解放は実質的に同一イベントとして扱い、実用性を向上
3. **予測精度**: より正確な解放パターンにより、事前準備の効果を最大化

### 推奨戦略

#### C060 (アイルランド生演奏)
- **最適戦略**: 修正後の最頻出時間帯に集中監視
- **事前準備**: 該当時間の5分前からスタンバイ

#### C063 (アイルランドバンドライブ)
- **希少性重視**: 限定的な解放パターンを正確に把握
- **確実性優先**: 高確率時間帯での確実な取得を目指す

#### C066 (アイルランド生演奏なし)
- **代替手段**: 他パビリオンが満席時のバックアップ
- **柔軟対応**: 複数時間帯での分散監視

"""

    return report

def main():
    """メイン実行関数"""
    print("🎭 アイルランドパビリオン修正版分析を開始...")
    print("📋 15分間隔重複除去による実用的解放予測分析\n")

    # データ読み込み
    data = load_data()
    if not data:
        return

    # 元データの統計を取得（比較用）
    target_pavilions = ['C060', 'C063', 'C066']
    original_totals = {}
    for pavilion_code in target_pavilions:
        count = len([entry for entry in data
                    if entry.get('pavilion_code') == pavilion_code and entry.get('status') == 0])
        original_totals[pavilion_code] = count

    # 修正版前処理（15分間隔重複除去）
    print("\n🔧 15分間隔重複除去を実行中...")
    corrected_release_data = preprocess_releases_for_prediction(data, interval_minutes=15)

    # 修正版確率分布計算
    print("\n📊 修正版確率分布を計算中...")
    corrected_distributions = calculate_corrected_distribution(corrected_release_data)

    # 修正版曜日別分析
    print("\n📅 修正版曜日別パターンを分析中...")
    weekday_patterns = analyze_weekday_patterns_corrected(corrected_release_data)

    # 比較可視化
    print("\n📈 修正前後の比較可視化を作成中...")
    # 元データも同じ形式で準備
    original_release_data = defaultdict(list)
    for entry in data:
        if entry.get('pavilion_code') in target_pavilions and entry.get('status') == 0:
            timestamp = parse_timestamp(entry['timestamp'])
            if timestamp:
                original_release_data[entry['pavilion_code']].append({
                    'timestamp': timestamp,
                    'time': timestamp.time(),
                    'date': timestamp.date()
                })

    create_comparison_visualization(original_release_data, corrected_release_data)

    # 修正版レポート生成
    print("\n📝 修正版詳細レポートを生成中...")
    corrected_report = generate_corrected_report(
        corrected_distributions, weekday_patterns, corrected_release_data, original_totals)

    with open('ireland_pavilion_corrected_report.md', 'w', encoding='utf-8') as f:
        f.write(corrected_report)

    # 修正版確率分布HTMLレポート生成用に元のpavilion_analyzer.pyを更新
    print("\n🎨 修正版HTMLレポート用データを準備中...")

    # 修正版データをJSONとして保存（元スクリプトで使用するため）
    corrected_data_for_html = {}
    for pavilion_code, data in corrected_distributions.items():
        corrected_data_for_html[pavilion_code] = data

    with open('corrected_distributions.json', 'w', encoding='utf-8') as f:
        json.dump(corrected_data_for_html, f, ensure_ascii=False, indent=2, default=str)

    print("✅ 修正版分析完了!")
    print("📁 生成ファイル:")
    print("  - ireland_comparison_before_after.png (修正前後比較)")
    print("  - ireland_pavilion_corrected_report.md (修正版詳細レポート)")
    print("  - corrected_distributions.json (修正版HTMLレポート用データ)")
    print("\n🎯 次のステップ:")
    print("  - pavilion_analyzer.pyを更新して修正版HTMLレポートを生成できます")

if __name__ == "__main__":
    main()