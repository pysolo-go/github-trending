import os
import requests
from bs4 import BeautifulSoup
import resend
from datetime import datetime
import json
from openai import OpenAI

# Configure Resend
resend.api_key = os.environ.get("RESEND_API_KEY")

# Configure OpenAI
openai_api_key = os.environ.get("OPENAI_API_KEY")
openai_base_url = os.environ.get("OPENAI_BASE_URL")
client = OpenAI(api_key=openai_api_key, base_url=openai_base_url) if openai_api_key else None

def fetch_trending():
    url = "https://github.com/trending"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Failed to load page {url}: {response.status_code}")
    
    soup = BeautifulSoup(response.text, 'html.parser')
    repos = []
    
    # Select the articles that contain the trending repos
    for article in soup.select('article.Box-row'):
        # Get Repo Name (and link)
        h2 = article.select_one('h2.h3 a')
        if not h2:
            continue
        
        # Text usually contains "owner / repo" with lots of whitespace
        repo_name = h2.text.strip().replace('\n', '').replace(' ', '')
        repo_url = f"https://github.com{h2['href']}"
        
        # Get Description
        p = article.select_one('p.col-9')
        description = p.text.strip() if p else "No description provided."
        
        # Get Language
        lang_span = article.select_one('span[itemprop="programmingLanguage"]')
        language = lang_span.text.strip() if lang_span else "Unknown"
        
        # Get Stars
        stars_link = article.select_one('a[href*="stargazers"]')
        stars = stars_link.text.strip() if stars_link else "0"
        
        # Get Stars Today (or this week/month depending on default view, usually today)
        stars_today_span = article.select_one('span.d-inline-block.float-sm-right')
        stars_today = stars_today_span.text.strip() if stars_today_span else ""
        
        repos.append({
            "name": repo_name,
            "url": repo_url,
            "description": description,
            "language": language,
            "stars": stars,
            "stars_today": stars_today
        })
        
    return repos

