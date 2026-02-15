from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from datetime import datetime
import urllib.parse
import json
import re

def generate_quickchart_url(chart_config):
    base_url = "https://quickchart.io/chart"
    params = {
        'c': json.dumps(chart_config),
        'w': 500,
        'h': 300,
        'bkg': 'white'
    }
    return f"{base_url}?{urllib.parse.urlencode(params)}"

def auto_link_keywords(text, keyword_dict):
    if not text or not keyword_dict:
        return text
        
    for keyword, explanation in keyword_dict.items():
        if keyword in text and "<details" not in text: 
            search_query = urllib.parse.quote(keyword)
            search_url = f"https://www.google.com/search?q={search_query}"
            replacement = (
                f'<details class="inline-term" style="display:inline;">'
                f'<summary style="list-style:none; cursor:help; border-bottom:2px dotted #888; display:inline;">{keyword}</summary>'
                f'<div class="term-content" style="background:#e3f2fd; color:#0d47a1; padding:12px; border-radius:6px; margin:8px 0 15px 0; font-size:14px; border-left:4px solid #1976d2;">'
                f'<div style="margin-bottom:8px;"><b>💡 AI用語解説:</b> {explanation}</div>'
                f'<a href="{search_url}" target="_blank" style="display:inline-block; font-size:12px; color:#fff; background-color:#1976d2; padding:4px 10px; border-radius:15px; text-decoration:none;">🔍 裏付け検索 (Google)</a>'
                f'</div>'
                f'</details>'
            )
            text = text.replace(keyword, replacement)
    return text

def render_trust_area(reasoning=None, evidence_query=None):
    if not reasoning and not evidence_query:
        return ""
    html = '<div class="trust-area">'
    if reasoning:
        html += f"""
        <div class="reasoning-box">
            <span class="reasoning-label">💡 AI選定理由 (なぜこの情報？)</span>
            {reasoning}
        </div>
        """
    if evidence_query:
        search_url = f"https://www.google.com/search?q={urllib.parse.quote(evidence_query)}"
        html += f"""
        <div class="action-buttons">
            <a href="{search_url}" target="_blank" class="link-btn link-btn-evidence">🔍 裏付け検索 (Google)</a>
        </div>
        """
    html += '</div>'
    return html

