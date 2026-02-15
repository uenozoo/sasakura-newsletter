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
    
    # Dynamically select the best model
    try:
        print("利用可能なモデルを検索中...")
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                model_name = m.name.replace('models/', '')
                available_models.append(model_name)
        
        print(f"利用可能モデル一覧: {available_models}")

        priority_list = [
            'gemini-2.0-pro-exp', 'gemini-2.0-flash-exp', 
            'gemini-1.5-pro-latest', 'gemini-1.5-pro',
            'gemini-1.5-flash-latest', 'gemini-1.5-flash',
            'gemini-pro'
        ]
        
        for candidate in priority_list:
            if candidate in available_models:
                print(f"推奨モデルを選択しました: {candidate}")
                return genai.GenerativeModel(candidate)
        
        for model in available_models:
            if 'gemini' in model:
                print(f"代替モデルを選択しました: {model}")
                return genai.GenerativeModel(model)

        if available_models:
            print(f"モデルを選択しました: {available_models[0]}")
            return genai.GenerativeModel(available_models[0])
            
    except Exception as e:
        print(f"モデル一覧取得エラー: {e}")
        print("デフォルトモデル(gemini-pro)を試行します。")
        return genai.GenerativeModel('gemini-pro')
    
    return None

def extract_json(text):
    """Encapsulated JSON extraction logic"""
    try:
        # Try finding the first JSON object
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return None
    except json.JSONDecodeError:
        return None

def analyze_news_with_gemini(model, item, category):
    if not model:
        # Fallback if no model configured
        return {
            "summary": item.get('snippet', '')[:80] + "...",
            "detail": item.get('snippet', '詳細なし'),
            "reasoning": "（AI未接続）",
            "sales_talk": f"{item['title']}について顧客と話をしてみましょう。",
            "sales_hint": "業界動向としての紹介が有効です。"
        }
    
    prompt = f"""
    あなたは騒音対策エンジニアリング会社「ササクラAE」の優秀な営業企画担当です。
    以下のニュース記事を分析し、営業担当者がB2B営業（データセンター、工場、インフラ案件）で使える形に情報を加工してください。

    【記事情報】
    タイトル: {item['title']}
    ソース: {item['source']}
    抜粋: {item.get('snippet', '')}
    カテゴリ: {category}

    【重要】
    必ず「有効なJSON形式」で出力してください。Markdownコードブロック（```json）は不要です。

    {{
        "summary": "記事の核心（40文字以内）",
        "detail": "詳細解説（200文字程度）",
        "reasoning": "なぜ営業にとって重要か（100文字以内）",
        "sales_talk": "具体的な「呼び水トーク」（1つ）",
        "sales_hint": "誰にどう提案すべきかのアドバイス"
    }}
    """

    try:
        response = model.generate_content(prompt)
        text = response.text
        # DEBUG LOG
        print(f"[DEBUG] News Analysis Raw ({item['title'][:10]}...): {text[:100]}...")

        parsed = extract_json(text)
        
        if not parsed:
            # Fallback Parsing if JSON fails
            print(f"[WARN] JSON parsing failed, attempting Regex fallback for {item['title']}")
            parsed = {}
            patterns = {
                'summary': r'(?:summary|要約)[:："\s]+(.*?)(?=",|\n)',
                'detail': r'(?:detail|詳細)[:："\s]+(.*?)(?=",|\n)',
                'reasoning': r'(?:reasoning|選定理由)[:："\s]+(.*?)(?=",|\n)',
                'sales_talk': r'(?:sales_talk|商談トーク)[:："\s]+(.*?)(?=",|\n)',
                'sales_hint': r'(?:sales_hint|営業ヒント)[:："\s]+(.*?)(?=",|\n|"\}\s*$)'
            }
            for key, pattern in patterns.items():
                match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
                if match:
                    parsed[key] = match.group(1).strip().strip('"').strip(',')
        
        # Ensure minimum fields exist
        fallback_data = {
            "summary": item['title'],
            "detail": item.get('snippet', '詳細生成失敗'),
            "reasoning": "詳細情報を確認してください。",
            "sales_talk": "話題のきっかけとして活用可能です。",
            "sales_hint": "顧客へ情報提供を行ってください。"
        }
        
        return {**fallback_data, **parsed}

    except Exception as e:
        print(f"[ERROR] AI Generation Error ({item['title']}): {e}")
        return {
            "summary": item['title'],
            "detail": f"AI生成エラー: {str(e)}",
            "reasoning": "エラー",
            "sales_talk": "ー",
            "sales_hint": "ー"
        }

