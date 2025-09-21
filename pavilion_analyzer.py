#!/usr/bin/env python3
"""
パビリオン空き状況解放時刻分析ツール
日毎の解放時刻パターンを10分単位で分析し、各パビリオンごとのHTMLレポートを生成
"""

import json
from datetime import datetime, timedelta
from collections import defaultdict
import os
import argparse

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
    
    print("🔍 データを分析中...")
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
    
    print(f"\n✅ 分析完了! 各パビリオンのHTMLファイルを開いて結果を確認してください。")
    print("🌟 生成されたレポートの特徴:")
    print("  - 📅 日別解放時刻詳細（分単位で正確表示）")
    print("  - 🕒 JST（日本標準時）での表示")
    print("  - ⏰ 10分間隔フィルタ適用（同じ時刻帯の重複除去）")
    print("  - 📋 シンプルなテーブル形式での表示")

if __name__ == "__main__":
    main()