def generate_html_body(news_data, date_range_str, 
                       summary_data=None, proposal_data=None, chart_data=None, 
                       glossary=None, keyword_dict=None):
    
    chart_img_url = ""
    if chart_data and chart_data.get('config'):
        chart_img_url = generate_quickchart_url(chart_data['config'])
    
    def process_text(text):
        if keyword_dict:
            return auto_link_keywords(text, keyword_dict)
        return text

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Sasakura AE Newsletter</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.8; color: #222; background-color: #f2f2f7; margin: 0; padding: 0; font-size: 18px; }}
            .wrapper {{ width: 100%; background-color: #f2f2f7; padding: 40px 0; }}
            .container {{ max-width: 720px; margin: 0 auto; background-color: #ffffff; border-radius: 20px; box-shadow: 0 12px 36px rgba(0, 0, 0, 0.08); overflow: hidden; }}
            
            .header {{ background: linear-gradient(135deg, #003366 0%, #004488 100%); padding: 50px 40px; text-align: center; color: white; }}
            .brand {{ font-size: 15px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; opacity: 0.95; margin-bottom: 12px; }}
            .title {{ font-size: 36px; font-weight: 800; margin: 0 0 20px 0; letter-spacing: -0.5px; line-height: 1.2; }}
            .period {{ font-size: 18px; background-color: rgba(255,255,255,0.2); display: inline-block; padding: 8px 20px; border-radius: 30px; font-weight: 600; }}

            .content {{ padding: 50px; }}
            .section-header {{ display: flex; align-items: center; margin-bottom: 30px; margin-top: 60px; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
            .section-header:first-child {{ margin-top: 0; }}
            .section-icon {{ font-size: 28px; margin-right: 15px; }}
            .section-title {{ font-size: 24px; font-weight: 800; color: #111; letter-spacing: -0.02em; }}
            
            .card {{ background-color: #fff; border: 1px solid #ddd; border-radius: 16px; padding: 30px; margin-bottom: 30px; }}
            .summary-card {{ background-color: #f0f7ff; border: 2px solid #cce4ff; border-left: 6px solid #0056b3; }}
            .proposal-card {{ background-color: #fffaf0; border: 2px solid #ffeeba; border-left: 6px solid #ff9500; }}
            .text-content {{ font-size: 18px; color: #333; }}
            .text-content ul {{ padding-left: 26px; margin: 0; }}
            .text-content li {{ margin-bottom: 15px; }}
            .trust-area {{ background-color: #f9f9f9; border-top: 1px solid #eee; padding-top: 15px; margin-top: 15px; }}
            .reasoning-box {{ font-size: 14px; color: #555; background-color: #fffde7; padding: 10px 15px; border-radius: 6px; margin-bottom: 15px; border: 1px solid #fff9c4; }}
            .reasoning-label {{ font-weight: 700; color: #f57f17; margin-bottom: 4px; display: block; font-size: 12px; text-transform: uppercase; }}
            .action-buttons {{ text-align: right; font-size: 14px; }}
            .link-btn {{ display: inline-block; padding: 8px 16px; border-radius: 20px; text-decoration: none; font-weight: 600; font-size: 13px; margin-left: 8px; transition: background-color 0.2s; }}
            .link-btn-evidence {{ background-color: #34c759; color: white; border: 1px solid #34c759; }}
            .link-btn-source {{ background-color: #fff; color: #0056b3; border: 1px solid #0056b3; }}
            .link-btn:hover {{ opacity: 0.9; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}

            .news-card {{ margin-bottom: 30px; padding: 0; background-color: #fdfdfd; border: 1px solid #e0e0e0; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.03); overflow:hidden; }}
            .news-summary-header {{ padding: 20px 25px; cursor: pointer; background-color: #fff; transition: background 0.2s; }}
            .news-summary-header:hover {{ background-color: #f9f9f9; }}
            .news-title {{ color: #003366; font-size: 22px; font-weight: 800; line-height: 1.4; }}
            .news-meta {{ font-size: 14px; color: #666; margin-top: 5px; }}
            
            .read-more-indicator {{
                display: block;
                margin-top: 15px;
                font-size: 14px;
                color: #0056b3;
                font-weight: 700;
                text-align: right;
            }}

            .news-content-wrapper {{
                padding: 0 25px 25px 25px;
                background-color: #fcfcfc;
                border-top: 1px dashed #eee;
            }}

            .point-badge {{ background-color: #0056b3; color: white; font-size: 12px; font-weight: 800; padding: 4px 10px; border-radius: 4px; margin-right: 8px; vertical-align: middle; }}
            .point-text {{ font-size: 18px; font-weight: 700; color: #333; vertical-align: middle; }}
            .news-point-area {{ margin-top: 15px; }}

            .news-body-area {{ background-color: #f5f5f7; padding: 20px; border-radius: 8px; font-size: 16px; color: #444; line-height: 1.8; border-left: 4px solid #ccc; margin-bottom: 20px; margin-top: 20px; }}

            /* Sales Action Area */
            .sales-action-area {{
                margin-top: 20px;
                margin-bottom: 20px;
                padding: 15px;
                background-color: #fff0f5; /* Light pinkish */
                border: 2px dashed #ffb6c1;
                border-radius: 8px;
            }}
            .sales-label {{
                font-size: 14px;
                font-weight: 800;
                color: #d63384;
                margin-bottom: 10px;
                display: block;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            .sales-talk-box {{
                display: flex;
                align-items: flex-start;
                margin-bottom: 10px;
            }}
            .talk-icon {{ font-size: 24px; margin-right: 10px; }}
            .talk-content {{ 
                background: #fff; 
                padding: 10px 15px; 
                border-radius: 0 15px 15px 15px; 
                border: 1px solid #ffccd5;
                font-weight: 600;
                color: #444;
                font-size: 16px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            }}
            .sales-hint-box {{
                font-size: 15px;
                color: #555;
                padding-left: 35px;
            }}
            .hint-icon {{ margin-right: 5px; }}

            .chart-header {{ font-size: 18px; font-weight: 700; color: #444; margin-bottom: 15px; text-align: center; }}
            .chart-container {{ text-align: center; margin: 30px 0; }}
            .chart-img {{ max-width: 100%; height: auto; border-radius: 12px; border: 1px solid #ccc; }}
            .source-note {{ font-size: 13px; color: #666; text-align: right; margin-top: 10px; display: block; }}

            .glossary-dl {{ margin: 0; }}
            .glossary-dt {{ font-weight: 800; font-size: 18px; margin-top: 25px; color: #222; border-bottom: 1px dashed #ccc; padding-bottom: 4px; display: inline-block; }}
            .glossary-dd {{ font-size: 16px; color: #555; margin-left: 0; margin-top: 8px; line-height: 1.8; }}
            .glossary-dd a.search-btn {{ display:inline-block; margin-top:8px; font-size:12px; color:#fff; background-color:#666; padding:4px 10px; border-radius:15px; text-decoration:none; }}
            
            .footer {{ background-color: #222; color: #ccc; text-align: center; padding: 50px 20px; font-size: 14px; line-height: 1.8; }}
            
            details > summary {{ list-style: none; }}
            details > summary::-webkit-details-marker {{ display: none; }}

            /* Mobile Responsive Styles */
            @media only screen and (max-width: 600px) {{
                .wrapper {{ padding: 0 !important; }}
                .container {{ border-radius: 0 !important; width: 100% !important; max-width: 100% !important; box-shadow: none !important; }}
                .header {{ padding: 30px 20px !important; }}
                .title {{ font-size: 28px !important; }}
                .content {{ padding: 20px !important; }}
                .section-header {{ margin-top: 40px !important; }}
                .card, .news-card {{ padding: 0 !important; margin-bottom: 20px !important; }}
                .news-summary-header {{ padding: 20px !important; }}
                .news-content-wrapper {{ padding: 0 20px 20px 20px !important; }}
                .news-title {{ font-size: 20px !important; }}
                .point-text {{ font-size: 16px !important; }}
                .text-content {{ font-size: 16px !important; }}
                .news-body-area, .sales-action-area {{ padding: 15px !important; }}
                .action-buttons {{ text-align: left !important; margin-top: 15px !important; }}
                .link-btn {{ margin-left: 0 !important; margin-right: 8px !important; margin-bottom: 8px !important; }}
            }}
        </style>
    </head>
    <body>
        <div class="wrapper">
            <div class="container">
                <div class="header">
                    <div class="brand">Sasakura AE Newsletter</div>
                    <h1 class="title">消音・防音業界ニュース</h1>
                    <div class="period">{date_range_str}</div>
                </div>
                
                <div class="content">
                    
                    <!-- 1. Executive Summary -->
                    <div class="section-header">
                        <span class="section-icon">📝</span>
                        <div class="section-title">今週のまとめ</div>
                    </div>
                    <div class="card summary-card text-content" style="padding: 25px;">
                        {process_text(summary_data['text'] if summary_data else "")}
                        {render_trust_area(summary_data.get('reasoning') if summary_data else None, summary_data.get('evidence') if summary_data else None)}
                    </div>
                    
                    <!-- 2. Visual Data -->
                    {f'''
                    <div class="section-header">
                        <span class="section-icon">📊</span>
                        <div class="section-title">Visual Data</div>
                    </div>
                    <div class="card" style="padding: 25px;">
                        <div class="chart-header">{chart_data['title']}</div>
                        <div class="chart-container">
                            <img src="{chart_img_url}" alt="Visual Data" class="chart-img">
                            <span class="source-note">Source: {chart_data['source']}</span>
                        </div>
                        {render_trust_area(chart_data.get('reasoning'), chart_data.get('evidence'))}
                    </div>
                    ''' if chart_img_url else ''}
                    
                    <!-- 3. Action Plan -->
                     <div class="section-header">
                        <span class="section-icon">🚀</span>
                        <div class="section-title">営業アクション提案</div>
                    </div>
                    <div class="card proposal-card text-content" style="padding: 25px;">
                        {process_text(proposal_data['text'] if proposal_data else "")}
                        {render_trust_area(proposal_data.get('reasoning') if proposal_data else None, proposal_data.get('evidence') if proposal_data else None)}
                    </div>
                    
                    <hr style="border: 0; border-top: 1px solid #ddd; margin: 50px 0;">

                    <!-- 4. News Items -->
                    <div class="section-header">
                        <span class="section-icon">🗞</span>
                        <div class="section-title">ピックアップ記事など</div>
                    </div>
    """
    
    for category, items in news_data.items():
        if not items:
            continue
            
        html += f'<h3 style="font-size: 18px; font-weight:800; color: #666; margin-top: 50px; border-bottom:2px solid #ddd; padding-bottom:10px; margin-bottom: 30px;">{category}</h3>'
        
        for item in items:
            
            buttons_html = ""
            search_query = urllib.parse.quote(item['title'])
            evidence_url = f"https://www.google.com/search?q={search_query}"
            buttons_html += f'<a href="{evidence_url}" target="_blank" class="link-btn link-btn-evidence">🔍 裏付け検索</a>'
            
            if item.get('url'):
                buttons_html += f'<a href="{item["url"]}" target="_blank" class="link-btn link-btn-source">元記事 ⧉</a>'
            
            sales_html = ""
            if item.get('sales_talk') or item.get('sales_hint'):
                sales_html += '<div class="sales-action-area">'
                sales_html += '<span class="sales-label">🎯 営業アクションのヒント</span>'
                if item.get('sales_talk'):
                    sales_html += f"""
                    <div class="sales-talk-box">
                        <span class="talk-icon">💬</span>
                        <div class="talk-content">{process_text(item['sales_talk'])}</div>
                    </div>
                    """
                if item.get('sales_hint'):
                    sales_html += f"""
                    <div class="sales-hint-box">
                        <span class="hint-icon">📌</span> {process_text(item['sales_hint'])}
                    </div>
                    """
                sales_html += '</div>'

            trust_html = render_trust_area(item.get('reasoning'), None) 
            trust_html += f'<div class="action-buttons" style="margin-top:10px;">{buttons_html}</div>'
            
            # Details Tag Structure for Collapsible Content
            # POINT is now inside SUMMARY to be always visible
            html += f"""
            <div class="news-card">
                <details>
                    <summary class="news-summary-header">
                        <div class="news-title">{process_text(item['title'])}</div>
                        <div class="news-meta">{item['formatted_date']} | {item['source']}</div>
                        
                        <div class="news-point-area">
                            <span class="point-badge">💡 要点</span>
                            <span class="point-text">{process_text(item.get('summary', ''))}</span>
                        </div>

                        <span class="read-more-indicator">▼ 続きを読む（解説・トーク）</span>
                    </summary>
                    
                    <div class="news-content-wrapper">
                        <div class="news-body-area">
                            {process_text(item.get('detail', item.get('snippet', '詳細情報なし')))}
                        </div>
                        
                        {sales_html}
                        
                        <div class="trust-area">
                            {trust_html}
                        </div>
                    </div>
                </details>
            </div>
            """
    
    if glossary:
        html += """
        <hr style="border: 0; border-top: 1px solid #ddd; margin: 50px 0;">
        <div class="section-header">
            <span class="section-icon">📚</span>
            <div class="section-title">用語解説</div>
        </div>
        <div class="card" style="padding: 25px;">
            <dl class="glossary-dl">
        """
        for term, data in glossary.items():
            desc = data if isinstance(data, str) else data['desc']
            search_url = f"https://www.google.com/search?q={urllib.parse.quote(term)}"
            html += f"""
                <dt class="glossary-dt">{term}</dt>
                <dd class="glossary-dd">
                    {process_text(desc)}
                    <br>
                    <a href="{search_url}" target="_blank" class="search-btn">🔍 裏付け検索 (Google)</a>
                </dd>
            """
        html += """
            </dl>
        </div>
        """

    html += """
                </div>
            </div>
            <div class="footer">Sasakura AE Sales Support</div>
        </div>
    </body>
    </html>
    """
    return html

def save_to_file(html_content, filename="newsletter.html"):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_content)

def send_newsletter(html_body, subject, to_emails, smtp_server, smtp_port, smtp_user, smtp_password):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = smtp_user
    msg['To'] = ", ".join(to_emails)

    part = MIMEText(html_body, 'html')
    msg.attach(part)

    try:
        server = smtplib.SMTP(smtp_server, int(smtp_port))
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, to_emails, msg.as_string())
        server.quit()
        print(f"メール送信成功: {', '.join(to_emails)}")
    except Exception as e:
        print(f"メール送信エラー: {e}")
