#!/usr/bin/env python3
"""
パビリオン空き状況解放時刻分析ツール
日毎の解放時刻パターンを10分単位で分析し、各パビリオンごとのHTMLレポートを生成
"""

import json
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import os
import argparse
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# パビリオン名のマッピング
PAVILION_NAMES = {
    'HEH0': '住友館',
    'EDF0': 'ヨルダン',
    'C060': 'アイルランド生演奏',
    'C063': 'アイルランドバンドライブ',
    'C066': 'アイルランド生演奏なし'
}

def load_and_process_data(file_path, start_date=None, end_date=None):
    """JSONLファイルを読み込み、データを処理"""
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                item = json.loads(line.strip())
                # 対象のパビリオンのみ処理
                if item['pavilion_code'] in PAVILION_NAMES:
                    data.append(item)
            except json.JSONDecodeError:
                continue
    
    # データを処理（UTCからJSTに変換）
    processed_data = []
    for item in data:
        # UTC時刻をJSTに変換
        utc_time = datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00'))
        jst_time = utc_time + timedelta(hours=9)  # JST = UTC + 9時間
        
        # 日時フィルタリング
        if start_date and jst_time.date() < start_date:
            continue
        if end_date and jst_time.date() > end_date:
            continue
        
        # 分単位で正確な時刻を保持
        exact_time = jst_time.replace(second=0, microsecond=0)
        
        processed_data.append({
            'timestamp': jst_time,
            'pavilion_code': item['pavilion_code'],
            'pavilion_name': PAVILION_NAMES[item['pavilion_code']],
            'time_slot': item['time_slot'],
            'status': item['status'],
            'date': jst_time.date().isoformat(),
            'exact_time': exact_time
        })
    
    return processed_data

def analyze_daily_release_patterns(data):
    """日毎の解放パターンを分析（10分間隔フィルタリング）"""
    pavilion_patterns = defaultdict(lambda: defaultdict(list))
    
    for item in data:
        pavilion = item['pavilion_code']
        date = item['date']
        exact_time = item['exact_time']
        
        # 日付と時刻のペアを記録
        pavilion_patterns[pavilion][date].append(exact_time)
    
    # 各日の時刻を15分間隔でフィルタリング
    filtered_patterns = defaultdict(lambda: defaultdict(list))
    
    for pavilion in pavilion_patterns:
        for date in pavilion_patterns[pavilion]:
            times = sorted(pavilion_patterns[pavilion][date])
            filtered_times = []
            
            for time in times:
                # 既に追加された時刻と10分以内かチェック
                should_add = True
                for existing_time in filtered_times:
                    time_diff = abs((time - existing_time).total_seconds())
                    if time_diff < 10 * 60:  # 10分 = 600秒
                        should_add = False
                        break
                
                if should_add:
                    filtered_times.append(time)
            
            filtered_patterns[pavilion][date] = filtered_times
    
    return filtered_patterns

def preprocess_releases_for_distribution(data, interval_minutes=15):
    """15分間隔重複除去による前処理"""
    target_pavilions = ['C060', 'C063', 'C066', 'HEH0', 'EDF0']
    raw_releases = defaultdict(list)

    # status=0（解放）のデータのみ収集
    for item in data:
        if item['pavilion_code'] in target_pavilions and item['status'] == 0:
            raw_releases[item['pavilion_code']].append(item)

    # 時系列でソート
    for pavilion_code in raw_releases:
        raw_releases[pavilion_code].sort(key=lambda x: x['timestamp'])

    print(f"📊 生データ統計 (status=0のみ):")
    for code in target_pavilions:
        count = len(raw_releases[code])
        print(f"  - {PAVILION_NAMES.get(code, code)}: {count}回（重複除去前）")

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

        print(f"  - {PAVILION_NAMES.get(code, code)}: {original}回 → {filtered}回")
        print(f"    除去: {removed}回 ({reduction_rate:.1f}%削減)")

    return filtered_releases