def analyze_with_ai(repos):
    if not client:
        print("OpenAI client not initialized. Skipping AI analysis.")
        return None

    # Limit to top 10 to avoid token limits if necessary, though list is usually short
    repos_to_analyze = repos[:15]
    
    prompt = f"""
    You are a technical editor for a "GitHub Trending Daily" newsletter.
    Analyze the following list of trending GitHub repositories and provide a comprehensive summary in JSON format.
    
    Repositories:
    {json.dumps(repos_to_analyze, indent=2)}
    
    Requirements:
    1. "summary": A high-quality, insightful paragraph (in Chinese) analyzing today's trends. 
       - Identify themes (e.g., "AI Agents explosion", "Rust tooling maturity").
       - Highlight the most significant 2-3 projects and *why* they matter.
       - Use professional technical tone but easy to read.
    2. "stats": Calculate total_projects, average_score (out of 10, strictly based on potential impact/novelty), and language_count.
    3. "language_distribution": A mapping of Language -> list of concise tech keywords/tags derived from the projects in that language.
    4. "projects": A list of enriched project objects, same order as input. Each object must have:
       - "name": same as input
       - "translation": Chinese translation of the description. Concise and accurate.
       - "score": A score from 1-10. Be strict. 9-10 for game changers, 7-8 for solid tools, <6 for niche/toy projects.
       - "tech_stack": A list of 3-5 key technologies/tags (e.g., "LLM", "Rust", "Web", "CLI").
       - "is_recommended": Boolean, true if score >= 8.
    
    Return ONLY valid JSON.
    """

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini", # Or gpt-3.5-turbo, adjust based on availability
            messages=[
                {"role": "system", "content": "You are a helpful assistant that outputs JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        content = completion.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print(f"AI Analysis failed: {e}")
        return None

def get_mock_ai_data(repos):
    # This is a fallback mock data generator for visualization purposes when API key is missing
    # It attempts to generate realistic-looking data based on the actual repos found
    
    total_projects = len(repos)
    languages = {}
    for r in repos:
        lang = r.get("language", "Unknown")
        if lang not in languages:
            languages[lang] = []
        languages[lang].append("DevOps" if lang == "Go" else "AI/LLM" if lang == "Python" else "Web")

    projects = []
    
    # Mock data dictionary for better demo effect
    mock_translations = {
        "openclaw": "一个全平台的个人 AI 助手，支持任何操作系统，采用独特的龙虾风格设计。",
        "system_prompts_leaks": "收集了来自 ChatGPT、Claude 和 Gemini 等流行聊天机器人的系统提示词（System Prompts）。",
        "kimi-cli": "Kimi Code 的命令行接口版本，旨在成为你的下一个 CLI 智能代理。",
        "ext-apps": "MCP 应用协议的官方规范与 SDK 仓库，定义了嵌入式 AI 聊天机器人的标准。",
        "memU": "专为 openclaw 等 24/7 主动代理设计的记忆系统。",
        "vault": "HashiCorp 推出的机密管理工具，提供加密即服务和特权访问管理功能。",
        "protobuf": "Google 的数据交换格式（Protocol Buffers），一种轻量级、高效的结构化数据存储格式。",
        "whatsapp-web.js": "一个用于 Node.js 的 WhatsApp 客户端库，通过连接 WhatsApp Web 浏览器应用实现功能。"
    }

    for i, r in enumerate(repos):
        score = 9 if i < 3 else 7 # Fake score logic
        
        # Try to find a mock translation by repo name match
        repo_short_name = r["name"].split('/')[-1]
        translation = mock_translations.get(repo_short_name)
        
        if not translation:
            # Generic Chinese description for others to show visual effect
            lang = r.get("language", "未知语言")
            translation = f"这是一个基于 {lang} 的热门开源项目。在真实模式下，AI 会自动将项目的英文简介翻译为准确、流畅的中文，帮助您快速了解其核心功能与技术特点。"

        projects.append({
            "name": r["name"],
            "translation": translation,
            "score": score,
            "tech_stack": [r["language"], "Open Source", "Hot"],
            "is_recommended": score >= 8
        })

    return {
        "summary": "【演示模式】今日 GitHub Trending 呈现出 AI 垂直应用爆发的趋势。榜单前列的项目多集中在 AI Agent 开发工具与大模型微调框架上，显示出开发者正从单纯关注模型能力转向关注应用落地。Go 语言在基础设施领域的地位依然稳固，而 Python 则继续主导 AI 生态。建议重点关注前三名的项目，它们代表了当前开源社区最活跃的技术方向。（注：此为无 API Key 时的演示文本，配置 Key 后将显示真实 AI 分析）",
        "stats": {
            "total_projects": total_projects,
            "average_score": 8.2,
            "language_count": len(languages)
        },
        "language_distribution": languages,
        "projects": projects
    }

def generate_html(repos, ai_data):
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    # Fallback if AI data is missing
    if not ai_data:
        print("Using Mock AI Data for preview...")
        ai_data = get_mock_ai_data(repos)

    # Summary
        # Summary
        summary_section = f"""
        <div class="summary-card">
            <h2>✨ 今日重点推荐</h2>
            <p>{ai_data.get('summary', '')}</p>
            <div class="stats-row">
                <div class="stat-item">
                    <strong>{ai_data.get('stats', {}).get('total_projects', 0)}</strong>
                    <span>项目总数</span>
                </div>
                <div class="stat-item">
                    <strong>{ai_data.get('stats', {}).get('average_score', 0)}</strong>
                    <span>平均推荐分</span>
                </div>
                <div class="stat-item">
                    <strong>{ai_data.get('stats', {}).get('language_count', 0)}</strong>
                    <span>语言种类</span>
                </div>
            </div>
        </div>
        """
        
        # Language Distribution
        lang_dist_html = ""
        lang_dist = ai_data.get('language_distribution', {})
        for lang, tags in lang_dist.items():
            tags_str = ", ".join(tags)
            lang_dist_html += f"<p><strong>{lang}</strong>: {tags_str}</p>"
            
        lang_section = f"""
        <div class="lang-section">
            <h3>📊 语言分布</h3>
            {lang_dist_html}
        </div>
        """
        
        # Merge AI project data with original repos
        ai_projects_map = {p['name']: p for p in ai_data.get('projects', [])}
        projects_data = []
        for r in repos:
            p_ai = ai_projects_map.get(r['name'], {})
            projects_data.append({
                **r,
                "translation": p_ai.get('translation', r['description']),
                "score": p_ai.get('score', '-'),
                "tech_stack": p_ai.get('tech_stack', [r['language']]),
                "is_recommended": p_ai.get('is_recommended', False)
            })

    # Generate Project List HTML
    projects_html = ""
    for idx, p in enumerate(projects_data):
        rank = idx + 1
        tags_html = "".join([f'<span class="tag">{t}</span>' for t in p['tech_stack']])
        recommend_badge = f'<div class="recommend-badge">🔥 高推荐 ({p["score"]}/10)</div>' if p.get('is_recommended') else f'<div class="score-text">推荐分: {p["score"]}/10</div>'
        
        projects_html += f"""
        <div class="repo">
            <div class="repo-header">
                <span class="rank">#{rank}</span>
                <a href="{p['url']}" class="repo-name">{p['name']}</a>
            </div>
            <p class="repo-desc">{p['translation']}</p>
            {recommend_badge}
            <div class="repo-meta">
                <div class="tech-stack">
                    <strong>主要技术栈:</strong> {tags_html}
                </div>
                <div class="stars-info">
                    <span>⭐ {p['stars']}</span> &bull; <span>{p['stars_today']}</span>
                </div>
            </div>
        </div>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; background-color: #f6f8fa; }}
            .container {{ background: white; padding: 40px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
            .header {{ margin-bottom: 30px; border-bottom: 1px solid #eee; padding-bottom: 20px; }}
            .header h1 {{ margin: 0; color: #24292e; font-size: 24px; }}
            .header p {{ color: #586069; margin: 5px 0 0 0; }}
            
            .summary-card {{ background-color: #f1f8ff; border: 1px solid #c8e1ff; border-radius: 6px; padding: 20px; margin-bottom: 30px; }}
            .summary-card h2 {{ margin-top: 0; font-size: 18px; color: #0366d6; }}
            .stats-row {{ display: flex; gap: 40px; margin-top: 20px; border-top: 1px solid #c8e1ff; padding-top: 15px; }}
            .stat-item {{ display: flex; flex-direction: column; }}
            .stat-item strong {{ font-size: 20px; color: #24292e; }}
            .stat-item span {{ font-size: 12px; color: #586069; }}
            
            .lang-section {{ margin-bottom: 30px; }}
            .lang-section h3 {{ font-size: 18px; border-left: 4px solid #2ea44f; padding-left: 10px; margin-bottom: 15px; }}
            .lang-section p {{ margin: 5px 0; font-size: 14px; color: #444; }}
            
            .repo {{ border-bottom: 1px solid #eee; padding: 25px 0; }}
            .repo:last-child {{ border-bottom: none; }}
            .repo-header {{ font-size: 18px; font-weight: 600; margin-bottom: 8px; }}
            .rank {{ color: #6a737d; margin-right: 8px; font-weight: normal; }}
            .repo-name {{ color: #0366d6; text-decoration: none; }}
            .repo-desc {{ margin: 0 0 12px 0; color: #24292e; font-size: 15px; }}
            
            .recommend-badge {{ color: #d73a49; font-weight: 600; font-size: 14px; margin-bottom: 10px; }}
            .score-text {{ color: #586069; font-size: 14px; margin-bottom: 10px; }}
            
            .repo-meta {{ display: flex; flex-direction: column; gap: 8px; font-size: 13px; color: #586069; background: #fafbfc; padding: 12px; border-radius: 6px; }}
            .tech-stack {{ margin-bottom: 4px; }}
            .tag {{ display: inline-block; background-color: #f1f8ff; color: #0366d6; padding: 2px 8px; border-radius: 12px; font-size: 12px; margin-right: 4px; border: 1px solid #c8e1ff; }}
            .stars-info {{ color: #6a737d; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 GitHub Trending 每日推送</h1>
                <p>{date_str} &bull; {len(repos)} 个热门项目</p>
            </div>
            
            {summary_section}
            {lang_section}
            
            <div class="projects-list">
                {projects_html}
            </div>
        </div>
    </body>
    </html>
    """
    return html_content

def send_email(html_content, date_str):
    from_email = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
    to_email = os.environ.get("RECEIVER_EMAIL")
    
    if not to_email:
        print("Error: RECEIVER_EMAIL environment variable is not set.")
        return

    params = {
        "from": f"GitHub Trending <{from_email}>",
        "to": [to_email],
        "subject": f"GitHub Trending - {date_str}",
        "html": html_content,
    }

    try:
        print(f"Sending email to {to_email} from {from_email}...")
        email = resend.Emails.send(params)
        print(f"Email sent successfully: {email}")
    except Exception as e:
        print(f"Error sending email: {e}")

if __name__ == "__main__":
    try:
        print("Fetching GitHub trending repositories...")
        trending_repos = fetch_trending()
        print(f"Found {len(trending_repos)} repositories.")
        
        # Determine if we can run AI analysis
        ai_data = None
        if client:
            print("Running AI analysis...")
            ai_data = analyze_with_ai(trending_repos)
            print("AI analysis completed.")
        else:
            print("Skipping AI analysis (OPENAI_API_KEY not set).")
        
        html_content = generate_html(trending_repos, ai_data)
        date_str = datetime.now().strftime("%Y-%m-%d")

        # Always save a preview HTML file for testing
        preview_path = os.path.join(os.path.dirname(__file__), "trending_preview.html")
        with open(preview_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"Preview HTML saved to: {preview_path}")
        
        # Determine if we can send email
        if os.environ.get("RESEND_API_KEY") and os.environ.get("RECEIVER_EMAIL"):
            send_email(html_content, date_str)
        else:
            print("RESEND_API_KEY or RECEIVER_EMAIL not set. Skipping email sending.")
            
    except Exception as e:
        print(f"An error occurred: {e}")
        exit(1)
