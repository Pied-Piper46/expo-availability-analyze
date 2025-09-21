#!/usr/bin/env python3
"""
パビリオン空き状況散布図表示ツール
日付を横軸、開放時間を縦軸とした散布図を生成
"""

import json
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from collections import defaultdict
import os
import argparse
import numpy as np

# 日本語フォント設定
plt.rcParams['font.family'] = ['Hiragino Sans', 'Yu Gothic', 'Meiryo', 'Takao', 'IPAexGothic', 'IPAPGothic', 'VL PGothic', 'Noto Sans CJK JP']

# パビリオン名のマッピング
PAVILION_NAMES = {
    'HEH0': '住友館',
    'EDF0': 'ヨルダン'
}

def load_and_process_data(file_path, start_date=None, end_date=None):
    """JSONLファイルを読み込み、データを処理"""
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                item = json.loads(line.strip())
                if item['pavilion_code'] in PAVILION_NAMES:
                    data.append(item)
            except json.JSONDecodeError:
                continue
    
    processed_data = []
    for item in data:
        utc_time = datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00'))
        jst_time = utc_time + timedelta(hours=9)
        
        if start_date and jst_time.date() < start_date:
            continue
        if end_date and jst_time.date() > end_date:
            continue
        
        exact_time = jst_time.replace(second=0, microsecond=0)
        
        processed_data.append({
            'timestamp': jst_time,
            'pavilion_code': item['pavilion_code'],
            'pavilion_name': PAVILION_NAMES[item['pavilion_code']],
            'time_slot': item['time_slot'],
            'status': item['status'],
            'date': jst_time.date(),
            'exact_time': exact_time
        })
    
    return processed_data

def analyze_release_patterns(data):
    """解放パターンを分析（10分間隔フィルタリング）"""
    pavilion_patterns = defaultdict(lambda: defaultdict(list))
    
    for item in data:
        pavilion = item['pavilion_code']
        date = item['date']
        exact_time = item['exact_time']
        
        pavilion_patterns[pavilion][date].append(exact_time)
    
    filtered_patterns = defaultdict(lambda: defaultdict(list))
    
    for pavilion in pavilion_patterns:
        for date in pavilion_patterns[pavilion]:
            times = sorted(pavilion_patterns[pavilion][date])
            filtered_times = []
            
            for time in times:
                should_add = True
                for existing_time in filtered_times:
                    time_diff = abs((time - existing_time).total_seconds())
                    if time_diff < 10 * 60:
                        should_add = False
                        break
                
                if should_add:
                    filtered_times.append(time)
            
            filtered_patterns[pavilion][date] = filtered_times
    
    return filtered_patterns

def create_scatter_plot(patterns, pavilion_code, pavilion_name):
    """散布図を作成"""
    dates = []
    times = []
    
    for date, time_list in patterns[pavilion_code].items():
        for time in time_list:
            dates.append(date)
            # 時刻を分単位の数値に変換（0:00 = 0, 1:00 = 60, etc.）
            time_minutes = time.hour * 60 + time.minute
            times.append(time_minutes)
    
    if not dates:
        print(f"{pavilion_name}のデータがありません")
        return
    
    fig, ax = plt.subplots(figsize=(15, 8))
    
    # 散布図をプロット
    ax.scatter(dates, times, alpha=0.6, s=30, c='#FF9500', edgecolors='white', linewidth=0.5)
    
    # グラフの設定
    ax.set_xlabel('日付', fontsize=12, fontweight='bold')
    ax.set_ylabel('開放時間', fontsize=12, fontweight='bold')
    ax.set_title(f'{pavilion_name} - 空き開放時間の推移', fontsize=16, fontweight='bold', pad=20)
    
    # X軸（日付）の設定
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(set(dates)) // 20)))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    # Y軸（時間）の設定
    y_ticks = np.arange(0, 24*60, 60)  # 1時間ごと
    y_labels = [f"{int(tick//60):02d}:00" for tick in y_ticks]
    ax.set_yticks(y_ticks)
    ax.set_yticklabels(y_labels)
    ax.set_ylim(0, 24*60)
    
    # グリッドを追加
    ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    ax.set_axisbelow(True)
    
    # 背景色を設定
    ax.set_facecolor('#f8f9fa')
    fig.patch.set_facecolor('white')
    
    # レイアウトを調整
    plt.tight_layout()
    
    # ファイル名を生成
    filename = f"{pavilion_code}_{pavilion_name}_scatter.png"
    filename = filename.replace('/', '-')
    
    # 画像を保存
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✅ {pavilion_name}の散布図を保存しました: {filename}")
    
    # グラフを表示
    plt.show()
    
    return filename

def parse_arguments():
    """コマンドライン引数を解析"""
    parser = argparse.ArgumentParser(
        description='パビリオン空き状況散布図表示ツール',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用例:
  # 全期間を対象に散布図を生成
  python scatter_plot_analyzer.py
  
  # 2024年1月1日から2024年1月31日までを対象に散布図を生成
  python scatter_plot_analyzer.py --start 2024-01-01 --end 2024-01-31
  
  # 2024年1月15日以降を対象に散布図を生成
  python scatter_plot_analyzer.py --start 2024-01-15
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
    
    return parser.parse_args()

def main():
    """メイン処理"""
    args = parse_arguments()
    
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
    
    if start_date and end_date and start_date > end_date:
        print("エラー: 開始日が終了日より後になっています。")
        return
    
    input_file = args.input
    
    if not os.path.exists(input_file):
        print(f"エラー: {input_file} が見つかりません。")
        return
    
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
    
    print("🔍 データを分析中...")
    patterns = analyze_release_patterns(data)
    
    print(f"📈 分析対象:")
    for pavilion_code, pavilion_name in PAVILION_NAMES.items():
        if pavilion_code in patterns:
            print(f"  - {pavilion_name} ({pavilion_code})")
    
    print("\n📊 散布図を生成中...")
    
    for pavilion_code, pavilion_name in PAVILION_NAMES.items():
        if pavilion_code in patterns:
            create_scatter_plot(patterns, pavilion_code, pavilion_name)
    
    print(f"\n✅ 散布図生成完了!")
    print("🌟 生成された散布図の特徴:")
    print("  - 📅 横軸: 日付")
    print("  - 🕒 縦軸: 開放時間（JST）")
    print("  - ⏰ 10分間隔フィルタ適用")
    print("  - 📋 PNG形式で保存")

if __name__ == "__main__":
    main()