def calculate_release_time_distribution(data):
    """解放時間の確率分布を計算（15分単位、重複除去済み）"""
    pavilion_distributions = {}

    # 15分間隔重複除去を実行
    filtered_releases = preprocess_releases_for_distribution(data)

    # 対象パビリオンのみ処理
    target_pavilions = ['C060', 'C063', 'C066', 'HEH0', 'EDF0']

    # 10:00 ~ 20:00の全ての15分間隔を生成
    all_time_slots = []
    all_time_labels = []
    for hour in range(10, 20):
        for minute in [0, 15, 30, 45]:
            start_time = f"{hour:02d}:{minute:02d}"

            # 終了時間を計算
            end_minute = minute + 15
            end_hour = hour
            if end_minute >= 60:
                end_minute = end_minute - 60
                end_hour = hour + 1
            end_time = f"{end_hour:02d}:{end_minute:02d}"

            time_label = f"{start_time}~{end_time}"
            all_time_slots.append(start_time)
            all_time_labels.append(time_label)

    for pavilion_code in target_pavilions:
        if pavilion_code not in PAVILION_NAMES:
            continue

        pavilion_data = filtered_releases.get(pavilion_code, [])

        if not pavilion_data:
            continue

        # 15分単位で時間をグループ化
        time_groups = defaultdict(int)
        total_releases = len(pavilion_data)

        for item in pavilion_data:
            jst_time = item['timestamp']
            # 15分単位に丸める
            minutes = jst_time.minute
            rounded_minutes = (minutes // 15) * 15
            time_group = jst_time.replace(minute=rounded_minutes, second=0, microsecond=0).strftime('%H:%M')

            # 10:00 ~ 20:00の範囲内のみカウント
            if time_group in all_time_slots:
                time_groups[time_group] += 1

        if total_releases == 0:
            continue

        # 全ての時間帯について確率分布を計算（データがない時間帯は0%）
        distribution = {}
        for i, time_slot in enumerate(all_time_slots):
            count = time_groups[time_slot]
            probability = count / total_releases if total_releases > 0 else 0
            distribution[all_time_labels[i]] = {
                'count': count,
                'probability': probability,
                'percentage': probability * 100
            }

        pavilion_distributions[pavilion_code] = {
            'pavilion_name': PAVILION_NAMES[pavilion_code],
            'total_releases': total_releases,
            'distribution': distribution,
            'time_labels': all_time_labels
        }

    return pavilion_distributions

def create_distribution_visualization(pavilion_distributions):
    """確率分布の可視化を作成（各パビリオンごとに個別のグラフ）"""
    # バックエンドを設定（GUI不要）
    import matplotlib
    matplotlib.use('Agg')

    # 日本語フォントの設定（元の設定を復元）
    plt.rcParams['font.family'] = ['DejaVu Sans', 'Hiragino Sans', 'Yu Gothic', 'Meiryo', 'Takao', 'IPAexGothic', 'IPAPGothic', 'VL PGothic', 'Noto Sans CJK JP']

    target_pavilions = ['C060', 'C063', 'C066', 'HEH0', 'EDF0']
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7']

    created_files = []

    for i, pavilion_code in enumerate(target_pavilions):
        if pavilion_code not in pavilion_distributions:
            continue

        data = pavilion_distributions[pavilion_code]
        pavilion_name = data['pavilion_name']
        total_releases = data['total_releases']
        distribution = data['distribution']
        time_labels = data['time_labels']

        percentages = [distribution[time_label]['percentage'] for time_label in time_labels]

        # 個別のグラフを作成
        fig, ax = plt.subplots(1, 1, figsize=(16, 8))

        bars = ax.bar(range(len(time_labels)), percentages, color=colors[i], alpha=0.8, edgecolor='black', linewidth=0.5)

        # グラフの装飾
        ax.set_title(f'{pavilion_name} - 解放時間確率分布 (総解放回数: {total_releases}回)',
                    fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('解放時刻 (15分間隔)', fontsize=14)
        ax.set_ylabel('確率 (%)', fontsize=14)
        ax.grid(True, alpha=0.3, axis='y')

        # X軸の設定
        ax.set_xticks(range(len(time_labels)))
        ax.set_xticklabels(time_labels, rotation=45, ha='right', fontsize=10)
        ax.tick_params(axis='y', labelsize=12)

        # 上位3つの時間帯にパーセンテージを表示
        sorted_items = sorted(distribution.items(), key=lambda x: x[1]['percentage'], reverse=True)
        top_3_times = [item[0] for item in sorted_items[:3] if item[1]['percentage'] > 0]

        for j, (time_label, percentage) in enumerate(zip(time_labels, percentages)):
            if time_label in top_3_times and percentage > 1.0:  # 1%以上のもののみ表示
                ax.text(j, percentage + 0.2, f'{percentage:.1f}%',
                       ha='center', va='bottom', fontweight='bold', fontsize=9)

        # Y軸の範囲を調整
        max_percentage = max(percentages) if percentages else 0
        ax.set_ylim(0, max(max_percentage * 1.15, 5))  # 最低5%まで表示

        # ファイル名を生成（日本語文字を安全な文字に置換）
        safe_name = pavilion_name.replace("アイルランド", "Ireland").replace("生演奏", "Live").replace("バンドライブ", "Band").replace("なし", "NoLive")
        filename = f'{pavilion_code}_{safe_name.replace(" ", "_")}_distribution.png'

        plt.tight_layout()
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        created_files.append(filename)
        plt.close()  # メモリ節約のためにクローズ

    return created_files

def generate_distribution_table(pavilion_distributions):
    """確率分布表を生成"""
    print("\n" + "="*80)
    print("パビリオン解放時間確率分布表（15分単位・重複除去版）")
    print("="*80)

    target_pavilions = ['C060', 'C063', 'C066', 'HEH0', 'EDF0']

    for pavilion_code in target_pavilions:
        if pavilion_code not in pavilion_distributions:
            continue

        data = pavilion_distributions[pavilion_code]
        pavilion_name = data['pavilion_name']
        total_releases = data['total_releases']
        distribution = data['distribution']

        print(f"\n【{pavilion_name} ({pavilion_code})】")
        print(f"総解放回数: {total_releases}回")
        print("-" * 60)
        print(f"{'解放時刻':<15} {'回数':<8} {'確率(%)':<10}")
        print("-" * 60)

        # 確率の高い順にソート（確率が0より大きいもののみ表示）
        sorted_items = sorted(
            [(time, stats) for time, stats in distribution.items() if stats['percentage'] > 0],
            key=lambda x: x[1]['percentage'],
            reverse=True
        )

        for time, stats in sorted_items:
            count = stats['count']
            percentage = stats['percentage']
            print(f"{time:<15} {count:<8} {percentage:<10.2f}")

        # 上位3位を表示
        print(f"\n上位3位:")
        for i, (time, stats) in enumerate(sorted_items[:3], 1):
            print(f"  {i}位: {time} ({stats['percentage']:.2f}%)")

        # 0%の時間帯の数を表示
        zero_count = sum(1 for stats in distribution.values() if stats['percentage'] == 0)
        print(f"\n解放がなかった時間帯: {zero_count}個")

    print("\n" + "="*80)

def calculate_detailed_ireland_distribution(data):
    """アイルランドパビリオンの1分間隔詳細分析（15分間隔重複除去維持・1分間隔集計）"""
    ireland_pavilions = ['C060', 'C063', 'C066']

    # 15分間隔重複除去を実行（既存ロジック維持）
    filtered_releases = preprocess_releases_for_distribution(data, interval_minutes=15)

    detailed_distributions = {}

    # 10:00 ~ 20:00の全ての1分間隔を生成
    all_minute_slots = []
    all_minute_labels = []
    for hour in range(10, 20):
        for minute in range(60):
            time_label = f"{hour:02d}:{minute:02d}"
            all_minute_slots.append(time_label)
            all_minute_labels.append(time_label)

    for pavilion_code in ireland_pavilions:
        if pavilion_code not in PAVILION_NAMES:
            continue

        pavilion_data = filtered_releases.get(pavilion_code, [])

        if not pavilion_data:
            continue

        # 1分単位で時間をグループ化（15分間隔フィルタリング済みデータを1分単位で集計）
        time_groups = defaultdict(int)
        total_releases = len(pavilion_data)

        for item in pavilion_data:
            jst_time = item['timestamp']
            # 1分単位に丸める（秒は切り捨て）
            time_group = jst_time.replace(second=0, microsecond=0).strftime('%H:%M')

            # 10:00 ~ 20:00の範囲内のみカウント
            if time_group in all_minute_slots:
                time_groups[time_group] += 1

        if total_releases == 0:
            continue

        # 全ての時間帯について確率分布を計算（データがない時間帯は0%）
        distribution = {}
        for minute_slot in all_minute_slots:
            count = time_groups[minute_slot]
            probability = count / total_releases if total_releases > 0 else 0
            distribution[minute_slot] = {
                'count': count,
                'probability': probability,
                'percentage': probability * 100
            }

        detailed_distributions[pavilion_code] = {
            'pavilion_name': PAVILION_NAMES[pavilion_code],
            'total_releases': total_releases,
            'distribution': distribution,
            'minute_labels': all_minute_labels
        }

    return detailed_distributions

def save_minute_interval_distributions_json(data):
    """1分間隔集計でのcorrected_distributions.jsonファイルを作成"""
    import json

    # 15分間隔重複除去を実行（既存ロジック維持）
    filtered_releases = preprocess_releases_for_distribution(data, interval_minutes=15)

    # アイルランドパビリオンのみ対象
    ireland_pavilions = ['C060', 'C063', 'C066']

    minute_distributions = {}

    for pavilion_code in ireland_pavilions:
        if pavilion_code not in PAVILION_NAMES:
            continue

        pavilion_data = filtered_releases.get(pavilion_code, [])

        if not pavilion_data:
            continue

        # 1分単位で時間をグループ化
        time_groups = defaultdict(int)
        total_releases = len(pavilion_data)

        for item in pavilion_data:
            jst_time = item['timestamp']
            # 1分単位に丸める（秒は切り捨て）
            time_group = jst_time.replace(second=0, microsecond=0).strftime('%H:%M')

            # 10:00 ~ 20:00の範囲内のみカウント
            hour = jst_time.hour
            if 10 <= hour < 20:
                time_groups[time_group] += 1

        # 確率分布を計算（0%のデータは除外）
        distribution = {}
        for time_slot, count in time_groups.items():
            if count > 0:  # 実際に解放があった時間帯のみ
                probability = count / total_releases
                distribution[time_slot] = {
                    'count': count,
                    'probability': probability,
                    'percentage': probability * 100
                }

        if distribution:  # データがある場合のみ追加
            minute_distributions[pavilion_code] = {
                'pavilion_name': PAVILION_NAMES[pavilion_code],
                'total_releases': total_releases,
                'distribution': distribution
            }

    # JSONファイルとして保存
    output_filename = "corrected_distributions_1minute.json"
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(minute_distributions, f, ensure_ascii=False, indent=2)

    print(f"✅ 1分間隔集計のJSONファイルが '{output_filename}' として保存されました。")

    return minute_distributions

def create_simple_html_from_json():
    """corrected_distributions_1minute.jsonから簡単なHTMLグラフを作成"""
    import json
    import os

    json_filename = "corrected_distributions_1minute.json"

    if not os.path.exists(json_filename):
        print(f"❌ {json_filename} が見つかりません。")
        return

    # JSONファイルを読み込み
    with open(json_filename, 'r', encoding='utf-8') as f:
        data = json.load(f)

    html_content = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>アイルランドパビリオン 1分間隔解放時間分析</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #2E8B57 0%, #228B22 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }

        .header {
            background: linear-gradient(135deg, #2E8B57 0%, #228B22 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }

        .header h1 {
            font-size: 2.5em;
            font-weight: 700;
            margin-bottom: 10px;
        }

        .header p {
            font-size: 1.2em;
            opacity: 0.9;
        }

        .content {
            padding: 40px;
        }

        .pavilion-section {
            margin-bottom: 60px;
            background: #f8f9fa;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }

        .pavilion-title {
            font-size: 1.8em;
            font-weight: 700;
            color: #2E8B57;
            margin-bottom: 20px;
            text-align: center;
        }

        .chart-container {
            position: relative;
            height: 400px;
            margin: 30px 0;
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 3px 10px rgba(0,0,0,0.1);
        }

        .stats {
            text-align: center;
            margin-bottom: 20px;
            background: white;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 3px 10px rgba(0,0,0,0.1);
        }

        .summary {
            background: linear-gradient(135deg, #2E8B57 0%, #228B22 100%);
            color: white;
            padding: 30px;
            text-align: center;
            margin-top: 40px;
        }

        .summary h2 {
            margin-bottom: 15px;
        }

        .summary p {
            opacity: 0.9;
            line-height: 1.6;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🍀 アイルランドパビリオン 1分間隔分析</h1>
            <p>15分間隔重複除去 + 1分間隔集計による詳細解放時間分析</p>
        </div>

        <div class="content">
"""

    colors = ['rgba(255, 107, 107, 0.8)', 'rgba(78, 205, 196, 0.8)', 'rgba(69, 183, 209, 0.8)']
    border_colors = ['rgb(255, 107, 107)', 'rgb(78, 205, 196)', 'rgb(69, 183, 209)']

    chart_index = 0
    for pavilion_code, pavilion_data in data.items():
        pavilion_name = pavilion_data['pavilion_name']
        total_releases = pavilion_data['total_releases']
        distribution = pavilion_data['distribution']

        # 時間順にソートしてラベルとデータを作成
        sorted_times = sorted(distribution.keys())
        time_labels = [f"'{time}'" for time in sorted_times]
        percentages = [distribution[time]['percentage'] for time in sorted_times]

        html_content += f"""
            <div class="pavilion-section">
                <h2 class="pavilion-title">{pavilion_name}</h2>

                <div class="stats">
                    <strong>総解放回数: {total_releases}回</strong>
                </div>

                <div class="chart-container">
                    <canvas id="chart_{pavilion_code}"></canvas>
                </div>
            </div>
"""

        chart_index += 1

    html_content += """
        </div>

        <div class="summary">
            <h2>📊 分析サマリー</h2>
            <p>15分間隔での重複除去を行った後、1分間隔で集計した詳細な解放時間分析です。<br>
            各パビリオンの解放時間パターンが1分単位で確認できます。</p>
        </div>
    </div>

    <script>
"""

    # Chart.js用のJavaScriptを生成
    chart_index = 0
    for pavilion_code, pavilion_data in data.items():
        distribution = pavilion_data['distribution']

        # 時間順にソートしてデータを作成
        sorted_times = sorted(distribution.keys())
        time_labels = [f"'{time}'" for time in sorted_times]
        percentages = [distribution[time]['percentage'] for time in sorted_times]

        html_content += f"""
        // Chart for {pavilion_code}
        const ctx_{pavilion_code} = document.getElementById('chart_{pavilion_code}').getContext('2d');

        const chart_{pavilion_code} = new Chart(ctx_{pavilion_code}, {{
            type: 'bar',
            data: {{
                labels: [{', '.join(time_labels)}],
                datasets: [{{
                    label: '解放確率(%)',
                    data: {percentages},
                    backgroundColor: '{colors[chart_index]}',
                    borderColor: '{border_colors[chart_index]}',
                    borderWidth: 2,
                    borderRadius: 3,
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        display: false
                    }},
                    title: {{
                        display: true,
                        text: '1分間隔での解放確率分布',
                        font: {{
                            size: 16,
                            weight: 'bold'
                        }}
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        ticks: {{
                            callback: function(value) {{
                                return value + '%';
                            }}
                        }},
                        grid: {{
                            display: true,
                            color: 'rgba(0, 0, 0, 0.1)',
                            lineWidth: 1
                        }}
                    }},
                    x: {{
                        ticks: {{
                            maxRotation: 45,
                            font: {{
                                size: 10
                            }}
                        }},
                        grid: {{
                            display: false
                        }}
                    }}
                }}
            }}
        }});

"""
        chart_index += 1

    html_content += """
    </script>
</body>
</html>"""

    # HTMLファイルとして保存
    output_filename = "ireland_pavilion_1minute_analysis.html"
    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"✅ HTMLグラフが '{output_filename}' として保存されました。")
    return output_filename

def generate_detailed_ireland_html(detailed_distributions):
    """アイルランドパビリオン詳細分析のHTMLレポートを生成"""

    html_content = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>アイルランドパビリオン詳細解放時間分析（1分間隔）</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #2E8B57 0%, #228B22 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }

        .header {
            background: linear-gradient(135deg, #2E8B57 0%, #228B22 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }

        .header h1 {
            font-size: 2.5em;
            font-weight: 700;
            margin-bottom: 10px;
        }

        .header p {
            font-size: 1.2em;
            opacity: 0.9;
        }

        .content {
            padding: 40px;
        }

        .pavilion-section {
            margin-bottom: 60px;
            background: #f8f9fa;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }

        .pavilion-title {
            font-size: 1.8em;
            font-weight: 700;
            color: #2E8B57;
            margin-bottom: 20px;
            text-align: center;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 3px 10px rgba(0,0,0,0.1);
        }

        .stat-value {
            font-size: 1.5em;
            font-weight: 700;
            color: #2E8B57;
        }

        .stat-label {
            font-size: 0.9em;
            color: #666;
            margin-top: 5px;
        }

        .chart-container {
            position: relative;
            height: 400px;
            margin: 30px 0;
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 3px 10px rgba(0,0,0,0.1);
        }

        .window-info {
            background: #e8f5e8;
            border-left: 4px solid #2E8B57;
            padding: 15px;
            margin: 20px 0;
            border-radius: 5px;
        }

        .window-info h3 {
            color: #2E8B57;
            margin-bottom: 10px;
        }

        .summary {
            background: linear-gradient(135deg, #2E8B57 0%, #228B22 100%);
            color: white;
            padding: 30px;
            text-align: center;
            margin-top: 40px;
        }

        .summary h2 {
            margin-bottom: 15px;
        }

        .summary p {
            opacity: 0.9;
            line-height: 1.6;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🍀 アイルランドパビリオン詳細分析</h1>
            <p>1分間隔・15分間時間窓での高精度解放時間分析</p>
        </div>

        <div class="content">
"""

    ireland_pavilions = ['C060', 'C063', 'C066']
    colors = ['rgba(255, 107, 107, 0.8)', 'rgba(78, 205, 196, 0.8)', 'rgba(69, 183, 209, 0.8)']
    border_colors = ['rgb(255, 107, 107)', 'rgb(78, 205, 196)', 'rgb(69, 183, 209)']

    for i, pavilion_code in enumerate(ireland_pavilions):
        if pavilion_code not in detailed_distributions:
            continue

        data = detailed_distributions[pavilion_code]
        pavilion_name = data['pavilion_name']
        total_releases = data['total_releases']
        window_releases = data['window_releases']
        window_start = data['window_start']
        window_end = data['window_end']
        distribution = data['distribution']
        minute_slots = data['minute_slots']
        most_common_time = data['most_common_time']

        html_content += f"""
            <div class="pavilion-section">
                <h2 class="pavilion-title">{pavilion_name}</h2>

                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-value">{total_releases}回</div>
                        <div class="stat-label">総解放回数</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{window_releases}回</div>
                        <div class="stat-label">分析対象時間窓内</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{most_common_time}</div>
                        <div class="stat-label">最頻出時刻</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{window_start}～{window_end}</div>
                        <div class="stat-label">分析時間窓</div>
                    </div>
                </div>

                <div class="window-info">
                    <h3>📊 分析内容</h3>
                    <p>最も解放頻度の高い時刻（{most_common_time}）を中心とした15分間の時間窓で、1分間隔での詳細分析を実施。
                    重複除去は1分間隔で適用し、より細かな解放パターンを把握します。</p>
                </div>

                <div class="chart-container">
                    <canvas id="chart_{pavilion_code}"></canvas>
                </div>

            </div>
"""

    html_content += """
        </div>

        <div class="summary">
            <h2>📊 詳細分析サマリー</h2>
            <p>アイルランドパビリオンの解放時間は比較的固定的なパターンを示すため、1分間隔での詳細分析により、<br>
            より正確な予約タイミングの把握が可能になります。15分間の時間窓内での分布をご確認ください。</p>
        </div>
    </div>

    <script>
"""

    # Chart.js用のJavaScriptを生成
    for i, pavilion_code in enumerate(ireland_pavilions):
        if pavilion_code not in detailed_distributions:
            continue

        data = detailed_distributions[pavilion_code]
        minute_slots = data['minute_slots']
        distribution = data['distribution']

        chart_labels = [f"'{slot}'" for slot in minute_slots]
        chart_data = [distribution[slot]['percentage'] for slot in minute_slots]

        html_content += f"""
        // Chart for {pavilion_code}
        const ctx_{pavilion_code} = document.getElementById('chart_{pavilion_code}').getContext('2d');

        const chart_{pavilion_code} = new Chart(ctx_{pavilion_code}, {{
            type: 'bar',
            data: {{
                labels: [{', '.join(chart_labels)}],
                datasets: [{{
                    label: '解放確率(%)',
                    data: {chart_data},
                    backgroundColor: '{colors[i]}',
                    borderColor: '{border_colors[i]}',
                    borderWidth: 2,
                    borderRadius: 3,
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        display: false
                    }},
                    title: {{
                        display: true,
                        text: '1分間隔での解放確率分布（15分間時間窓）',
                        font: {{
                            size: 16,
                            weight: 'bold'
                        }}
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        max: Math.ceil(Math.max(...{chart_data}) / 10) * 10,
                        ticks: {{
                            stepSize: 10,
                            callback: function(value) {{
                                return value + '%';
                            }}
                        }},
                        grid: {{
                            display: true,
                            color: 'rgba(0, 0, 0, 0.1)',
                            lineWidth: 1
                        }}
                    }},
                    x: {{
                        ticks: {{
                            maxRotation: 45,
                            font: {{
                                size: 10
                            }}
                        }},
                        grid: {{
                            display: false
                        }}
                    }}
                }}
            }}
        }});

"""

    html_content += """
    </script>
</body>
</html>"""

    return html_content

def generate_distribution_html(pavilion_distributions):
    """確率分布のHTMLレポートを生成"""
    target_pavilions = ['C060', 'C063', 'C066', 'HEH0', 'EDF0']

    html_content = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>パビリオン解放時間確率分布レポート（15分重複除去版）</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }

        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }

        .header h1 {
            font-size: 2.5em;
            font-weight: 700;
            margin-bottom: 10px;
        }

        .header p {
            font-size: 1.2em;
            opacity: 0.9;
        }

        .content {
            padding: 40px;
        }

        .pavilion-section {
            margin-bottom: 60px;
            background: #f8f9fa;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }

        .pavilion-title {
            font-size: 1.8em;
            font-weight: 700;
            color: #667eea;
            margin-bottom: 20px;
            text-align: center;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }

        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 3px 10px rgba(0,0,0,0.1);
            display: inline-block;
            margin: 0 auto;
            max-width: fit-content;
        }

        .stat-card-container {
            text-align: center;
            margin-bottom: 30px;
        }

        .stat-value {
            font-size: 1.2em;
            font-weight: 700;
            color: #667eea;
        }

        .stat-label {
            font-size: 0.9em;
            color: #666;
            margin-top: 5px;
        }

        .chart-container {
            position: relative;
            height: 400px;
            margin: 30px 0;
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 3px 10px rgba(0,0,0,0.1);
        }

        .top-times {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 3px 10px rgba(0,0,0,0.1);
        }

        .top-times h3 {
            color: #667eea;
            margin-bottom: 15px;
            font-size: 1.3em;
        }

        .top-time-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid #eee;
        }

        .top-time-item:last-child {
            border-bottom: none;
        }

        .rank {
            background: #667eea;
            color: white;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
        }

        .time-range {
            font-weight: 600;
            color: #333;
        }

        .percentage {
            background: #e8f2ff;
            color: #667eea;
            padding: 5px 10px;
            border-radius: 15px;
            font-weight: 600;
        }

        .summary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
            margin-top: 40px;
        }

        .summary h2 {
            margin-bottom: 15px;
        }

        .summary p {
            opacity: 0.9;
            line-height: 1.6;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>パビリオン解放時間確率分布（修正版）</h1>
            <p>15分間隔重複除去による実用的解放予測分析</p>
        </div>

        <div class="content">
"""

    for pavilion_code in target_pavilions:
        if pavilion_code not in pavilion_distributions:
            continue

        data = pavilion_distributions[pavilion_code]
        pavilion_name = data['pavilion_name']
        total_releases = data['total_releases']
        distribution = data['distribution']
        time_labels = data['time_labels']


        html_content += f"""
            <div class="pavilion-section">
                <h2 class="pavilion-title">{pavilion_name} (総解放回数：{total_releases}回)</h2>

                <div class="stat-card-container">
                    <div class="stat-card">
                        <div class="stat-value">確率 ＝ その時間帯の解放回数 / 総解放回数</div>
                    </div>
                </div>

                <div class="chart-container">
                    <canvas id="chart_{pavilion_code}"></canvas>
                </div>

            </div>
"""

    html_content += """
        </div>

        <div class="summary">
            <h2>📊 分析サマリー</h2>
            <p>このレポートは過去の解放データを基に、各パビリオンの解放時間パターンを分析したものです。<br>
            予約を取りたい時間帯の参考としてご活用ください。</p>
        </div>
    </div>

    <script>
"""

    # Chart.js用のJavaScriptを生成
    colors = ['rgba(255, 107, 107, 0.8)', 'rgba(78, 205, 196, 0.8)', 'rgba(69, 183, 209, 0.8)', 'rgba(150, 206, 180, 0.8)', 'rgba(255, 234, 167, 0.8)']
    border_colors = ['rgb(255, 107, 107)', 'rgb(78, 205, 196)', 'rgb(69, 183, 209)', 'rgb(150, 206, 180)', 'rgb(255, 234, 167)']

    for i, pavilion_code in enumerate(target_pavilions):
        if pavilion_code not in pavilion_distributions:
            continue

        data = pavilion_distributions[pavilion_code]
        time_labels = data['time_labels']
        distribution = data['distribution']

        chart_labels = [f"'{label}'" for label in time_labels]
        chart_data = [distribution[time_label]['percentage'] for time_label in time_labels]

        html_content += f"""
        // Chart for {pavilion_code}
        const ctx_{pavilion_code} = document.getElementById('chart_{pavilion_code}').getContext('2d');
        const maxValue_{pavilion_code} = Math.max(...{chart_data});
        const maxIndex_{pavilion_code} = {chart_data}.indexOf(maxValue_{pavilion_code});

        const chart_{pavilion_code} = new Chart(ctx_{pavilion_code}, {{
            type: 'bar',
            data: {{
                labels: [{', '.join(chart_labels)}],
                datasets: [{{
                    label: '解放確率(%)',
                    data: {chart_data},
                    backgroundColor: '{colors[i]}',
                    borderColor: '{border_colors[i]}',
                    borderWidth: 2,
                    borderRadius: 5,
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        display: false
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        max: Math.ceil(Math.max(...{chart_data}) / 20) * 20,
                        ticks: {{
                            stepSize: 20,
                            callback: function(value) {{
                                return value + '%';
                            }}
                        }},
                        grid: {{
                            display: true,
                            color: 'rgba(0, 0, 0, 0.1)',
                            lineWidth: 1
                        }}
                    }},
                    x: {{
                        ticks: {{
                            maxRotation: 45,
                            font: {{
                                size: 10
                            }}
                        }},
                        grid: {{
                            display: false,
                            tickLength: 5,
                            tickColor: 'rgba(0, 0, 0, 0.3)'
                        }},
                        border: {{
                            display: true
                        }}
                    }}
                }}
            }}
        }});

"""

    html_content += """
    </script>
</body>
</html>"""

    return html_content

def run_daily_analysis(data):
    """日別レポート分析を実行"""
    print("🔍 日別レポート分析を実行中...")
    patterns = analyze_daily_release_patterns(data)

    print(f"📈 分析対象:")
    for pavilion_code, pavilion_name in PAVILION_NAMES.items():
        if pavilion_code in patterns:
            print(f"  - {pavilion_name} ({pavilion_code})")

    print("\n🎨 HTMLレポートを生成中...")

    # 各パビリオンのHTMLレポートを生成
    for pavilion_code, pavilion_name in PAVILION_NAMES.items():
        if pavilion_code in patterns:
            html_content = generate_pavilion_html(
                pavilion_code,
                pavilion_name,
                patterns[pavilion_code]
            )

            output_file = f"{pavilion_code}_{pavilion_name.replace('(', '').replace(')', '').replace('~', '-').replace(':', '')}_report.html"
            # ファイル名を安全にする
            output_file = output_file.replace('/', '-')

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html_content)

            print(f"  ✅ {pavilion_name}: {output_file}")

    print(f"\n✅ 日別レポート分析完了! 各パビリオンのHTMLファイルを開いて結果を確認してください。")
    print("🌟 生成されたレポートの特徴:")
    print("  - 📅 日別解放時刻詳細（分単位で正確表示）")
    print("  - 🕒 JST（日本標準時）での表示")
    print("  - ⏰ 10分間隔フィルタ適用（同じ時刻帯の重複除去）")
    print("  - 📋 シンプルなテーブル形式での表示")

def run_ireland_detailed_analysis(data):
    """アイルランドパビリオン詳細分析を実行"""
    print(f"🍀 アイルランドパビリオン詳細分析を実行中...")

    # status=0のデータのみをフィルタリング
    status_0_data = [item for item in data if item['status'] == 0]

    if not status_0_data:
        print("status=0のデータが見つかりません。")
        return

    # 1分間隔集計のJSONファイルを作成
    print(f"\n📊 1分間隔集計のJSONファイルを作成中...")
    minute_distributions = save_minute_interval_distributions_json(status_0_data)

    if not minute_distributions:
        print("アイルランドパビリオン（C060, C063, C066）のstatus=0データが見つかりません。")
        return

    # JSONからHTMLグラフを作成
    print(f"\n🎨 HTMLグラフを生成中...")
    html_filename = create_simple_html_from_json()

    print(f"\n✅ アイルランドパビリオン詳細分析完了!")
    print("🌟 作成されたファイル:")
    print("  - 📄 corrected_distributions_1minute.json (1分間隔集計データ)")
    print(f"  - 🎨 {html_filename} (HTMLグラフ)")
    print("  - 🕐 15分間隔重複除去 + 1分間隔集計")
    print("  - 🕒 JST（日本標準時）での時刻表示")
    print("  - 📊 解放があった時間帯のみ記録")

def run_distribution_analysis(data):
    """確率分布分析を実行"""
    print(f"🔍 解放時間確率分布を分析中...")

    # status=0のデータのみをフィルタリング
    status_0_data = [item for item in data if item['status'] == 0]

    if not status_0_data:
        print("status=0のデータが見つかりません。")
        return

    # 確率分布を計算
    pavilion_distributions = calculate_release_time_distribution(status_0_data)

    if not pavilion_distributions:
        print("対象パビリオン（C060, C063, C066）のstatus=0データが見つかりません。")
        return

    # 確率分布表を生成・表示
    generate_distribution_table(pavilion_distributions)

    # 可視化グラフを作成
    print(f"\n📊 グラフを生成中...")
    try:
        created_files = create_distribution_visualization(pavilion_distributions)
        print("✅ 各パビリオンのグラフが以下のファイルとして保存されました:")
        for filename in created_files:
            print(f"  - {filename}")
    except Exception as e:
        print(f"⚠️ グラフ生成エラー: {e}")

    # HTMLレポートを生成
    print(f"\n🎨 HTMLレポートを生成中...")
    try:
        html_content = generate_distribution_html(pavilion_distributions)
        html_filename = "pavilion_distribution_report.html"
        with open(html_filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"✅ HTMLレポートが '{html_filename}' として保存されました。")
        print("   ブラウザで開いてリッチな表示をご確認ください。")
    except Exception as e:
        print(f"⚠️ HTMLレポート生成エラー: {e}")

    print(f"\n✅ 確率分布分析完了!")
    print("🌟 分析結果の特徴:")
    print("  - 📊 15分単位での解放時間確率分布")
    print("  - 🕒 JST（日本標準時）での表示")
    print("  - 📈 各パビリオンの総解放回数を表示")
    print("  - 📋 確率の高い順にソート表示")
    print("  - 🎨 インタラクティブなHTMLレポート")

def generate_pavilion_html(pavilion_code, pavilion_name, patterns):
    """各パビリオンのHTMLレポートを生成（簡素化版）"""
    
    # 日付を取得してソート
    dates = sorted(patterns.keys())
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{pavilion_name} - 空き解放時刻分析</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: white;
                min-height: 100vh;
                padding: 20px;
                color: #333;
            }}
            
            .container {{
                max-width: 1000px;
                margin: 0 auto;
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                overflow: hidden;
            }}
            
            .header {{
                background: #667eea;
                color: white;
                padding: 40px;
                text-align: center;
            }}
            
            .header h1 {{
                font-size: 2.5em;
                font-weight: 700;
                margin-bottom: 10px;
            }}
            
            .header p {{
                font-size: 1.2em;
                font-weight: 700;
                opacity: 0.9;
            }}
            
            .content {{
                padding: 40px;
            }}
            
            .summary-table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
                background: white;
                border-radius: 10px;
                overflow: hidden;
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            }}
            
            .summary-table th, .summary-table td {{
                padding: 15px;
                text-align: left;
                border-bottom: 1px solid #eee;
            }}
            
            .summary-table th {{
                background: #667eea;
                color: white;
                font-weight: 600;
            }}
            
            .summary-table tr:hover {{
                background: #f8f9fa;
            }}
            
            .time-list {{
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
            }}
            
            .time-tag {{
                background: #FF9500;
                color: white;
                padding: 6px 12px;
                border-radius: 15px;
                font-size: 0.9em;
                font-weight: 700;
            }}
            
            .date-cell {{
                font-weight: 600;
                color: #667eea;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{pavilion_name}</h1>
                <p>空き開放時刻一覧</p>
                <p>（一度開放されてから10分間は新たな開放時刻として表示していません）</p>
                <p>（会場オープン時の開放も表示していません）</p>
            </div>
            
            <div class="content">
                <table class="summary-table">
                    <thead>
                        <tr>
                            <th>日付</th>
                            <th>開放時刻</th>
                        </tr>
                    </thead>
                    <tbody>
    """
    
    # 日別詳細テーブルを追加
    for date in dates:
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        # 曜日を含めた日付表示
        weekdays = ['月', '火', '水', '木', '金', '土', '日']
        weekday = weekdays[date_obj.weekday()]
        formatted_date = f"{date_obj.strftime('%Y年%m月%d日')}({weekday})"
        
        release_times = [t.strftime('%H:%M') for t in sorted(patterns[date])]
        time_count = len(release_times)
        
        html_content += f"""
                        <tr>
                            <td class="date-cell">{formatted_date}</td>
                            <td>
                                <div class="time-list">
        """
        
        for time in release_times:
            html_content += f'<span class="time-tag">{time}</span>'
        
        html_content += f"""
                                </div>
                            </td>
                        </tr>
        """
    
    html_content += """
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html_content

def parse_arguments():
    """コマンドライン引数を解析"""
    parser = argparse.ArgumentParser(
        description='パビリオン空き状況解放時刻分析ツール',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用例:
  # 全期間を対象に分析
  python pavilion_analyzer.py
  
  # 2024年1月1日から2024年1月31日までを対象に分析
  python pavilion_analyzer.py --start 2024-01-01 --end 2024-01-31
  
  # 2024年1月15日以降を対象に分析
  python pavilion_analyzer.py --start 2024-01-15
        '''
    )
    
    parser.add_argument(
        '--start', '-s',
        type=str,
        help='分析開始日（YYYY-MM-DD形式、例: 2024-01-01）'
    )
    
    parser.add_argument(
        '--end', '-e',
        type=str,
        help='分析終了日（YYYY-MM-DD形式、例: 2024-01-31）'
    )
    
    parser.add_argument(
        '--input', '-i',
        type=str,
        default='availability_log.jsonl',
        help='入力ファイルパス（デフォルト: availability_log.jsonl）'
    )

    parser.add_argument(
        '--mode', '-m',
        type=str,
        choices=['daily', 'distribution', 'both', 'ireland-detailed'],
        default='both',
        help='分析モード: daily=日別レポート, distribution=確率分布, both=両方, ireland-detailed=アイルランド詳細分析（デフォルト: both）'
    )

    return parser.parse_args()

def main():
    """メイン処理"""
    args = parse_arguments()
    
    # 日付パラメータの解析
    start_date = None
    end_date = None
    
    if args.start:
        try:
            start_date = datetime.strptime(args.start, '%Y-%m-%d').date()
        except ValueError:
            print(f"エラー: 開始日の形式が正しくありません: {args.start}")
            print("正しい形式: YYYY-MM-DD (例: 2024-01-01)")
            return
    
    if args.end:
        try:
            end_date = datetime.strptime(args.end, '%Y-%m-%d').date()
        except ValueError:
            print(f"エラー: 終了日の形式が正しくありません: {args.end}")
            print("正しい形式: YYYY-MM-DD (例: 2024-01-31)")
            return
    
    # 日付の妥当性チェック
    if start_date and end_date and start_date > end_date:
        print("エラー: 開始日が終了日より後になっています。")
        return
    
    input_file = args.input
    
    if not os.path.exists(input_file):
        print(f"エラー: {input_file} が見つかりません。")
        return
    
    # 分析期間の表示
    period_info = "全期間"
    if start_date or end_date:
        if start_date and end_date:
            period_info = f"{start_date.strftime('%Y年%m月%d日')} ～ {end_date.strftime('%Y年%m月%d日')}"
        elif start_date:
            period_info = f"{start_date.strftime('%Y年%m月%d日')} 以降"
        elif end_date:
            period_info = f"{end_date.strftime('%Y年%m月%d日')} 以前"
    
    print(f"📊 データを読み込み中... ({period_info})")
    data = load_and_process_data(input_file, start_date, end_date)
    
    if not data:
        print("対象パビリオンのデータが見つかりません。")
        return
    
    # 分析モードに応じて実行
    mode = args.mode

    if mode in ['daily', 'both']:
        print("\n" + "="*60)
        print("【日別レポート分析】")
        print("="*60)
        run_daily_analysis(data)

    if mode in ['distribution', 'both']:
        print("\n" + "="*60)
        print("【確率分布分析】")
        print("="*60)
        run_distribution_analysis(data)

    if mode == 'ireland-detailed':
        print("\n" + "="*60)
        print("【アイルランドパビリオン詳細分析】")
        print("="*60)
        run_ireland_detailed_analysis(data)

    print(f"\n🎉 全ての分析が完了しました！")
    if mode == 'both':
        print("📊 実行された分析:")
        print("  - 日別解放時刻レポート（HTMLファイル）")
        print("  - 解放時間確率分布（グラフとテーブル）")
    elif mode == 'ireland-detailed':
        print("📊 実行された分析:")
        print("  - アイルランドパビリオン1分間隔詳細分析（HTMLファイル）")

if __name__ == "__main__":
    main()