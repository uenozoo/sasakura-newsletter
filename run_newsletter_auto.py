import os
import yaml
import argparse
import json
import re
from datetime import datetime, timedelta
import google.generativeai as genai
from content_fetcher import fetch_news
from email_sender import generate_html_body, save_to_file, send_newsletter

def load_config(config_path="config.yaml"):
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print("Config file not found.")
        return {}

def configure_gemini():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("警告: GEMINI_API_KEY が設定されていません。AI生成機能はスキップされます。")
        return None
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-1.5-flash')

def analyze_news_with_gemini(model, item, category):
    if not model:
        return {
            "summary": item.get('snippet', '')[:80] + "...",
            "detail": item.get('snippet', '詳細なし'),
            "reasoning": "（AI未接続のため自動選定）",
            "sales_talk": "この記事をきっかけに顧客へアプローチしてみましょう。",
            "sales_hint": "関連する課題がないかヒアリングしてください。"
        }
    
    prompt = f"""
    あなたは騒音対策エンジニアリング会社「ササクラAE」の優秀な営業企画担当です。
    以下のニュース記事を分析し、営業担当者がB2B営業（データセンター、工場、インフラ案件）で使える形に情報を加工してください。

    【記事情報】
    タイトル: {item['title']}
    ソース: {item['source']}
    抜粋: {item.get('snippet', '')}
    カテゴリ: {category}

    【出力フォーマット（JSON形式想定）】
    Summary: 記事の核心（40文字以内）
    Detail: 詳細解説（200文字程度）
    Reasoning: なぜ営業にとって重要か（100文字以内）
    SalesTalk: 具体的な「呼び水トーク」（1つ）
    SalesHint: 誰にどう提案すべきかのアドバイス
    """

    try:
        response = model.generate_content(prompt)
        text = response.text
        
        parsed = {}
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith("Summary:"): parsed['summary'] = line.replace("Summary:", "").strip()
            elif line.startswith("Detail:"): parsed['detail'] = line.replace("Detail:", "").strip()
            elif line.startswith("Reasoning:"): parsed['reasoning'] = line.replace("Reasoning:", "").strip()
            elif line.startswith("SalesTalk:"): parsed['sales_talk'] = line.replace("SalesTalk:", "").strip()
            elif line.startswith("SalesHint:"): parsed['sales_hint'] = line.replace("SalesHint:", "").strip()
        
        if not parsed.get('summary'): parsed['summary'] = item['title']
        return parsed

    except Exception as e:
        print(f"AI Generation Error ({item['title']}): {e}")
        return {
            "summary": "AI生成エラー",
            "detail": "情報の生成に失敗しました。",
            "reasoning": "ー",
            "sales_talk": "ー",
            "sales_hint": "ー"
        }

def generate_overall_insight(model, news_context):
    if not model:
        return {
            "summary": {"text": "AI未接続のため生成なし", "reasoning": "", "evidence": ""},
            "proposal": {"text": "AI未接続のため生成なし", "reasoning": "", "evidence": ""}
        }
    
    prompt = f"""
    以下のニュース内容から、今週の「全体まとめ」と「営業アクションプラン」を策定してください。
    
    【ニュース一覧】
    {news_context}

    【出力形式】
    SummaryText: 今週のトレンド（箇条書きHTML <ul><li>...</li></ul>）
    SummaryReasoning: その理由
    ProposalText: 具体的な行動指針（箇条書きHTML <ul><li>...</li></ul>）
    ProposalReasoning: その意図
    """
    
    try:
        response = model.generate_content(prompt)
        text = response.text
        parsed = {}
        for line in text.split('\n'):
            if line.startswith("SummaryText:"): parsed['summary_text'] = line.replace("SummaryText:", "").strip()
            elif line.startswith("SummaryReasoning:"): parsed['summary_reasoning'] = line.replace("SummaryReasoning:", "").strip()
            elif line.startswith("ProposalText:"): parsed['proposal_text'] = line.replace("ProposalText:", "").strip()
            elif line.startswith("ProposalReasoning:"): parsed['proposal_reasoning'] = line.replace("ProposalReasoning:", "").strip()

        return {
            "summary": {
                "text": parsed.get('summary_text', '要約生成失敗'),
                "reasoning": parsed.get('summary_reasoning', ''),
                "evidence": "今週のニュース全般"
            },
            "proposal": {
                "text": parsed.get('proposal_text', '提案生成失敗'),
                "reasoning": parsed.get('proposal_reasoning', ''),
                "evidence": "ー"
            }
        }
    except Exception as e:
        print(f"Overall Insight Error: {e}")
        return {
            "summary": {"text": "生成エラー", "reasoning": "", "evidence": ""},
            "proposal": {"text": "生成エラー", "reasoning": "", "evidence": ""}
        }

