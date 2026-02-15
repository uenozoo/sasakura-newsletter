from duckduckgo_search import DDGS
from datetime import datetime, timedelta
import time
from dateutil import parser
import re
from difflib import SequenceMatcher
import requests

def validate_url(url, timeout=5):
    """
    指定されたURLが有効か（ステータスコード200番台か）を確認する。
    無効またはタイムアウトの場合は False を返す。
    """
    if not url:
        return False
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.head(url, headers=headers, timeout=timeout, allow_redirects=True)
        if response.status_code >= 400:
            # HEADでダメならGETでも試す（一部サーバー対策）
            response = requests.get(url, headers=headers, timeout=timeout, stream=True)
            
        return 200 <= response.status_code < 300
    except requests.RequestException:
        return False

def is_similar(a, b, threshold=0.6):
    """タイトルaとbの類似度を判定"""
    return SequenceMatcher(None, a, b).ratio() > threshold

def fetch_news(topics, excluded_terms=None, target_date_start=None, target_date_end=None):
    ddgs = DDGS()
    news_results = {}
    
    # 日付フィルタリング用のヘルパー
    def is_in_date_range(date_str):
        if not date_str: return False
        try:
            # "2 minutes ago" などの相対表記は簡易的に無視するか、現在時刻として扱う（今回は過去ログ取得が主目的なので、絶対日付を持つものだけを重視する戦略もアリ）
            # ここでは dateutil で解析を試みる
            dt = parser.parse(date_str, fuzzy=True)
            # UTCオフセット等の調整は簡易化
            dt = dt.replace(tzinfo=None)
            
            if target_date_start and dt < target_date_start: return False
            if target_date_end and dt > target_date_end: return False
            return True
        except:
            return False # 解析不能なら安全側に倒して除外、または含める（要件次第）

    seen_titles = []

    for category, keywords in topics.items():
        print(f"カテゴリ: {category}")
        category_items = []
        
        for keyword in keywords:
            print(f"  検索中: {keyword} ...")
            try:
                # timelimit='m' (1ヶ月以内) で広めに取ってからフィルタするStrategy
                news_items = ddgs.news(
                    keywords=keyword,
                    region="jp-jp",
                    safesearch="off",
                    timelimit="m", 
                    max_results=10
                )
                
                for item in news_items:
                    title = item['title']
                    url = item['url']
                    date_str = item['date']
                    
                    # 1. 除外キーワード判定
                    if excluded_terms and any(term in title for term in excluded_terms):
                        continue
                        
                    # 2. 日付判定 (指定がある場合)
                    if (target_date_start or target_date_end) and not is_in_date_range(date_str):
                        continue

                    # 3. 重複判定
                    if any(is_similar(title, seen) for seen in seen_titles):
                        continue

                    # 4. リンク死活監視 (Fetching段階で行うと遅くなるが、品質重視ならここでやる)
                    # ここではデモ用にはコメントアウトし、後段処理または今回はMockで行う
                    # if not validate_url(url):
                    #    continue
                    
                    seen_titles.append(title)
                    
                    # フォーマット整理
                    try:
                        dt = parser.parse(date_str, fuzzy=True)
                        formatted_date = dt.strftime("%Y年%m月%d日")
                    except:
                        formatted_date = date_str

                    category_items.append({
                        "title": title,
                        "url": url,
                        "source": item['source'],
                        "formatted_date": formatted_date,
                        "snippet": item['body'],
                        "date_obj": dt if 'dt' in locals() else datetime.min # ソート用
                    })
                    
            except Exception as e:
                print(f"  エラーが発生しました: {keyword} {e}")
                time.sleep(2) # レート制限回避待ち
                continue
        
        # カテゴリ内を日付順などでソートしたり、件数を絞る
        # 今回は重複排除済みのものをそのまま追加（件数はConfig等で制御も可だが、User要望により「固定しなくていい」）
        news_results[category] = category_items

    return news_results
