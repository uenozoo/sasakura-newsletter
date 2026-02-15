import os
import yaml
import argparse
from datetime import datetime, timedelta
from content_fetcher import fetch_news
from email_sender import generate_html_body, save_to_file, send_newsletter

def load_config(config_path="config.yaml"):
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="メール送信せずにHTML保存のみ行う")
    args = parser.parse_args()

    # Config loading
    try:
        config = load_config()
    except Exception as e:
        print(f"Config load error: {e}")
        return

    # Date Range (Past 7 days)
    today = datetime.now()
    start_date = today - timedelta(days=7)
    date_range_str = f"{start_date.strftime('%Y/%m/%d')} ～ {today.strftime('%Y/%m/%d')}"

    print(f"[{datetime.now()}] ニュース収集開始: {date_range_str}")

    # Fetch News
    news_data_raw = fetch_news(config['topics'], excluded_terms=config.get('excluded_terms', []), target_date_start=start_date)
    
    # Process News Data (Rule-based augmentation for automation without LLM)
    news_data_processed = {}
    for category, items in news_data_raw.items():
        processed_items = []
        for item in items:
            # Simple rule-based augmentation
            item['summary'] = item['snippet'][:100] + "..." if item.get('snippet') else "詳細本文を参照してください。"
            item['detail'] = item.get('snippet', '詳細な本文は元記事リンクからご確認ください。')
            item['reasoning'] = f"【自動選定】「{category}」に関連する最新動向として検出されました。"
            item['sales_talk'] = f"最近「{item['title'][:15]}...」という記事が出ていましたが、御社の関連プロジェクトへの影響はいかがでしょうか？"
            item['sales_hint'] = "記事のキーワードを顧客との雑談のネタとして活用してください。"
            processed_items.append(item)
        news_data_processed[category] = processed_items

    # Generic Summary/Proposal (Placeholder)
    summary_data = {
        "text": "<ul><li>今週の主要ニュースを自動収集しました。詳細は各記事をご確認ください。</li></ul>",
        "reasoning": "自動収集プロセスによる生成",
        "evidence": "ニュース一覧"
    }
    proposal_data = {
        "text": "<ul><li>収集されたニュースを基に、関連顧客への情報提供を行ってください。</li></ul>",
        "reasoning": "定型的アクション提案",
        "evidence": "ー"
    }
    
    # Keywords (Static for now)
    keyword_dict = {
        "データセンター": "大量のサーバーを設置・運用する施設。冷却設備の騒音が課題。",
        "環境アセスメント": "開発前の環境影響評価手続き。",
    }

    # Generate HTML
    html_body = generate_html_body(
        news_data_processed,
        date_range_str,
        summary_data=summary_data,
        proposal_data=proposal_data,
        chart_data=None, # QuickChart requires data logic, skipping for auto-run simple mode
        glossary=None,
        keyword_dict=keyword_dict
    )

    # Output / Send
    if args.dry_run:
        os.makedirs("output", exist_ok=True)
        path = "output/auto_run_test.html"
        save_to_file(html_body, path)
        print(f"Dry Run完了: {path}")
    else:
        # Get Secrets from Env
        smtp_server = os.environ.get("SMTP_SERVER")
        smtp_port = os.environ.get("SMTP_PORT", 587)
        smtp_user = os.environ.get("SMTP_USER")
        smtp_password = os.environ.get("SMTP_PASSWORD")
        to_address = os.environ.get("TO_EMAIL", smtp_user) # Default to sender if not specified

        if smtp_server and smtp_user and smtp_password:
            send_newsletter(html_body, f"【週刊】消音・防音業界ニュース ({date_range_str})", [to_address], smtp_server, smtp_port, smtp_user, smtp_password)
        else:
            print("各SMTP環境変数が設定されていません。メール送信をスキップします。")
            # Fallback save
            os.makedirs("output", exist_ok=True)
            save_to_file(html_body, "output/newsletter_no_smtp.html")

if __name__ == "__main__":
    main()