def generate_glossary(model, news_context):
    if not model: return None
    
    prompt = f"""
    以下のニュース内で使用されている「技術用語」や「業界用語」から、営業担当者が知っておくべきものを最大3つ選び、解説してください。
    必ずJSON形式で出力してください。

    【ニュース】
    {news_context}

    【JSON形式】
    {{
        "用語A": "解説A",
        "用語B": "解説B"
    }}
    """
    try:
        response = model.generate_content(prompt)
        text = response.text
        # Extract JSON part if mixed with text
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return None
    except Exception as e:
        print(f"Glossary Error: {e}")
        return None

def generate_chart_data(model, news_context):
    if not model: return None

    prompt = f"""
    以下のニュース内容から、営業担当者が顧客に見せるのに適した「架空のグラフデータ」を1つ作成してください。
    QuickChart.io のJSON形式の設定オブジェクトを出力してください。
    
    テーマ例: データセンター電力消費予測、騒音規制の推移、市場規模など（ニュース内容に関連すること）

    【JSON形式】
    {{
        "title": "グラフタイトル",
        "source": "出典（架空可）",
        "reasoning": "なぜこのグラフが必要か",
        "config": {{
            "type": "bar",
            "data": {{ ...Labels and Datasets... }},
            "options": {{ ... }}
        }}
    }}
    """
    try:
        response = model.generate_content(prompt)
        text = response.text
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            # Ensure config is dict not string
            if isinstance(data.get('config'), str):
                data['config'] = json.loads(data['config'])
            return data
        return None
    except Exception as e:
        print(f"Chart Error: {e}")
        return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="メール送信せずにHTML保存のみ行う")
    args = parser.parse_args()

    config = load_config()
    model = configure_gemini()

    # Date Range
    today = datetime.now()
    start_date = today - timedelta(days=7)
    date_range_str = f"{start_date.strftime('%Y/%m/%d')} ～ {today.strftime('%Y/%m/%d')}"
    print(f"[{datetime.now()}] ニュース収集開始: {date_range_str}")

    # Fetch
    news_data_raw = fetch_news(config.get('topics', {}), excluded_terms=config.get('excluded_terms', []), target_date_start=start_date)
    
    # Process with AI
    news_data_processed = {}
    all_text_context = ""
    
    print("AI分析を開始します...")
    for category, items in news_data_raw.items():
        processed_items = []
        for item in items[:5]: 
            print(f"  分析中: {item['title'][:20]}...")
            analysis = analyze_news_with_gemini(model, item, category)
            
            item.update(analysis)
            processed_items.append(item)
            all_text_context += f"{item['title']} {item['summary']}\n"
            
        news_data_processed[category] = processed_items

    # Generate Overall Assets
    print("全体コンテンツ（要約・提案・用語・グラフ）を生成中...")
    insights = generate_overall_insight(model, all_text_context[:5000])
    glossary = generate_glossary(model, all_text_context[:3000])
    chart_data = generate_chart_data(model, all_text_context[:3000])
    
    # Keyword Dict for auto-linking (Use glossary keys if available, else fallback)
    keyword_dict = {}
    if glossary:
        keyword_dict = {k: v for k, v in glossary.items()}

    # Generate HTML
    html_body = generate_html_body(
        news_data_processed,
        date_range_str,
        summary_data=insights['summary'],
        proposal_data=insights['proposal'],
        chart_data=chart_data,
        glossary=glossary,
        keyword_dict=keyword_dict
    )

    # Output / Send
    if args.dry_run:
        os.makedirs("output", exist_ok=True)
        path = "output/auto_run_ai_full_test.html"
        save_to_file(html_body, path)
        print(f"Dry Run (Full AI) 完了: {path}")
    else:
        smtp_server = os.environ.get("SMTP_SERVER")
        smtp_port = os.environ.get("SMTP_PORT", 587)
        smtp_user = os.environ.get("SMTP_USER")
        smtp_password = os.environ.get("SMTP_PASSWORD")
        to_address = os.environ.get("TO_EMAIL", smtp_user)

        if smtp_server and smtp_user and smtp_password:
            send_newsletter(html_body, f"【週刊】消音・防音業界ニュース ({date_range_str})", [to_address], smtp_server, smtp_port, smtp_user, smtp_password)
        else:
            print("SMTP設定不足のため保存のみ行います。")
            os.makedirs("output", exist_ok=True)
            save_to_file(html_body, "output/newsletter_no_smtp.html")

if __name__ == "__main__":
    main()