def generate_overall_insight(model, news_context):
    if not model:
        return {
            "summary": {"text": "AI未接続", "reasoning": "", "evidence": ""},
            "proposal": {"text": "AI未接続", "reasoning": "", "evidence": ""}
        }
    
    prompt = f"""
    以下のニュース内容から、今週の「全体まとめ」と「営業アクションプラン」を策定してください。
    
    【ニュース一覧】
    {news_context}

    【重要】
    必ず「有効なJSON形式」で出力してください。

    {{
        "summary_text": "今週のトレンド（箇条書きHTML <ul><li>...</li></ul>）",
        "summary_reasoning": "その理由",
        "proposal_text": "具体的な行動指針（箇条書きHTML <ul><li>...</li></ul>）",
        "proposal_reasoning": "その意図"
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        text = response.text
        parsed = extract_json(text)

        if not parsed:
            print("[WARN] Overall Insight JSON parsing failed.")
            parsed = {}

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
        print(f"[ERROR] Overall Insight Error: {e}")
        return {
            "summary": {"text": "生成エラー", "reasoning": "", "evidence": ""},
            "proposal": {"text": "生成エラー", "reasoning": "", "evidence": ""}
        }

def generate_glossary(model, news_context):
    if not model: return None
    
    prompt = f"""
    以下のニュース内で使用されている「技術用語」や「業界用語」から、営業担当者が知っておくべきものを最大3つ選び、解説してください。
    
    【重要】
    必ず「有効なJSON形式」で出力してください。
    キーは用語、値は解説です。

    {{
        "用語A": "解説A",
        "用語B": "解説B"
    }}

    【ニュース】
    {news_context}
    """
    try:
        response = model.generate_content(prompt)
        text = response.text
        return extract_json(text)
    except Exception as e:
        print(f"Glossary Error: {e}")
        return None

def generate_chart_data(model, news_context):
    if not model: return None

    # Static fallback data
    fallback_chart = {
        "title": "データセンター市場動向(サンプル)",
        "source": "AI生成エラーのためサンプル表示",
        "reasoning": "エラー発生時のプレースホルダー",
        "config": {
            "type": "bar",
            "data": {
                "labels": ["2024", "2025", "2026"],
                "datasets": [{"label": "市場規模予測", "data": [100, 120, 150]}]
            },
            "options": {"title": {"display": True, "text": "サンプルチャート"}}
        }
    }

    prompt = f"""
    以下のニュース内容から、営業担当者が顧客に見せるのに適した「架空のグラフデータ」を1つ作成してください。
    QuickChart.io (Chart.js v2.9.4互換) のJSON形式の設定オブジェクトを出力してください。
    必ず 'type', 'data', 'options' を含めてください。

    【JSON形式】
    {{
        "title": "グラフタイトル",
        "source": "出典（架空可）",
        "reasoning": "なぜこのグラフが必要か",
        "config": {{
            "type": "bar",
            "data": {{ 
                "labels": ["Label1", "Label2"], 
                "datasets": [{{ "label": "Dataset1", "data": [10, 20] }}] 
            }},
            "options": {{
                "title": {{ "display": true, "text": "Chart Title" }}
            }}
        }}
    }}
    """
    try:
        response = model.generate_content(prompt)
        text = response.text
        data = extract_json(text)
        
        if data:
            # Normalization
            if isinstance(data.get('config'), str):
                try:
                    data['config'] = json.loads(data['config'])
                except:
                    pass
            
            # Validation
            if 'config' in data and isinstance(data['config'], dict):
                if 'options' not in data['config']:
                    data['config']['options'] = {}
                return data

        print("[WARN] Chart JSON invalid or missing.")
        return fallback_chart
    except Exception as e:
        print(f"Chart Error: {e}")
        return fallback_chart

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
