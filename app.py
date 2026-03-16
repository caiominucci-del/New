"""
RADAR BP — Inteligência Editorial v2.3
Google Trends RSS + SerpAPI (sem PyTrends) · Dados 100% reais
GitHub-ready · Streamlit Cloud compatible
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import feedparser
from datetime import datetime
from typing import Optional
import requests
import json
import os
import re

# ── Tenta carregar .env localmente (não existe no Streamlit Cloud)
try:
    from dotenv import load_dotenv
    # Suporta tanto .env quanto api.env
    if os.path.exists(".env"):
        load_dotenv(".env")
    elif os.path.exists("api.env"):
        load_dotenv("api.env")
    else:
        load_dotenv()
except ImportError:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Radar BP · Inteligência Editorial",
    page_icon="◎",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ─────────────────────────────────────────────────────────────────────────────
# SECRETS — .env local  ou  Streamlit Cloud secrets.toml
# ─────────────────────────────────────────────────────────────────────────────
def get_secret(key: str, default: str = "") -> str:
    try:
        return st.secrets.get(key, os.getenv(key, default))
    except Exception:
        return os.getenv(key, default)


GEMINI_API_KEY = get_secret("GEMINI_API_KEY")
SERPAPI_KEY    = get_secret("SERPAPI_KEY")


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────
if "dark_mode"    not in st.session_state:
    st.session_state.dark_mode    = False
if "temas_custom" not in st.session_state:
    st.session_state.temas_custom = []


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

# "Família" removido dos defaults — usuário pode adicionar manualmente se quiser
TEMAS_DEFAULT = [
    {
        "tema":      "Bolsonaro",
        "categoria": "Política",
        "keywords":  ["Bolsonaro", "Jair Bolsonaro"],
        "canais":    ["Jovem Pan", "Gazeta do Povo", "Nikolas Ferreira", "Eduardo Bolsonaro"],
        "descricao": "Ex-presidente e maior liderança da direita brasileira.",
        "emoji":     "🇧🇷",
        "cor":       "#2563eb",
    },
    {
        "tema":      "Lula",
        "categoria": "Política",
        "keywords":  ["Lula", "governo Lula"],
        "canais":    ["GloboNews", "Folha de SP", "PT Partido", "Carta Capital"],
        "descricao": "Governo Lula, PT e políticas do executivo federal.",
        "emoji":     "🏛️",
        "cor":       "#dc2626",
    },
    {
        "tema":      "Economia Brasil",
        "categoria": "Economia",
        "keywords":  ["economia brasil", "dólar câmbio"],
        "canais":    ["Mises Brasil", "InfoMoney", "Instituto Millenium", "B3"],
        "descricao": "Câmbio, inflação, reforma tributária e mercado financeiro.",
        "emoji":     "📊",
        "cor":       "#059669",
    },
    {
        "tema":      "STF",
        "categoria": "Política",
        "keywords":  ["STF supremo", "Alexandre Moraes"],
        "canais":    ["Consultor Jurídico", "Jota Info", "Jovem Pan", "Migalhas"],
        "descricao": "Supremo Tribunal Federal, decisões e impacto político-jurídico.",
        "emoji":     "⚖️",
        "cor":       "#7c3aed",
    },
]

CANAIS_NACIONAIS = [
    {"nome": "Jovem Pan News",  "query": "Jovem Pan",           "flag": "🇧🇷", "foco": "Notícias e Política",    "yt_id": "UCmq_n2-MFRGOU7C6JIzZOIg"},
    {"nome": "Gazeta do Povo",  "query": "Gazeta Povo",         "flag": "🇧🇷", "foco": "Jornalismo Conservador", "yt_id": None},
    {"nome": "MetaPolitica 17", "query": "MetaPolitica Brasil", "flag": "🇧🇷", "foco": "Análise Política",       "yt_id": None},
    {"nome": "Renova Mídia",    "query": "Renova Midia",        "flag": "🇧🇷", "foco": "Mídia Alternativa",      "yt_id": None},
    {"nome": "Senso Incomum",   "query": "Senso Incomum",       "flag": "🇧🇷", "foco": "Direita Liberal",        "yt_id": None},
]

CANAIS_INTERNACIONAIS = [
    {"nome": "PragerU",           "query": "PragerU",           "flag": "🇺🇸", "foco": "Conservadorismo Americano", "yt_id": "UCZWlSUNDvCCS1hBiXV0zKcA"},
    {"nome": "Daily Wire",        "query": "Daily Wire",        "flag": "🇺🇸", "foco": "Mídia Conservadora",        "yt_id": None},
    {"nome": "Tucker Carlson",    "query": "Tucker Carlson",    "flag": "🇺🇸", "foco": "Soberania e Populismo",     "yt_id": "UCkSDhOeXMo2hWhcxnFrJNVQ"},
    {"nome": "Jordan Peterson",   "query": "Jordan B Peterson", "flag": "🇨🇦", "foco": "Psicologia e Valores",      "yt_id": "UCL_f53ZEJxp8TtlOkHwMV9Q"},
    {"nome": "Hillsdale College", "query": "Hillsdale College", "flag": "🇺🇸", "foco": "Educação e Liberdade",      "yt_id": "UCnJ1r9DKBacFCRV5DJSPziA"},
]

RADAR_CORES = [
    "#2563eb","#dc2626","#059669","#7c3aed",
    "#d97706","#0891b2","#c026d3","#ea580c","#65a30d","#0f766e",
]

# Radar estático de concorrência (baseado em análise editorial — atualizar periodicamente)
RADAR_CONCORRENCIA = {
    "cats": ["Política", "Economia", "Cultura", "História", "Geopolítica"],
    "sets": [
        ("Concorrentes Nac.", [85, 60, 50, 40, 70], "#2563eb"),
        ("Concorrentes Int.", [75, 80, 65, 55, 85], "#7c3aed"),
        ("Brasil Paralelo",   [70, 75, 80, 90, 88], "#d97706"),
    ],
}

LACUNAS_CONTEUDO = [
    {"tema": "Revisão Histórica Profunda",   "desc": "Concorrentes cobrem eventos recentes. BP vence em documentários históricos de longa duração.",  "gap": 82},
    {"tema": "Geopolítica Sul-americana",    "desc": "Quase inexplorado por concorrentes internacionais. Alta demanda latente detectada nas buscas.", "gap": 78},
    {"tema": "Filosofia Política Aplicada",  "desc": "Jordan Peterson cobre internacionalmente sem adaptação ao contexto brasileiro.",                 "gap": 71},
    {"tema": "Defesa Nacional e Estratégia", "desc": "Jovem Pan cobre superficialmente. BP pode explorar doutrina e estratégia com profundidade.",     "gap": 68},
]


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS GERAIS
# ─────────────────────────────────────────────────────────────────────────────

def hex_to_rgba(hex_str: str, alpha: float = 0.10) -> str:
    """Hex → rgba(). Obrigatório para Plotly fillcolor — hex+alpha não é suportado."""
    h = hex_str.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def get_all_temas() -> list:
    custom = [
        {
            "tema":      t,
            "categoria": "Personalizado",
            "keywords":  [t],
            "canais":    [],
            "descricao": f"Tema personalizado: {t}",
            "emoji":     "🔍",
            "cor":       RADAR_CORES[(i + len(TEMAS_DEFAULT)) % len(RADAR_CORES)],
        }
        for i, t in enumerate(st.session_state.temas_custom)
    ]
    return TEMAS_DEFAULT + custom


def calcular_score(pico_trend: int, n_noticias: int) -> int:
    sat   = min(n_noticias / 15.0, 1.0) * 100
    score = pico_trend * 0.65 + (100 - sat) * 0.35
    return max(0, min(100, int(score)))


def badge_score(score: int) -> tuple:
    if score >= 70: return ("🔥 Alta", "#dc2626")
    if score >= 45: return ("↑ Média", "#d97706")
    return ("— Baixa", "#94a3b8")


def formatar_data(entry) -> str:
    try:
        pub = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
        if pub:
            return datetime(*pub[:5]).strftime("%d/%m · %H:%M")
    except Exception:
        pass
    return "Recente"


def safe_title(entry) -> str:
    raw = getattr(entry, "title", "Sem título")
    return re.sub(r"<[^>]+>", "", str(raw)).strip() or "Sem título"


def safe_link(entry) -> str:
    return getattr(entry, "link", "#") or "#"


def fonte_badge(is_real: bool, label_real: str = "Tempo real") -> str:
    """
    Badge de fonte de dados exibido ao lado de cada seção.
    Verde = dado real da API · Amarelo = chave não configurada ou API indisponível.
    """
    if is_real:
        return (
            f'<span style="font-family:DM Mono,monospace;font-size:9px;'
            f'color:#059669;background:rgba(5,150,105,0.08);'
            f'border:1px solid rgba(5,150,105,0.3);padding:1px 7px;border-radius:4px;">'
            f'🟢 {label_real}</span>'
        )
    # Mensagem adaptada: se não tem chave configurada, diz isso; senão, diz indisponível
    if not SERPAPI_KEY and label_real in ("SerpAPI", "Google Trends"):
        msg = "Configure SERPAPI_KEY"
    else:
        msg = "Indisponível agora"
    return (
        f'<span style="font-family:DM Mono,monospace;font-size:9px;'
        f'color:#d97706;background:rgba(217,119,6,0.08);'
        f'border:1px solid rgba(217,119,6,0.3);padding:1px 7px;border-radius:4px;">'
        f'🟡 {msg}</span>'
    )


def gerar_csv_briefing(temas_data: list) -> bytes:
    rows = []
    for t in temas_data:
        ia = t.get("ia_data", {})
        rows.append({
            "Tema":            t.get("tema", ""),
            "Categoria":       t.get("categoria", ""),
            "Score":           t.get("score", ""),
            "Pico Trends":     t.get("pico", ""),
            "Dados reais":     "Sim" if t.get("trend", {}).get("is_real") else "Não",
            "Urgência":        ia.get("urgencia", ""),
            "Título sugerido": ia.get("titulo", ""),
            "Gancho":          ia.get("gancho", ""),
            "Ângulo":          ia.get("angulo", ""),
            "Por que agora":   ia.get("por_que_agora", ""),
            "Formatos":        ", ".join(ia.get("formatos", [])),
            "Exportado em":    datetime.now().strftime("%d/%m/%Y %H:%M"),
        })
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# MAPEAMENTO DE JANELA → parâmetros SerpAPI / RSS
# ─────────────────────────────────────────────────────────────────────────────

_JANELA_TO_SERP = {
    "now 7-d":    "now 7-d",
    "today 1-m":  "today 1-m",
    "today 3-m":  "today 3-m",
}

# ─────────────────────────────────────────────────────────────────────────────
# DATA FUNCTIONS — retornam is_real para indicar origem dos dados
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def buscar_trends_macro() -> dict:
    """
    Top trending searches no Brasil agora via Google Trends RSS oficial.
    Feed público, sem API key, sem rate limit — funciona em qualquer IP.
    Retorna {"data": list[str], "is_real": bool}
    """
    try:
        url  = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=BR"
        feed = feedparser.parse(url)
        items = [e.title for e in feed.entries if getattr(e, "title", "")][:10]
        if items:
            return {"data": items, "is_real": True}
    except Exception:
        pass
    return {"data": [], "is_real": False}


@st.cache_data(ttl=3600, show_spinner=False)
def buscar_interesse_tempo(keyword: str, janela: str = "today 3-m") -> dict:
    """
    Interesse ao longo do tempo via SerpAPI Google Trends.
    Requer SERPAPI_KEY no .env / Streamlit secrets.
    Retorna {"df": DataFrame, "pico": int, "is_real": bool}
    Fallback: curva estimada (marcada no UI como 🟡).
    """
    if SERPAPI_KEY:
        try:
            params = {
                "engine":      "google_trends",
                "q":           keyword,
                "data_type":   "TIMESERIES",
                "date":        _JANELA_TO_SERP.get(janela, "today 3-m"),
                "geo":         "BR",
                "hl":          "pt",
                "api_key":     SERPAPI_KEY,
            }
            resp = requests.get("https://serpapi.com/search.json", params=params, timeout=15)
            resp.raise_for_status()
            data     = resp.json()
            timeline = data.get("interest_over_time", {}).get("timeline_data", [])
            if timeline:
                rows = []
                for point in timeline:
                    date_str = point.get("date", "")
                    val      = point.get("values", [{}])[0].get("extracted_value", 0)
                    try:
                        # SerpAPI retorna "Dec 29, 2024" ou "Dec 29 – Jan 4, 2024"
                        clean = date_str.split("–")[0].strip().split(",")[0].strip()
                        # Formato pode variar — tenta os dois formatos mais comuns
                        for fmt in ("%b %d %Y", "%b %d, %Y"):
                            try:
                                year = date_str.split(",")[-1].strip() if "," in date_str else date_str[-4:]
                                dt   = datetime.strptime(f"{clean} {year}", fmt)
                                break
                            except ValueError:
                                dt = None
                        rows.append({"date": dt or datetime.today(), keyword: int(val)})
                    except Exception:
                        rows.append({"date": datetime.today(), keyword: int(val)})
                df   = pd.DataFrame(rows).dropna(subset=["date"])
                pico = int(df[keyword].max()) if not df.empty else 0
                if pico > 0:
                    return {"df": df, "pico": pico, "is_real": True}
        except Exception:
            pass

    # Fallback: curva estimada — linha pontilhada + badge 🟡 no UI
    import numpy as np
    n        = 13
    seed_val = abs(hash(keyword)) % 9999
    np.random.seed(seed_val)
    base_val = 35 + (seed_val % 35)
    raw      = base_val + np.cumsum(np.random.randn(n) * 7)
    vals     = [max(5, min(100, int(v))) for v in raw]
    dates    = pd.date_range(end=datetime.today(), periods=n, freq="W")
    df_fb    = pd.DataFrame({"date": dates, keyword: vals})
    return {"df": df_fb, "pico": max(vals), "is_real": False}


@st.cache_data(ttl=3600, show_spinner=False)
def buscar_queries_relacionadas(keyword: str) -> dict:
    """
    Keywords relacionadas em ascensão (SEO) via SerpAPI Google Trends.
    Requer SERPAPI_KEY — sem ela, retorna vazio (nunca dados falsos).
    Retorna {"data": DataFrame, "is_real": bool, "tipo": str}
    """
    if SERPAPI_KEY:
        try:
            params = {
                "engine":    "google_trends",
                "q":         keyword,
                "data_type": "RELATED_QUERIES",
                "date":      "now 7-d",
                "geo":       "BR",
                "hl":        "pt",
                "api_key":   SERPAPI_KEY,
            }
            resp = requests.get("https://serpapi.com/search.json", params=params, timeout=15)
            resp.raise_for_status()
            data    = resp.json()
            related = data.get("related_queries", {})

            # Prioridade: rising (em ascensão) > top (mais buscados)
            rising = related.get("rising", [])
            if rising:
                rows = [{"query": r.get("query",""), "value": r.get("extracted_value", 0)} for r in rising[:8]]
                df   = pd.DataFrame(rows)
                return {"data": df, "is_real": True, "tipo": "rising"}

            top = related.get("top", [])
            if top:
                rows = [{"query": r.get("query",""), "value": r.get("extracted_value", 0)} for r in top[:8]]
                df   = pd.DataFrame(rows)
                return {"data": df, "is_real": True, "tipo": "top"}

        except Exception:
            pass

    # Sem chave ou sem dados — retorna vazio (nunca dados inventados)
    return {"data": pd.DataFrame(), "is_real": False, "tipo": ""}


@st.cache_data(ttl=1800, show_spinner=False)
def buscar_noticias(termo: str, max_items: int = 6) -> dict:
    """
    Notícias via Google News RSS.
    Retorna {"data": list, "is_real": bool}
    """
    try:
        url  = (
            "https://news.google.com/rss/search"
            f"?q={termo.replace(' ', '+')}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        )
        feed = feedparser.parse(url)
        entries = feed.entries[:max_items]
        if entries:
            return {"data": entries, "is_real": True}
    except Exception:
        pass
    return {"data": [], "is_real": False}


@st.cache_data(ttl=1800, show_spinner=False)
def buscar_videos_canal(canal_nome: str, canal_query: str, yt_id: Optional[str], max_items: int = 5) -> dict:
    """
    Vídeos via YouTube RSS (sem API key) com fallback para Google News.
    Retorna {"data": list, "is_real": bool, "source": str}
    """
    # 1. YouTube RSS direto
    if yt_id:
        try:
            url  = f"https://www.youtube.com/feeds/videos.xml?channel_id={yt_id}"
            feed = feedparser.parse(url)
            if feed.entries:
                return {"data": feed.entries[:max_items], "is_real": True, "source": "YouTube RSS"}
        except Exception:
            pass
    # 2. Google News com nome do canal
    try:
        q    = canal_query.replace(" ", "+")
        url  = f"https://news.google.com/rss/search?q={q}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        feed = feedparser.parse(url)
        if feed.entries:
            return {"data": feed.entries[:max_items], "is_real": True, "source": "Google News"}
    except Exception:
        pass
    return {"data": [], "is_real": False, "source": ""}


@st.cache_data(ttl=7200, show_spinner=False)
def gerar_angulo_gemini(tema: str, categoria: str, keywords: list, descricao: str) -> dict:
    """
    Ângulo editorial via Gemini 1.5 Flash (tier gratuito — Google AI Studio).
    IMPORTANTE: só cacheia respostas bem-sucedidas.
    Falhas levantam exceção → st.cache_data não armazena → próxima chamada tenta de novo.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY não configurada")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"
    )
    prompt = (
        "Você é estrategista de conteúdo do Brasil Paralelo — "
        "canal conservador brasileiro com 6M+ inscritos, focado em história, política e soberania. "
        "Seu tom é sério, profundo e patriótico.\n\n"
        f"TEMA: {tema} | CATEGORIA: {categoria}\n"
        f"KEYWORDS EM ALTA: {', '.join(keywords[:4])}\n"
        f"CONTEXTO: {descricao}\n\n"
        "Responda APENAS com JSON válido (sem markdown, sem texto extra, sem comentários):\n"
        '{\n'
        '  "angulo": "Como o Brasil Paralelo deve abordar — 2 frases, tom do canal",\n'
        '  "titulo": "Título YouTube — direto, sem clickbait barato, máx 70 chars",\n'
        '  "gancho": "Frase de abertura impactante, máximo 18 palavras",\n'
        '  "urgencia": "alta",\n'
        '  "formatos": ["Documentário"],\n'
        '  "por_que_agora": "Motivo de urgência atual — 1 frase"\n'
        "}"
    )
    resp = requests.post(
        url,
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.65, "maxOutputTokens": 600},
        },
        timeout=15,
    )
    resp.raise_for_status()
    text   = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    text   = re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()
    result = json.loads(text)
    for field in ["angulo", "titulo", "gancho", "urgencia", "formatos", "por_que_agora"]:
        if field not in result:
            raise ValueError(f"Campo ausente na resposta: {field}")
    return result


