import os
import yaml
import argparse
import json
import re
from datetime import datetime, timedelta
# New SDK Import
from google import genai
from google.genai import types

from content_fetcher import fetch_news
from email_sender import generate_html_body, save_to_file, send_newsletter

def load_config(config_path="config.yaml"):
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print("Config file not found.")
        return {}

def configure_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("警告: GEMINI_API_KEY が設定されていません。AI生成機能はスキップされます。")
        return None
    return genai.Client(api_key=api_key)

def extract_json(text):
    """Encapsulated JSON extraction logic"""
    try:
        # Clean markdown code blocks
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```', '', text)
        
        # Try finding the first JSON object or array
        match = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return json.loads(text) # Try raw text
    except json.JSONDecodeError:
        return None

def batch_analyze_news(client, items, category, model_name="gemini-2.5-flash"):
    if not client or not items:
        return []

    # Prepare batch context
    items_text = ""
    for idx, item in enumerate(items):
        items_text += f"""
        [ID: {idx}]
        Title: {item['title']}
        Snippet: {item.get('snippet', '')}
        Source: {item['source']}
        ---
        """

    prompt = f"""
    あなたは騒音対策エンジニアリング会社「ササクラAE」の優秀な営業企画担当です。
    以下のニュース記事リスト（カテゴリ: {category}）を一括分析し、B2B営業（DC、工場、インフラ）で使える形に加工してください。

    【ニュースリスト】
    {items_text}

    【タスク】
    各記事（IDごと）に対して、以下のJSONオブジェクトを作成し、それを「リスト形式（配列）」で出力してください。

    {{
        "id": (整数のID),
        "summary": "記事の核心（40文字以内）",
        "detail": "詳細解説（200文字程度）",
        "reasoning": "なぜ営業にとって重要か（100文字以内）",
        "sales_talk": "具体的な呼び水トーク（1つ）",
        "sales_hint": "誰にどう提案すべきか"
    }}

    出力は厳密なJSON配列（[ {{...}}, {{...}} ]）のみを行ってください。
    """

    try:
        # New SDK usage
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json" # Force JSON
            )
        )
        data = extract_json(response.text)
        
        if isinstance(data, list):
            return data
        else:
            print(f"[WARN] Batch Analysis returned non-list: {type(data)}")
            return []

    except Exception as e:
        print(f"[ERROR] Batch Analysis Error ({category}): {e}")
        return []

def generate_overall_insight(client, news_context, model_name="gemini-2.5-flash"):
    if not client:
        return {"summary": {"text": "AI未接続", "reasoning": "", "evidence": ""}, "proposal": {"text": "AI未接続", "reasoning": "", "evidence": ""}}
    
    prompt = f"""
    以下のニュース要約リストから、今週の「全体まとめ」と「営業アクションプラン」を策定してください。
    
    {news_context}

    【出力形式: JSON】
    {{
        "summary_text": "今週のトレンド（箇条書きHTML <ul><li>...</li></ul>）",
        "summary_reasoning": "その理由",
        "proposal_text": "具体的な行動指針（箇条書きHTML <ul><li>...</li></ul>）",
        "proposal_reasoning": "その意図"
    }}
    """
    
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return extract_json(response.text) or {}
    except Exception as e:
        print(f"[ERROR] Overall Insight Error: {e}")
        return {}

def generate_glossary(client, news_context, model_name="gemini-2.5-flash"):
    if not client: return None
    
    prompt = f"""
    ニュース内で使用されている専門用語から、営業担当者が知っておくべきものを3つ解説してください。
    
    {news_context}

    【出力形式: JSON】
    {{ "用語A": "解説A", "用語B": "解説B", ... }}
    """
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return extract_json(response.text)
    except Exception as e:
        print(f"Glossary Error: {e}")
        return None

def generate_chart_data(client, news_context, model_name="gemini-2.5-flash"):
    if not client: return None

    prompt = f"""
    ニュース内容に関連する「営業用グラフデータ（架空）」を1つ作成してください。
    QuickChart.io (Chart.js v2) 形式のJSONを出力してください。

    {news_context}

    【出力形式: JSON】
    {{
        "title": "グラフタイトル",
        "source": "出典",
        "reasoning": "理由",
        "config": {{ "type": "bar", "data": {{...}}, "options": {{...}} }}
    }}
    """
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        data = extract_json(response.text)
        # Normalize config string to dict if needed
        if data and isinstance(data.get('config'), str):
             data['config'] = json.loads(data['config'])
        return data
    except Exception as e:
        print(f"Chart Error: {e}")
        return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="メール送信せずにHTML保存のみ行う")
    args = parser.parse_args()

    config = load_config()
    client = configure_client()
    
    # Model Selection (Default to requested 2.5, fallback logic can be added if needed)
    MODEL_NAME = "gemini-2.5-flash"

    # Date Range
    today = datetime.now()
    start_date = today - timedelta(days=7)
    date_range_str = f"{start_date.strftime('%Y/%m/%d')} ～ {today.strftime('%Y/%m/%d')}"
    print(f"[{datetime.now()}] ニュース収集開始: {date_range_str}")

    # Fetch
    news_data_raw = fetch_news(config.get('topics', {}), excluded_terms=config.get('excluded_terms', []), target_date_start=start_date)
    
    news_data_processed = {}
    all_text_context = ""
    
    print("AI一括分析を開始します (Batch Processing)...")
    
    for category, items in news_data_raw.items():
        if not items: continue
        
        # Limit to 5 items and Process in Batch
        target_items = items[:5]
        print(f"  カテゴリ: {category} ({len(target_items)}件) を分析中...")
        
        if client:
            batch_results = batch_analyze_news(client, target_items, category, MODEL_NAME)
            
            # Merge results back to items
            processed_items = []
            for i, item in enumerate(target_items):
                # Find matching result by ID (or index fallback)
                res = next((r for r in batch_results if r.get('id') == i), None)
                if not res and i < len(batch_results): res = batch_results[i] # Fallback by index
                
                if res:
                    item.update(res)
                else:
                    item.update({ # Fallback if analysis missing
                        "summary": item['title'], "detail": item.get('snippet',''), "reasoning": "分析失敗", "sales_talk": "-", "sales_hint": "-"
                    })
                
                processed_items.append(item)
                all_text_context += f"Title: {item['title']}\nSummary: {item.get('summary', '')}\nDetail: {item.get('detail', '')}\n---\n"
            
            news_data_processed[category] = processed_items
        else:
            # AI Skipped
            news_data_processed[category] = target_items

    # Generate Overall Assets (Single Calls)
    print("全体コンテンツ（要約・提案・用語・グラフ）を生成中...")
    
    # Context trimming to avoid token limits (though Flash has large window)
    context_snippet = all_text_context[:10000]
    
    insights = generate_overall_insight(client, context_snippet, MODEL_NAME) or {}
    glossary = generate_glossary(client, context_snippet, MODEL_NAME)
    chart_data = generate_chart_data(client, context_snippet, MODEL_NAME)
    
    # Formatting Insights
    summary_data = {
        "text": insights.get('summary_text', '生成失敗'),
        "reasoning": insights.get('summary_reasoning', ''),
        "evidence": "Week News"
    }
    proposal_data = {
        "text": insights.get('proposal_text', '生成失敗'),
        "reasoning": insights.get('proposal_reasoning', ''),
        "evidence": "-"
    }

    keyword_dict = glossary if glossary else {}

    # Generate HTML
    html_body = generate_html_body(
        news_data_processed,
        date_range_str,
        summary_data=summary_data,
        proposal_data=proposal_data,
        chart_data=chart_data,
        glossary=glossary,
        keyword_dict=keyword_dict
    )

    # Output / Send
    if args.dry_run:
        os.makedirs("output", exist_ok=True)
        path = "output/auto_run_ai_batch_v2.html"
        save_to_file(html_body, path)
        print(f"Dry Run (Batch AI) 完了: {path}")
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