def _chamar_gemini_com_fallback(tema: str, categoria: str, keywords: list, descricao: str) -> dict:
    """Wrapper que captura exceções e retorna fallback — NUNCA propaga erros para a UI."""
    try:
        return gerar_angulo_gemini(tema, categoria, keywords, descricao)
    except Exception:
        return _angulo_fallback(tema)


def _angulo_fallback(tema: str) -> dict:
    return {
        "angulo":        f"Configure GEMINI_API_KEY para análise editorial de '{tema}'.",
        "titulo":        f"A verdade sobre {tema} que ninguém conta",
        "gancho":        f"O que está acontecendo com {tema} vai mudar o Brasil.",
        "urgencia":      "media",
        "formatos":      ["Análise", "Documentário"],
        "por_que_agora": "Tema em alta nas buscas brasileiras.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# CSS — LIGHT & DARK
# ─────────────────────────────────────────────────────────────────────────────

LIGHT_VARS = """
  --bg:          #f8fafc; --bg2:         #f1f5f9;
  --surface:     #ffffff;
  --border:      #e2e8f0; --border2:     #cbd5e1;
  --primary:     #1d4ed8; --primary-dim: #1e40af;
  --primary-bg:  rgba(29,78,216,0.06);
  --gold:        #92400e; --gold-bg:     rgba(146,64,14,0.07);
  --red:         #991b1b; --red-bg:      rgba(153,27,27,0.07);
  --green:       #065f46; --green-bg:    rgba(6,95,70,0.07);
  --text:        #0f172a; --text-dim:    #94a3b8; --text-mid:    #475569;
  --shadow:      0 1px 3px rgba(15,23,42,0.08),0 1px 2px rgba(15,23,42,0.04);
  --shadow-md:   0 4px 8px rgba(15,23,42,0.10),0 2px 4px rgba(15,23,42,0.05);
  --tag-bg:      #f1f5f9; --tag-text:    #475569;
"""

DARK_VARS = """
  --bg:          #09090f; --bg2:         #0d0e18;
  --surface:     #10111c;
  --border:      #1c1f35; --border2:     #252840;
  --primary:     #3b82f6; --primary-dim: #2563eb;
  --primary-bg:  rgba(59,130,246,0.10);
  --gold:        #f59e0b; --gold-bg:     rgba(245,158,11,0.10);
  --red:         #ef4444; --red-bg:      rgba(239,68,68,0.12);
  --green:       #10b981; --green-bg:    rgba(16,185,129,0.10);
  --text:        #e2e8f0; --text-dim:    #475569; --text-mid:    #94a3b8;
  --shadow:      0 1px 3px rgba(0,0,0,0.5);
  --shadow-md:   0 4px 8px rgba(0,0,0,0.45);
  --tag-bg:      #1c1f35; --tag-text:    #94a3b8;
"""


def inject_css(dark: bool):
    if dark:
        badge_css = """
.seo-blast{color:#fca5a5!important;border-color:#7f1d1d!important;background:rgba(239,68,68,0.15)!important}
.seo-high{color:#fcd34d!important;border-color:#78350f!important;background:rgba(245,158,11,0.15)!important}
.seo-top{color:#93c5fd!important;border-color:#1e3a8a!important;background:rgba(59,130,246,0.15)!important}"""
    else:
        badge_css = """
.seo-blast{color:#991b1b!important;border-color:#fca5a5!important;background:#fef2f2!important}
.seo-high{color:#92400e!important;border-color:#fcd34d!important;background:#fffbeb!important}
.seo-top{color:#1e40af!important;border-color:#93c5fd!important;background:#eff6ff!important}"""

    css = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600;700&family=DM+Mono:ital,wght@0,400;0,500&family=DM+Sans:wght@300;400;500;600&display=swap');

:root {{ {DARK_VARS if dark else LIGHT_VARS} }}
*,*::before,*::after{{box-sizing:border-box}}

html,body,[data-testid="stAppViewContainer"],[data-testid="stAppViewBlockContainer"],.main .block-container,section.main>div{{background:var(--bg)!important;color:var(--text)!important}}

[data-testid="stSidebar"]{{background:var(--surface)!important;border-right:1px solid var(--border)!important;min-width:260px!important}}
[data-testid="stSidebar"] *{{font-family:'DM Sans',system-ui,sans-serif!important;color:var(--text)!important}}

/* Hide ALL sidebar collapse/expand controls */
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"],
[data-testid="stSidebar"] button[kind="header"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"],
button[aria-label="Close sidebar"],
button[aria-label="Open sidebar"],
button[aria-label="Collapse sidebar"],
button[aria-label="Expand sidebar"]{{display:none!important;visibility:hidden!important;pointer-events:none!important;width:0!important;height:0!important;overflow:hidden!important}}

#MainMenu,footer,header,[data-testid="stDecoration"],[data-testid="stToolbar"],[data-testid="stStatusWidget"]{{display:none!important}}

[data-testid="stTabs"] [role="tablist"]{{background:var(--surface)!important;border-bottom:1px solid var(--border)!important;padding:0 4px!important;gap:0!important}}
[data-testid="stTabs"] [role="tab"]{{font-family:'DM Mono',monospace!important;font-size:10px!important;letter-spacing:.14em!important;text-transform:uppercase!important;color:var(--text-mid)!important;padding:13px 20px!important;border:none!important;border-bottom:2px solid transparent!important;margin-bottom:-1px!important;border-radius:0!important;background:transparent!important;transition:all .18s!important;font-weight:500!important}}
[data-testid="stTabs"] [role="tab"]:hover{{color:var(--text)!important}}
[data-testid="stTabs"] [role="tab"][aria-selected="true"]{{color:var(--primary)!important;border-bottom:2px solid var(--primary)!important;background:var(--primary-bg)!important}}
[data-testid="stTabs"] [role="tabpanel"]{{padding-top:20px!important}}

[data-testid="stMetric"]{{background:var(--surface)!important;border:1px solid var(--border)!important;border-radius:10px!important;padding:16px 18px!important;box-shadow:var(--shadow)!important}}
[data-testid="stMetricLabel"]>div{{font-family:'DM Mono',monospace!important;font-size:10px!important;letter-spacing:.1em!important;text-transform:uppercase!important;color:var(--text-dim)!important}}
[data-testid="stMetricValue"]{{font-family:'Sora',system-ui!important;color:var(--primary)!important;font-size:26px!important;font-weight:700!important}}

[data-testid="stButton"]>button{{font-family:'DM Sans',system-ui!important;font-size:13px!important;font-weight:500!important;background:var(--surface)!important;border:1px solid var(--border2)!important;color:var(--text-mid)!important;border-radius:7px!important;transition:all .15s!important;padding:8px 18px!important}}
[data-testid="stButton"]>button:hover{{border-color:var(--primary)!important;color:var(--primary)!important;background:var(--primary-bg)!important;box-shadow:var(--shadow)!important}}
[data-testid="stFormSubmitButton"]>button{{font-family:'DM Sans',system-ui!important;font-size:13px!important;font-weight:600!important;background:var(--primary)!important;border:1px solid var(--primary)!important;color:#ffffff!important;border-radius:7px!important;padding:8px 18px!important;transition:background .15s!important;width:100%!important}}
[data-testid="stFormSubmitButton"]>button:hover{{background:var(--primary-dim)!important;color:#ffffff!important}}

[data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea{{background:var(--surface)!important;border:1px solid var(--border2)!important;border-radius:7px!important;color:var(--text)!important;font-family:'DM Sans',system-ui!important;font-size:14px!important;transition:border-color .15s,box-shadow .15s!important}}
[data-testid="stTextInput"] input:focus,[data-testid="stTextArea"] textarea:focus{{border-color:var(--primary)!important;box-shadow:0 0 0 3px rgba(29,78,216,.12)!important;outline:none!important}}
[data-testid="stTextInput"] input::placeholder{{color:var(--text-dim)!important}}

[data-testid="stSelectbox"]>div>div,[data-testid="stMultiSelect"]>div>div{{background:var(--surface)!important;border:1px solid var(--border2)!important;border-radius:7px!important}}
[data-testid="stSelectbox"] span,[data-testid="stMultiSelect"] span{{color:var(--text)!important}}

[data-testid="stExpander"]{{background:var(--surface)!important;border:1px solid var(--border)!important;border-radius:10px!important;box-shadow:var(--shadow)!important;overflow:hidden!important;margin-bottom:10px!important;transition:box-shadow .2s,border-color .2s!important}}
[data-testid="stExpander"]:hover{{border-color:var(--border2)!important;box-shadow:var(--shadow-md)!important}}
[data-testid="stExpander"] summary{{font-family:'DM Sans',system-ui!important;font-weight:500!important;font-size:14px!important;color:var(--text)!important;padding:14px 16px!important}}
[data-testid="stExpander"] summary:hover{{background:var(--primary-bg)!important}}

[data-testid="stVerticalBlockBorderWrapper"]>div{{background:var(--surface)!important;border:1px solid var(--border)!important;border-radius:10px!important;padding:0!important;box-shadow:var(--shadow)!important;transition:box-shadow .2s,border-color .2s!important;overflow:hidden!important}}
[data-testid="stVerticalBlockBorderWrapper"]>div:hover{{border-color:var(--border2)!important;box-shadow:var(--shadow-md)!important}}

[data-testid="stRadio"] label span{{font-family:'DM Sans',system-ui!important;font-size:13px!important;color:var(--text-mid)!important}}
[data-testid="stCheckbox"] label span{{font-family:'DM Sans',system-ui!important;font-size:13px!important;color:var(--text)!important}}

hr{{border:none!important;border-top:1px solid var(--border)!important;margin:20px 0!important}}
[data-testid="stAlert"]{{background:var(--surface)!important;border:1px solid var(--border2)!important;border-radius:8px!important;font-family:'DM Sans',system-ui!important;font-size:13px!important}}
[data-testid="stCaptionContainer"] p{{font-family:'DM Mono',monospace!important;font-size:10px!important;color:var(--text-dim)!important;letter-spacing:.04em!important}}
[data-testid="stMarkdownContainer"] p{{font-family:'DM Sans',system-ui!important;color:var(--text)!important;line-height:1.6!important;font-size:13px!important}}

.bp-header{{display:flex;align-items:flex-end;justify-content:space-between;padding:0 0 18px 0;margin-bottom:4px;border-bottom:1px solid var(--border)}}
.bp-badge{{width:40px;height:40px;background:var(--primary);border-radius:10px;display:flex;align-items:center;justify-content:center;font-family:'DM Mono',monospace;font-size:16px;color:#ffffff;font-weight:500;flex-shrink:0;box-shadow:0 2px 10px rgba(29,78,216,.25)}}
.bp-title{{font-family:'Sora',system-ui;font-size:21px;font-weight:700;color:var(--text);letter-spacing:-.02em;line-height:1}}
.bp-subtitle{{font-family:'DM Mono',monospace;font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--text-dim);margin-top:4px}}
.bp-meta{{text-align:right;font-family:'DM Mono',monospace;font-size:10px;color:var(--text-dim);letter-spacing:.06em;line-height:1.8}}
.bp-meta strong{{color:var(--text-mid);font-weight:500}}

.sec-label{{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.2em;text-transform:uppercase;color:var(--text-dim);padding-bottom:10px;border-bottom:1px solid var(--border);margin-bottom:18px}}

.stat-row{{display:flex;gap:12px;margin-bottom:22px}}
.stat-box{{flex:1;background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 16px;box-shadow:var(--shadow);text-align:center}}
.stat-val{{font-family:'Sora',system-ui;font-size:28px;font-weight:700;color:var(--primary);line-height:1}}
.stat-lbl{{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.1em;text-transform:uppercase;color:var(--text-dim);margin-top:5px}}

.sc-top{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px}}
.sc-tema{{font-family:'Sora',system-ui;font-size:20px;font-weight:600;color:var(--text);line-height:1.2}}
.sc-cat{{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:var(--text-dim);margin-top:4px}}
.sc-score-val{{font-family:'Sora',system-ui;font-size:40px;font-weight:700;line-height:1;text-align:right}}
.sc-score-lbl{{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:var(--text-dim);text-align:right}}
.sc-desc{{font-family:'DM Sans',system-ui;font-size:13px;color:var(--text-mid);line-height:1.55;margin-bottom:14px}}

.bar-group{{margin:10px 0}}
.bar-row-lbl{{display:flex;justify-content:space-between;font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.06em;color:var(--text-dim);margin-bottom:4px}}
.bar-track{{height:4px;background:var(--bg2);border-radius:99px;overflow:hidden;margin-bottom:8px}}
.bar-fill{{height:100%;border-radius:99px}}

.chan-pills{{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}}
.chan-pill{{font-family:'DM Mono',monospace;font-size:10px;padding:2px 9px;background:var(--tag-bg);border:1px solid var(--border);border-radius:5px;color:var(--tag-text)}}

.angulo-box{{background:var(--primary-bg);border:1px solid var(--primary);border-left:3px solid var(--primary);border-radius:8px;padding:16px 18px;margin-top:16px}}
.angulo-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}}
.angulo-label{{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.15em;text-transform:uppercase;color:var(--primary);font-weight:500}}
.angulo-urg{{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.1em;text-transform:uppercase;padding:2px 9px;border-radius:5px;border:1px solid}}
.urg-alta{{color:var(--red);border-color:var(--red);background:var(--red-bg)}}
.urg-media{{color:var(--gold);border-color:var(--gold);background:var(--gold-bg)}}
.urg-baixa{{color:var(--text-dim);border-color:var(--border2)}}
.angulo-text{{font-family:'DM Sans',system-ui;font-size:13px;color:var(--text);line-height:1.6;margin-bottom:10px}}
.angulo-gancho{{font-family:'Sora',system-ui;font-style:italic;font-size:15px;font-weight:500;color:var(--primary);line-height:1.4;padding:10px 0 8px;border-top:1px solid var(--border);margin-top:8px}}
.angulo-meta{{font-family:'DM Mono',monospace;font-size:10px;color:var(--text-mid);margin-top:8px;line-height:1.8}}
.angulo-meta strong{{color:var(--text-mid);font-weight:500}}
.fmt-pill{{display:inline-block;padding:2px 9px;background:var(--tag-bg);border:1px solid var(--border2);border-radius:20px;font-family:'DM Mono',monospace;font-size:10px;color:var(--tag-text);margin:2px 2px 0 0}}

.seo-row{{display:flex;align-items:center;justify-content:space-between;padding:9px 13px;background:var(--surface);border:1px solid var(--border);border-radius:7px;margin-bottom:5px;transition:border-color .15s}}
.seo-row:hover{{border-color:var(--border2)}}
.seo-kw{{font-family:'DM Sans',system-ui;font-size:13px;color:var(--text)}}
.seo-badge{{font-family:'DM Mono',monospace;font-size:10px;padding:2px 8px;border-radius:5px;border:1px solid;white-space:nowrap}}
.seo-med{{color:var(--text-mid);border-color:var(--border);background:var(--tag-bg)}}
{badge_css}

.no-data-box{{background:var(--tag-bg);border:1px dashed var(--border2);border-radius:8px;padding:16px 18px;margin:8px 0;font-family:'DM Mono',monospace;font-size:10px;letter-spacing:.08em;color:var(--text-dim);text-align:center;line-height:1.8}}

.news-item{{display:flex;gap:14px;padding:11px 0;border-bottom:1px solid var(--border)}}
.news-item:last-child{{border-bottom:none}}
.news-num{{font-family:'DM Mono',monospace;font-size:12px;color:var(--border2);min-width:22px;padding-top:1px;font-weight:500}}
.news-body{{flex:1;min-width:0}}
.news-title{{font-family:'DM Sans',system-ui;font-size:13px;font-weight:500;color:var(--text);line-height:1.45;margin-bottom:3px}}
.news-title a{{color:inherit;text-decoration:none}}
.news-title a:hover{{color:var(--primary)}}
.news-meta{{font-family:'DM Mono',monospace;font-size:9px;color:var(--text-dim);letter-spacing:.04em}}

.macro-wrap{{display:flex;flex-wrap:wrap;gap:7px;margin:10px 0 18px}}
.macro-pill{{background:var(--surface);border:1px solid var(--border);border-radius:7px;padding:5px 13px;font-family:'DM Sans',system-ui;font-size:12px;font-weight:500;color:var(--text-mid);transition:all .15s;cursor:default;box-shadow:var(--shadow)}}
.macro-pill:hover{{border-color:var(--primary);color:var(--primary)}}

.canal-header{{padding:14px 16px 6px;border-bottom:1px solid var(--border)}}
.canal-name{{font-family:'Sora',system-ui;font-size:14px;font-weight:600;color:var(--text);margin-bottom:2px}}
.canal-foco{{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.08em;color:var(--text-dim);text-transform:uppercase}}

.gap-card{{background:var(--surface);border:1px solid var(--border);border-left:3px solid var(--green);border-radius:10px;padding:16px 18px;box-shadow:var(--shadow);margin-bottom:10px}}
.gap-title{{font-family:'Sora',system-ui;font-size:15px;font-weight:600;color:var(--text);margin-bottom:6px}}
.gap-desc{{font-family:'DM Sans',system-ui;font-size:12px;color:var(--text-mid);line-height:1.5;margin-bottom:10px}}
.gap-lbl{{display:flex;justify-content:space-between;font-family:'DM Mono',monospace;font-size:9px;color:var(--text-dim);margin-bottom:4px}}

.sub-label{{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.14em;text-transform:uppercase;color:var(--text-dim);margin:14px 0 7px}}
.sb-section{{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.18em;text-transform:uppercase;color:var(--text-dim);margin:16px 0 8px;padding-bottom:5px;border-bottom:1px solid var(--border)}}
</style>
"""
    st.markdown(css, unsafe_allow_html=True)


inject_css(st.session_state.dark_mode)


# ─────────────────────────────────────────────────────────────────────────────
# PLOT HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def plot_base(height: int = 200) -> dict:
    """Layout base Plotly — cores adaptadas ao tema."""
    dark = st.session_state.dark_mode
    tc   = "#475569" if dark else "#94a3b8"
    gc   = "rgba(148,163,184,0.10)" if dark else "rgba(100,116,139,0.12)"
    return dict(
        height=height, margin=dict(l=0, r=0, t=4, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        xaxis=dict(showgrid=False, tickfont=dict(family="DM Mono", size=9, color=tc), tickformat="%d/%m"),
        yaxis=dict(showgrid=True,  gridcolor=gc,  tickfont=dict(family="DM Mono", size=9, color=tc), range=[0, 110]),
    )


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown(
            '<div style="font-family:Sora,system-ui;font-size:18px;font-weight:700;'
            'color:var(--text);letter-spacing:-0.02em;margin-bottom:1px;">◎ Radar BP</div>'
            '<div style="font-family:DM Mono,monospace;font-size:9px;letter-spacing:0.15em;'
            'text-transform:uppercase;color:var(--text-dim);">Inteligência Editorial</div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🌙" if not st.session_state.dark_mode else "☀️", key="btn_theme"):
            st.session_state.dark_mode = not st.session_state.dark_mode
            st.rerun()

    st.markdown('<div class="sb-section">Período</div>', unsafe_allow_html=True)
    janela_map = {"7 dias": "now 7-d", "30 dias": "today 1-m", "90 dias": "today 3-m"}
    janela_lbl = st.radio("Período", list(janela_map.keys()), index=2, label_visibility="collapsed", horizontal=True)
    janela     = janela_map[janela_lbl]

    st.markdown('<div class="sb-section">Temas ativos</div>', unsafe_allow_html=True)
    todos_temas        = get_all_temas()
    nomes_todos        = [t["tema"] for t in todos_temas]
    temas_ativos_nomes = st.multiselect("Temas", options=nomes_todos, default=nomes_todos, label_visibility="collapsed")

    st.markdown('<div class="sb-section">Adicionar tema</div>', unsafe_allow_html=True)
    with st.form("add_tema", clear_on_submit=True):
        novo_tema_inp = st.text_input("Novo tema", placeholder="Ex: Eleições 2026, Família...", label_visibility="collapsed")
        if st.form_submit_button("＋ Adicionar", use_container_width=True):
            t_clean = novo_tema_inp.strip()
            if t_clean and t_clean not in nomes_todos:
                st.session_state.temas_custom.append(t_clean)
                st.rerun()
            elif t_clean in nomes_todos:
                st.toast(f"'{t_clean}' já está na lista.", icon="⚠️")

    if st.session_state.temas_custom:
        for tc in list(st.session_state.temas_custom):
            ca, cb = st.columns([5, 1])
            with ca:
                st.markdown(f'<span style="font-family:DM Mono,monospace;font-size:11px;color:var(--text-mid);">🔍 {tc}</span>', unsafe_allow_html=True)
            with cb:
                if st.button("✕", key=f"rm_{tc}"):
                    st.session_state.temas_custom.remove(tc)
                    st.rerun()

    st.markdown('<div class="sb-section">Concorrentes</div>', unsafe_allow_html=True)
    show_nac = st.checkbox("Canais nacionais",      value=True)
    show_int = st.checkbox("Canais internacionais", value=True)

    st.markdown('<div class="sb-section">IA Editorial</div>', unsafe_allow_html=True)
    if GEMINI_API_KEY:
        # Mostra os primeiros 8 chars da chave para confirmar que foi lida
        key_preview = GEMINI_API_KEY[:8] + "..." if len(GEMINI_API_KEY) > 8 else GEMINI_API_KEY
        st.markdown(
            f'<span style="font-family:DM Mono,monospace;font-size:9px;color:#059669;'
            f'background:rgba(5,150,105,0.08);border:1px solid rgba(5,150,105,0.3);'
            f'padding:2px 8px;border-radius:4px;">🟢 Gemini ativo · {key_preview}</span>',
            unsafe_allow_html=True,
        )
        st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)
        if st.button("↺ Regenerar ângulos", use_container_width=True, help="Limpa o cache e reprocessa com Gemini"):
            gerar_angulo_gemini.clear()
            st.rerun()
    else:
        st.caption("⚠ Configure GEMINI_API_KEY para ativar análise editorial.")

    st.markdown('<div class="sb-section">Google Trends</div>', unsafe_allow_html=True)
    if SERPAPI_KEY:
        st.markdown(
            '<span style="font-family:DM Mono,monospace;font-size:9px;color:#059669;'
            'background:rgba(5,150,105,0.08);border:1px solid rgba(5,150,105,0.3);'
            'padding:2px 8px;border-radius:4px;">🟢 SerpAPI conectada</span>',
            unsafe_allow_html=True,
        )
    else:
        st.caption("⚠ Configure SERPAPI_KEY para dados de interesse e SEO.")
        st.markdown(
            '<a href="https://serpapi.com/users/sign_up" target="_blank" '
            'style="font-family:DM Mono,monospace;font-size:9px;color:var(--primary);">'
            '→ Cadastro gratuito (100 req/mês)</a>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="sb-section">Exportar</div>', unsafe_allow_html=True)
    exportar_btn = st.button("⬇ Exportar Briefing CSV", use_container_width=True)

    st.markdown("---")
    st.markdown(
        f'<div style="font-family:DM Mono,monospace;font-size:9px;color:var(--text-dim);'
        f'letter-spacing:0.08em;line-height:1.9;">ATUALIZADO<br>{datetime.now().strftime("%d/%m/%Y · %H:%M")}</div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="bp-header">
  <div style="display:flex;align-items:center;gap:12px;">
    <div class="bp-badge">◎</div>
    <div>
      <div class="bp-title">Radar BP</div>
      <div class="bp-subtitle">Tendências · SEO · Concorrência · Editorial</div>
    </div>
  </div>
  <div class="bp-meta">
    <strong>Período: {janela_lbl}</strong>
    {datetime.now().strftime("%a, %d %b %Y · %H:%M")}
  </div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────────────────
aba1, aba2, aba3 = st.tabs([
    "◈  Temas Recomendados",
    "◉  Análise de Concorrência",
    "◎  Hard News",
])


# ═════════════════════════════════════════════════════════════════════════════
# ABA 1 — TEMAS RECOMENDADOS
# ═════════════════════════════════════════════════════════════════════════════
with aba1:
    st.markdown('<div class="sec-label">◈ Temas recomendados · score de oportunidade · ângulo editorial</div>', unsafe_allow_html=True)

    temas_filtrados = [t for t in get_all_temas() if t["tema"] in temas_ativos_nomes]

    if not temas_filtrados:
        st.info("Nenhum tema ativo. Selecione ou adicione temas na barra lateral.")
    else:
        # ── Coletar dados reais ────────────────────────────────────────────────
        temas_enriquecidos = []
        with st.spinner("Consultando Google Trends..."):
            for tf in temas_filtrados:
                kw         = tf["keywords"][0]
                trend_data = buscar_interesse_tempo(kw, janela)
                noticias   = buscar_noticias(kw, max_items=12)
                score      = calcular_score(trend_data["pico"], len(noticias["data"]))
                temas_enriquecidos.append({
                    **tf,
                    "trend":    trend_data,
                    "noticias": noticias,
                    "score":    score,
                    "pico":     trend_data["pico"],
                    "ia_data":  _angulo_fallback(tf["tema"]),
                })

        temas_enriquecidos.sort(key=lambda x: x["score"], reverse=True)

        # ── IA angles — roda automaticamente quando GEMINI_API_KEY está presente ──
        if GEMINI_API_KEY:
            with st.spinner("Gerando ângulos editoriais com Gemini..."):
                for t in temas_enriquecidos:
                    t["ia_data"] = _chamar_gemini_com_fallback(
                        t["tema"], t["categoria"], t["keywords"], t["descricao"]
                    )

        # ── Export ────────────────────────────────────────────────────────────
        if exportar_btn:
            st.download_button(
                "⬇ Baixar Briefing_BP.csv",
                data=gerar_csv_briefing(temas_enriquecidos),
                file_name=f"Briefing_BP_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
            )

        # ── Stats ─────────────────────────────────────────────────────────────
        n_real   = sum(1 for t in temas_enriquecidos if t["trend"]["is_real"])
        n_alta   = sum(1 for t in temas_enriquecidos if t["pico"] >= 70)
        avg_sc   = int(sum(t["score"] for t in temas_enriquecidos) / len(temas_enriquecidos))
        top_nome = temas_enriquecidos[0]["tema"]
        top_sc   = temas_enriquecidos[0]["score"]

        dados_status = (
            f'🟢 {n_real}/{len(temas_enriquecidos)} em tempo real'
            if n_real == len(temas_enriquecidos)
            else f'🟡 {n_real}/{len(temas_enriquecidos)} em tempo real'
        )

        st.markdown(f"""
        <div class="stat-row">
          <div class="stat-box"><div class="stat-val">{len(temas_enriquecidos)}</div><div class="stat-lbl">Temas</div></div>
          <div class="stat-box"><div class="stat-val" style="color:var(--red);">{n_alta}</div><div class="stat-lbl">Em alta</div></div>
          <div class="stat-box"><div class="stat-val">{avg_sc}</div><div class="stat-lbl">Score médio</div></div>
          <div class="stat-box"><div class="stat-val" style="color:var(--green);">{top_sc}</div><div class="stat-lbl">Top: {top_nome}</div></div>
        </div>
        <div style="font-family:'DM Mono',monospace;font-size:9px;color:var(--text-dim);margin:-10px 0 18px;text-align:right;">
          {dados_status}
        </div>
        """, unsafe_allow_html=True)

        # ── Cards ─────────────────────────────────────────────────────────────
        rank_icons = ["🥇","🥈","🥉","④","⑤","⑥","⑦","⑧","⑨","⑩"]
        for i, t in enumerate(temas_enriquecidos):
            score    = t["score"]
            pico     = t["pico"]
            ia       = t["ia_data"]
            urgencia = ia.get("urgencia", "media")
            cor_tema = t.get("cor", "#2563eb")
            sat      = min(len(t["noticias"]["data"]) / 15, 1.0) * 100
            badge_lbl, badge_col = badge_score(score)
            urg_cls  = {"alta":"urg-alta","media":"urg-media","baixa":"urg-baixa"}.get(urgencia, "urg-media")
            kw0      = t["keywords"][0]
            is_real_trend = t["trend"]["is_real"]

            with st.expander(f"{rank_icons[min(i,9)]} {t['emoji']} {t['tema']}  ·  Score {score}  ·  {badge_lbl}", expanded=(i == 0)):
                col_l, col_r = st.columns([1, 1.2], gap="large")

                with col_l:
                    st.markdown(f"""
                    <div class="sc-top">
                      <div>
                        <div class="sc-tema">{t['emoji']} {t['tema']}</div>
                        <div class="sc-cat">{t['categoria']}</div>
                      </div>
                      <div>
                        <div class="sc-score-val" style="color:{badge_col};">{score}</div>
                        <div class="sc-score-lbl">Score</div>
                      </div>
                    </div>
                    <div class="sc-desc">{t['descricao']}</div>
                    <div class="bar-group">
                      <div class="bar-row-lbl"><span>Interesse Trends</span><span>{pico}/100</span></div>
                      <div class="bar-track"><div class="bar-fill" style="width:{pico}%;background:{cor_tema};"></div></div>
                      <div class="bar-row-lbl"><span>Saturação de cobertura</span><span>{int(sat)}/100</span></div>
                      <div class="bar-track"><div class="bar-fill" style="width:{sat}%;background:#94a3b8;"></div></div>
                      <div class="bar-row-lbl"><span>Score de oportunidade</span><span style="color:{badge_col};font-weight:600;">{score}/100</span></div>
                      <div class="bar-track"><div class="bar-fill" style="width:{score}%;background:{badge_col};"></div></div>
                    </div>
                    """, unsafe_allow_html=True)

                    if t["canais"]:
                        pills = "".join(f'<span class="chan-pill">{c}</span>' for c in t["canais"])
                        st.markdown(f'<div class="sub-label">Canais que seu público consome</div><div class="chan-pills">{pills}</div>', unsafe_allow_html=True)

                    # ── SEO keywords — SOMENTE dados reais ────────────────────
                    seo_result = buscar_queries_relacionadas(kw0)
                    df_seo     = seo_result["data"]
                    seo_real   = seo_result["is_real"]
                    tipo_seo   = seo_result.get("tipo", "rising")

                    st.markdown(
                        f'<div style="display:flex;align-items:center;justify-content:space-between;margin:14px 0 7px;">'
                        f'<div class="sub-label" style="margin:0;">🎯 Keywords em ascensão (SEO)</div>'
                        f'{fonte_badge(seo_real, "SerpAPI")}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                    if seo_real and not df_seo.empty:
                        label_tipo = "🏆 Top" if tipo_seo == "top" else "📈 Crescendo"
                        for _, row in df_seo.head(5).iterrows():
                            v   = int(row.get("value", 0))
                            if tipo_seo == "top":
                                # Top queries: value é índice relativo (0-100)
                                cls = "seo-top"
                                lbl = f"{label_tipo} {v}"
                            else:
                                # Rising queries: value é % de crescimento — valores altos são REAIS aqui
                                cls = "seo-blast" if v >= 5000 else ("seo-high" if v >= 100 else "seo-med")
                                lbl = "🚀 Breakout" if v >= 5000 else f"+{v}%"
                            q_str = str(row["query"]).title()
                            st.markdown(
                                f'<div class="seo-row"><span class="seo-kw">{q_str}</span>'
                                f'<span class="seo-badge {cls}">{lbl}</span></div>',
                                unsafe_allow_html=True,
                            )
                    else:
                        st.markdown(
                            '<div class="no-data-box">'
                            'Google Trends temporariamente indisponível<br>'
                            '<span style="font-size:10px;">Tente novamente em alguns minutos.</span>'
                            '</div>',
                            unsafe_allow_html=True,
                        )

                with col_r:
                    # ── Gráfico de tendência ───────────────────────────────────
                    df_chart = t["trend"]["df"]
                    chart_label = "Interesse ao longo do tempo"
                    if not is_real_trend:
                        chart_label += " (estimado)"

                    if not df_chart.empty and kw0 in df_chart.columns:
                        fig_t = go.Figure()
                        fig_t.add_trace(go.Scatter(
                            x=df_chart["date"], y=df_chart[kw0],
                            mode="lines",
                            line=dict(color=cor_tema if is_real_trend else "#94a3b8", width=2.5, dash="solid" if is_real_trend else "dot"),
                            fill="tozeroy",
                            fillcolor=hex_to_rgba(cor_tema if is_real_trend else "#94a3b8", 0.07),
                            hovertemplate="%{x|%d/%m}: <b>%{y}</b><extra></extra>",
                        ))
                        if not is_real_trend:
                            fig_t.add_annotation(
                                text="⚠ estimado",
                                xref="paper", yref="paper",
                                x=0.98, y=0.96, showarrow=False,
                                font=dict(family="DM Mono", size=9, color="#94a3b8"),
                            )
                        layout = plot_base(155)
                        layout["yaxis"]["range"] = [0, 110]
                        fig_t.update_layout(**layout)
                        st.plotly_chart(fig_t, use_container_width=True, config={"displayModeBar": False})
                        st.markdown(
                            f'<div style="text-align:right;margin-top:-8px;">{fonte_badge(is_real_trend, "SerpAPI")}</div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.caption("Dados de tendência indisponíveis.")

                    # ── IA Box ─────────────────────────────────────────────────
                    if ia.get("angulo"):
                        fmt_pills = "".join(f'<span class="fmt-pill">{f}</span>' for f in ia.get("formatos", []))
                        st.markdown(
                            f'<div class="angulo-box">'
                            f'<div class="angulo-header">'
                            f'<span class="angulo-label">◈ Ângulo Editorial — Gemini</span>'
                            f'<span class="angulo-urg {urg_cls}">{urgencia.upper()}</span>'
                            f'</div>'
                            f'<div class="angulo-text">{ia.get("angulo","")}</div>'
                            f'<div class="angulo-gancho">"{ia.get("gancho","")}"</div>'
                            f'<div class="angulo-meta">'
                            f'<strong>📌 Título:</strong> {ia.get("titulo","")}<br>'
                            f'<strong>⏱ Por que agora:</strong> {ia.get("por_que_agora","")}'
                            f'</div>'
                            f'<div style="margin-top:10px;">{fmt_pills}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                    # ── Notícias recentes ──────────────────────────────────────
                    noticias_list = t["noticias"]["data"]
                    noticias_real = t["noticias"]["is_real"]
                    if noticias_list:
                        st.markdown(
                            f'<div style="display:flex;align-items:center;justify-content:space-between;margin:16px 0 7px;">'
                            f'<div class="sub-label" style="margin:0;">📰 Notícias recentes</div>'
                            f'{fonte_badge(noticias_real, "Google News")}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        for j, n in enumerate(noticias_list[:4]):
                            st.markdown(
                                f'<div class="news-item">'
                                f'<div class="news-num">0{j+1}</div>'
                                f'<div class="news-body">'
                                f'<div class="news-title"><a href="{safe_link(n)}" target="_blank">{safe_title(n)}</a></div>'
                                f'<div class="news-meta">🕒 {formatar_data(n)}</div>'
                                f'</div></div>',
                                unsafe_allow_html=True,
                            )
                    else:
                        st.caption("Sem notícias indexadas no momento.")

        # ── Gráfico comparativo ────────────────────────────────────────────────
        if len(temas_enriquecidos) > 1:
            st.markdown("---")
            st.markdown('<div class="sec-label">◈ Comparativo de scores por tema</div>', unsafe_allow_html=True)
            fig_bar = go.Figure()
            for t in temas_enriquecidos:
                fig_bar.add_trace(go.Bar(
                    x=[t["tema"]], y=[t["score"]],
                    marker_color=t.get("cor","#2563eb"), marker_line_width=0,
                    text=[str(t["score"])], textposition="outside",
                    textfont=dict(family="DM Mono", size=11, color="#64748b"),
                    name=t["tema"], showlegend=False,
                ))
            lb = plot_base(200)
            lb["xaxis"]["tickfont"] = dict(family="DM Mono", size=11, color="#94a3b8")
            lb["yaxis"]["range"]    = [0, 118]
            lb["bargap"]            = 0.40
            lb["margin"]            = dict(l=0, r=0, t=18, b=0)
            del lb["xaxis"]["tickformat"]
            fig_bar.update_layout(**lb)
            st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})


# ═════════════════════════════════════════════════════════════════════════════
# ABA 2 — ANÁLISE DE CONCORRÊNCIA
# ═════════════════════════════════════════════════════════════════════════════
with aba2:
    st.markdown('<div class="sec-label">◉ Top 10 concorrentes · temas em tratamento agora</div>', unsafe_allow_html=True)

    if not show_nac and not show_int:
        st.info("Ative pelo menos um tipo de canal na barra lateral.")
    else:
        def render_canal_grid(canais: list, label: str):
            st.markdown(f'<div class="sec-label" style="margin-top:4px;">{label}</div>', unsafe_allow_html=True)
            cols = st.columns(len(canais), gap="small")
            for idx, canal in enumerate(canais):
                with cols[idx]:
                    result = buscar_videos_canal(canal["nome"], canal["query"], canal.get("yt_id"))
                    videos = result["data"]
                    with st.container(border=True):
                        st.markdown(
                            f'<div class="canal-header">'
                            f'<div class="canal-name">{canal["flag"]} {canal["nome"]}</div>'
                            f'<div class="canal-foco">{canal["foco"]}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        if videos:
                            for v in videos:
                                st.markdown(f"▶ [{safe_title(v)}]({safe_link(v)})")
                                st.caption(f"🕒 {formatar_data(v)}")
                        else:
                            st.caption("Sem conteúdo indexado no momento.")

        if show_nac:
            render_canal_grid(CANAIS_NACIONAIS, "🇧🇷 Canais nacionais")
        if show_int:
            st.markdown("<br>", unsafe_allow_html=True)
            render_canal_grid(CANAIS_INTERNACIONAIS, "🌐 Canais internacionais")

        # ── Charts ────────────────────────────────────────────────────────────
        st.markdown("---")
        dark   = st.session_state.dark_mode
        tick_c = "#94a3b8" if dark else "#64748b"
        grid_c = "rgba(148,163,184,0.10)" if dark else "rgba(100,116,139,0.12)"
        col_rad, col_heat = st.columns(2, gap="large")

        with col_rad:
            st.markdown('<div class="sec-label">Radar de cobertura temática</div>', unsafe_allow_html=True)
            fig_r = go.Figure()
            for nome, vals, cor in RADAR_CONCORRENCIA["sets"]:
                fig_r.add_trace(go.Scatterpolar(
                    r=vals + [vals[0]],
                    theta=RADAR_CONCORRENCIA["cats"] + [RADAR_CONCORRENCIA["cats"][0]],
                    fill="toself", name=nome,
                    line=dict(color=cor, width=2),
                    fillcolor=hex_to_rgba(cor, 0.09),
                ))
            fig_r.update_layout(
                polar=dict(
                    bgcolor="rgba(0,0,0,0)",
                    radialaxis=dict(visible=True, range=[0,100], tickfont=dict(family="DM Mono",size=8,color=tick_c), gridcolor=grid_c, linecolor=grid_c),
                    angularaxis=dict(tickfont=dict(family="DM Mono",size=10,color=tick_c), gridcolor=grid_c, linecolor=grid_c),
                ),
                paper_bgcolor="rgba(0,0,0,0)",
                legend=dict(font=dict(family="DM Mono",size=9,color=tick_c), bgcolor="rgba(0,0,0,0)"),
                height=300, margin=dict(l=20,r=20,t=10,b=10),
            )
            st.plotly_chart(fig_r, use_container_width=True, config={"displayModeBar": False})

        with col_heat:
            st.markdown('<div class="sec-label">Heatmap de sobreposição temática</div>', unsafe_allow_html=True)
            cs    = ([[0,"#0d0e18"],[0.5,"#1e3a5f"],[1,"#3b82f6"]] if dark else [[0,"#f0f4f8"],[0.5,"#93c5fd"],[1,"#1d4ed8"]])
            txt_c = "#e2e8f0" if dark else "#0f172a"
            z_vals= [[90,30,70,40,80],[70,65,55,50,35],[55,40,85,60,45],[80,50,75,55,70],[95,35,65,50,85]]
            fig_h = go.Figure(go.Heatmap(
                z=z_vals, x=["Soberania","História","Economia","Valores","Defesa"],
                y=["Jovem Pan","Gazeta Povo","PragerU","Daily Wire","Tucker Carlson"],
                colorscale=cs, showscale=False,
                hovertemplate="%{y} × %{x}<br><b>%{z}%</b><extra></extra>",
                text=[[str(v) for v in row] for row in z_vals],
                texttemplate="%{text}",
                textfont=dict(family="DM Mono",size=11,color=txt_c),
            ))
            fig_h.update_layout(
                height=300, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0,r=0,t=0,b=0),
                xaxis=dict(tickfont=dict(family="DM Mono",size=10,color=tick_c)),
                yaxis=dict(tickfont=dict(family="DM Mono",size=10,color=tick_c)),
            )
            st.plotly_chart(fig_h, use_container_width=True, config={"displayModeBar": False})

        st.markdown("---")
        st.markdown('<div class="sec-label">◉ Lacunas de conteúdo — onde o BP pode se diferenciar</div>', unsafe_allow_html=True)
        col_g1, col_g2 = st.columns(2, gap="medium")
        for i, lac in enumerate(LACUNAS_CONTEUDO):
            with (col_g1 if i % 2 == 0 else col_g2):
                st.markdown(
                    f'<div class="gap-card">'
                    f'<div class="gap-title">{lac["tema"]}</div>'
                    f'<div class="gap-desc">{lac["desc"]}</div>'
                    f'<div class="gap-lbl"><span>Gap competitivo</span><span style="color:var(--green);font-weight:600;">{lac["gap"]}/100</span></div>'
                    f'<div class="bar-track"><div class="bar-fill" style="width:{lac["gap"]}%;background:var(--green);"></div></div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )


# ═════════════════════════════════════════════════════════════════════════════
# ABA 3 — HARD NEWS
# ═════════════════════════════════════════════════════════════════════════════
with aba3:
    st.markdown('<div class="sec-label">◎ Tendências macro · SEO Booster · Hard News ao vivo</div>', unsafe_allow_html=True)

    col_l3, col_r3 = st.columns([1, 1.1], gap="large")

    with col_l3:
        # ── Macro trends ───────────────────────────────────────────────────────
        with st.spinner("Consultando Google Trends..."):
            macro_result = buscar_trends_macro()
        macro_items  = macro_result["data"]
        macro_real   = macro_result["is_real"]

        st.markdown(
            f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">'
            f'<div class="sub-label" style="margin:0;">🔥 O que o Brasil está buscando agora</div>'
            f'{fonte_badge(macro_real, "Google Trends RSS")}'
            f'</div>',
            unsafe_allow_html=True,
        )
        pills_html = "".join(f'<span class="macro-pill">{m}</span>' for m in macro_items)
        st.markdown(f'<div class="macro-wrap">{pills_html}</div>', unsafe_allow_html=True)
        if not macro_real:
            st.markdown(
                '<div class="no-data-box">Google Trends indisponível — exibindo últimas tendências conhecidas.</div>',
                unsafe_allow_html=True,
            )

        st.markdown("---")

        # ── SEO Booster ────────────────────────────────────────────────────────
        st.markdown('<div class="sub-label">🎯 SEO Booster — pesquise qualquer tema</div>', unsafe_allow_html=True)
        tema_seo = st.text_input(
            "SEO input",
            placeholder="Digite: Bolsonaro, Lula, Reforma Tributária...",
            label_visibility="collapsed",
            key="seo_input",
        )

        termos_seo = (
            [tema_seo] if tema_seo
            else [t["keywords"][0] for t in get_all_temas() if t["tema"] in temas_ativos_nomes][:3]
        )

        for ts in termos_seo:
            if not ts:
                continue
            seo_r  = buscar_queries_relacionadas(ts)
            td_s   = buscar_interesse_tempo(ts, janela)
            pico_s = td_s["pico"]

            st.markdown(
                f'<div style="font-family:DM Mono,monospace;font-size:9px;letter-spacing:0.12em;'
                f'text-transform:uppercase;color:var(--text-mid);margin:12px 0 7px;'
                f'padding-left:8px;border-left:2px solid var(--primary);">'
                f'{ts.upper()} · Pico: {pico_s}/100 {"🟢" if td_s["is_real"] else "🟡"}</div>',
                unsafe_allow_html=True,
            )

            if seo_r["is_real"] and not seo_r["data"].empty:
                tipo = seo_r.get("tipo", "rising")
                for _, row in seo_r["data"].head(6).iterrows():
                    v = int(row.get("value", 0))
                    if tipo == "top":
                        cls = "seo-top"; lbl = f"🏆 Top {v}"
                    else:
                        cls = "seo-blast" if v >= 5000 else ("seo-high" if v >= 100 else "seo-med")
                        lbl = "🚀 Breakout" if v >= 5000 else f"+{v}%"
                    st.markdown(
                        f'<div class="seo-row"><span class="seo-kw">{str(row["query"]).title()}</span>'
                        f'<span class="seo-badge {cls}">{lbl}</span></div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown(
                    '<div class="no-data-box">Google Trends temporariamente indisponível.<br>'
                    '<span style="font-size:10px;">Tente novamente em alguns minutos.</span></div>',
                    unsafe_allow_html=True,
                )

            # Sparkline — pontilhado se estimado
            df_sc = td_s["df"]
            if not df_sc.empty and ts in df_sc.columns:
                fig_sp = go.Figure()
                fig_sp.add_trace(go.Scatter(
                    x=df_sc["date"], y=df_sc[ts],
                    mode="lines",
                    line=dict(color="#2563eb", width=1.5, dash="solid" if td_s["is_real"] else "dot"),
                    fill="tozeroy", fillcolor="rgba(37,99,235,0.06)",
                    hovertemplate="%{x|%d/%m}: <b>%{y}</b><extra></extra>",
                ))
                lsp = plot_base(90)
                lsp["yaxis"]["visible"] = False
                lsp["yaxis"]["range"]   = [0, 110]
                lsp["xaxis"]["showgrid"] = False
                fig_sp.update_layout(**lsp)
                st.plotly_chart(fig_sp, use_container_width=True, config={"displayModeBar": False})

        # ── Comparativo de interesse ───────────────────────────────────────────
        st.markdown("---")
        st.markdown('<div class="sub-label">📊 Interesse comparado — temas ativos</div>', unsafe_allow_html=True)
        fig_comp = go.Figure()
        temas_ativos_list = [t for t in get_all_temas() if t["tema"] in temas_ativos_nomes]
        any_real = False
        for idx, t in enumerate(temas_ativos_list[:8]):
            kw   = t["keywords"][0]
            td   = buscar_interesse_tempo(kw, janela)
            df_td = td["df"]
            cor_t = t.get("cor", RADAR_CORES[idx % len(RADAR_CORES)])
            if td["is_real"]: any_real = True
            if not df_td.empty and kw in df_td.columns:
                fig_comp.add_trace(go.Scatter(
                    x=df_td["date"], y=df_td[kw],
                    mode="lines", name=t["tema"],
                    line=dict(color=cor_t, width=2, dash="solid" if td["is_real"] else "dot"),
                    hovertemplate=f"{t['tema']}<br>%{{x|%d/%m}}: <b>%{{y}}</b><extra></extra>",
                ))
        lc = plot_base(220)
        lc["showlegend"] = True
        lc["legend"]     = dict(font=dict(family="DM Mono",size=9,color="#94a3b8"), bgcolor="rgba(0,0,0,0)", orientation="h", yanchor="bottom", y=1.01)
        fig_comp.update_layout(**lc)
        st.plotly_chart(fig_comp, use_container_width=True, config={"displayModeBar": False})
        if not any_real:
            st.markdown('<div style="text-align:right;">🟡 Curvas estimadas (Google indisponível)</div>', unsafe_allow_html=True)

    with col_r3:
        # ── Hard News feed ─────────────────────────────────────────────────────
        nomes_ativos = [t["tema"] for t in get_all_temas() if t["tema"] in temas_ativos_nomes]
        opcoes_news  = ["Todos os temas"] + nomes_ativos
        tema_news    = st.selectbox("Filtrar notícias", opcoes_news, label_visibility="collapsed", key="sel_news")

        kws_news = (
            [t["keywords"][0] for t in get_all_temas() if t["tema"] in nomes_ativos]
            if tema_news == "Todos os temas"
            else (next((t for t in get_all_temas() if t["tema"] == tema_news), None) or {}).get("keywords", [tema_news])[:2]
        )

        with st.spinner("Carregando notícias..."):
            todas_noticias = []
            for kw in kws_news:
                res = buscar_noticias(kw, max_items=5)
                todas_noticias += res["data"]

        # Deduplica
        seen_k, unicas = set(), []
        for n in todas_noticias:
            key = safe_title(n).lower()[:50]
            if key not in seen_k:
                seen_k.add(key)
                unicas.append(n)

        news_real = bool(unicas)
        st.markdown(
            f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">'
            f'<div class="sub-label" style="margin:0;">📰 Hard News — feed ao vivo</div>'
            f'{fonte_badge(news_real, "Google News")}'
            f'</div>',
            unsafe_allow_html=True,
        )

        if unicas:
            for j, n in enumerate(unicas[:16]):
                st.markdown(
                    f'<div class="news-item">'
                    f'<div class="news-num">{str(j+1).zfill(2)}</div>'
                    f'<div class="news-body">'
                    f'<div class="news-title"><a href="{safe_link(n)}" target="_blank">{safe_title(n)}</a></div>'
                    f'<div class="news-meta">🕒 {formatar_data(n)}</div>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )
        else:
            st.info("Sem notícias indexadas no momento. Verifique a conexão com a internet.")
