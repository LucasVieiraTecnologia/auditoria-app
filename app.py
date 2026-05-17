# -*- coding: utf-8 -*-
# Auditoria Inteligente de Condomínios — Streamlit App
from __future__ import annotations

import io
import html
import json
import os
import re
import hashlib
import shutil
import traceback
import base64
import bcrypt
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from datetime import datetime, timedelta

from dotenv import load_dotenv
load_dotenv()

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, timedelta

import rodar_auditoria_script as runner

# ==========================================
# AUTENTICAÇÃO
# ==========================================
import logs_acesso

st.set_page_config(page_title='Auditoria Inteligente de Condomínios', page_icon='🏢', layout='wide', initial_sidebar_state='collapsed')

def hash_password(password: str) -> str:
    # Generate salt and hash password using bcrypt
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode(), salt)
    return hashed.decode('utf-8')

def _get_credential(key):
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, '')

def _build_base_users():
    """Constrói dicionário de usuários a partir de st.secrets / variáveis de ambiente"""
    user_env = _get_credential('APP_USERNAME')
    pass_env = _get_credential('APP_PASSWORD')
    users_str = _get_credential('APP_USERS')

    users = {}
    if user_env and pass_env:
        users[user_env] = {
            'password_hash': hash_password(pass_env),
            'role': 'admin',
            'created_at': datetime.now().isoformat(),
            'last_login': None,
            'last_seen': None
        }

    if users_str:
        for pair in users_str.split(','):
            if ':' in pair:
                u, p = pair.split(':', 1)
                users[u.strip()] = {
                    'password_hash': hash_password(p.strip()),
                    'role': 'viewer',
                    'created_at': datetime.now().isoformat(),
                    'last_login': None,
                    'last_seen': None
                }

    return users

def get_users():
    """Retorna dicionário de usuários (username -> password_hash)"""
    all_users = get_all_users()
    return {u: info.get('password_hash', '') for u, info in all_users.items()}

def get_all_users():
    """Retorna dicionário completo de usuários.
    Sempre mescla usuários de st.secrets/env vars com os do users.json.
    Isso garante que usuários criados via UI sobrevivam a redeploys."""
    users_file = Path('users.json')
    base = _build_base_users()

    # Carrega usuários existentes do disco (preserva last_login, last_seen)
    disk_users = {}
    if users_file.exists():
        try:
            with open(users_file, 'r', encoding='utf-8') as f:
                disk_users = json.load(f).get('users', {})
        except Exception:
            pass

    # Mescla: secrets/env vars têm prioridade (atualiza hash), mas preserva metadados do disco
    merged = {}
    for username in set(list(base.keys()) + list(disk_users.keys())):
        if username in base:
            entry = base[username].copy()
            if username in disk_users:
                entry['last_login'] = disk_users[username].get('last_login', entry.get('last_login'))
                entry['last_seen'] = disk_users[username].get('last_seen', entry.get('last_seen'))
                entry['created_at'] = disk_users[username].get('created_at', entry.get('created_at'))
            merged[username] = entry
        else:
            merged[username] = disk_users[username].copy()

    save_all_users_to_file(merged)
    return merged

def save_all_users_to_file(users_dict):
    """Salva todos os dados dos usuários no arquivo users.json"""
    users_file = Path('users.json')
    
    # Save to file
    data = {
        'users': users_dict
    }
    
    with open(users_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def update_user_last_seen(username):
    """Atualiza o timestamp de última visualização do usuário"""
    users = get_all_users()
    if username in users:
        users[username]['last_seen'] = datetime.now().isoformat()
        save_all_users_to_file(users)

def is_user_online(username, minutes=5):
    """Verifica se o usuário está online (ativo nos últimos X minutos)"""
    users = get_all_users()
    if username not in users or not users[username].get('last_seen'):
        return False
    
    last_seen = datetime.fromisoformat(users[username]['last_seen'])
    return (datetime.now() - last_seen).total_seconds() < (minutes * 60)

def check_credentials(username: str, password: str) -> bool:
    users = get_users()
    if username in users:
        hashed_password = users[username]
        # Check if the hashed_password is a bcrypt hash (starts with $2b$)
        if hashed_password.startswith('$2b$'):
            # Verify using bcrypt
            return bcrypt.checkpw(password.encode(), hashed_password.encode('utf-8'))
        else:
            # Fallback for old SHA256 hashes (if any)
            return hashed_password == hash_password(password)
    return False

def init_auth():
    if 'authenticated' not in st.session_state:
        st.session_state['authenticated'] = False
        st.session_state['username'] = ''
        st.session_state['user_role'] = 'viewer'

def login_screen():
    st.markdown("""
    <style>
    .block-container {
        max-width: 500px !important;
        padding-top: 2.5rem !important;
    }
    .login-logo {
        text-align: center;
        font-size: 3.5rem;
        margin-bottom: 0;
    }
    .login-title {
        text-align: center;
        color: var(--text-color);
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        margin-bottom: 0.25rem;
    }
    .login-sub {
        text-align: center;
        color: var(--text-color);
        font-size: 0.9rem;
        margin-bottom: 1.5rem;
        opacity: 0.6;
    }
    .stForm {
        background: var(--secondary-background-color);
        padding: 2.5rem 2rem;
        border-radius: 24px;
        box-shadow: 0 8px 30px rgba(0,0,0,0.1);
        border: 1px solid rgba(128,128,128,0.12);
    }
    .stTextInput {
        margin-bottom: 0.5rem;
    }
    .stTextInput input {
        border-radius: 12px !important;
        border: 2px solid rgba(128,128,128,0.2) !important;
        padding: 14px 16px !important;
        font-size: 15px !important;
        background: var(--background-color) !important;
        color: var(--text-color) !important;
        transition: all 0.2s ease !important;
    }
    .stTextInput input:focus {
        border-color: var(--primary-color) !important;
        box-shadow: 0 0 0 4px color-mix(in srgb, var(--primary-color) 15%, transparent) !important;
    }
    .stButton button {
        width: 100%;
        border-radius: 12px;
        background: linear-gradient(135deg, var(--primary-color), color-mix(in srgb, var(--primary-color) 80%, #000));
        color: white;
        font-weight: 700;
        font-size: 16px;
        padding: 14px;
        border: none;
        transition: all 0.2s ease;
        margin-top: 0.75rem;
    }
    .stButton button:hover {
        filter: brightness(1.1);
        transform: translateY(-1px);
        box-shadow: 0 8px 20px color-mix(in srgb, var(--primary-color) 40%, transparent);
    }
    .stButton button:active {
        transform: translateY(0);
    }
    @media (max-width: 768px) {
        .block-container { max-width: 100% !important; padding: 1rem !important; }
        .stForm { padding: 1.5rem !important; }
        .login-title { font-size: 1.5rem !important; }
        .login-logo { font-size: 2.5rem !important; }
    }
    </style>
    """, unsafe_allow_html=True)
    
    users_check = get_all_users()
    if not users_check:
        st.error('Nenhum usuário configurado. Defina APP_USERNAME e APP_PASSWORD nas variáveis de ambiente ou secrets do Streamlit.')
        st.stop()
    
    st.markdown('<div class="login-logo">🏢</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-title">Condomínio Candelária</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-sub">Sistema de gestão condominial avançado</div>', unsafe_allow_html=True)
    
    with st.form('login_form'):
        username = st.text_input('Usuário', placeholder='Digite seu usuário')
        password = st.text_input('Senha', type='password', placeholder='Digite sua senha')
        submitted = st.form_submit_button('Entrar', use_container_width=True)
        
        if submitted:
            if check_credentials(username, password):
                st.session_state['authenticated'] = True
                st.session_state['username'] = username
                
                users = get_all_users()
                if username in users:
                    st.session_state['user_role'] = users[username].get('role', 'viewer')
                    users[username]['last_login'] = datetime.now().isoformat()
                    users[username]['last_seen'] = datetime.now().isoformat()
                    save_all_users_to_file(users)
                
                logs_acesso.log_acesso(username, 'LOGIN', detalhes='Login realizado com sucesso')
                st.rerun()
            else:
                st.error('Usuário ou senha inválidos')
                logs_acesso.log_acesso(username or 'desconhecido', 'LOGIN_FALHOU', detalhes='Tentativa de login falhou')
    
    st.stop()

init_auth()

# Update last seen timestamp for authenticated users
if st.session_state.get('authenticated', False):
    username = st.session_state.get('username', '')
    if username:
        update_user_last_seen(username)

if not st.session_state['authenticated']:
    login_screen()

BASE_DIR = Path('.')
PASTA_PDFS = BASE_DIR / 'ArquivosPDF'
PASTA_PDFS.mkdir(exist_ok=True)
ARQUIVO_EXCEL = BASE_DIR / 'auditoria_condominio.xlsx'
ARQUIVO_CSV_BALANCO = BASE_DIR / 'auditoria_balanco_mensal.csv'
ARQUIVO_CSV_CATEGORIAS = BASE_DIR / 'auditoria_categorias_mensais.csv'
ARQUIVO_CSV_MOVIMENTACOES = BASE_DIR / 'auditoria_movimentacoes.csv'
ARQUIVO_CSV_COBRANCAS = BASE_DIR / 'auditoria_composicao_cobrancas.csv'
ARQUIVOS_DOWNLOAD = [ARQUIVO_EXCEL, ARQUIVO_CSV_BALANCO, ARQUIVO_CSV_CATEGORIAS, ARQUIVO_CSV_MOVIMENTACOES, ARQUIVO_CSV_COBRANCAS]
DASHBOARDS_HTML = [
    ('Balanço do Mês', BASE_DIR / 'dashboard_balanco_mensal.html'),
    ('Evolução dos Saldos', BASE_DIR / 'dashboard_saldos.html'),
    ('Categorias (Geral)', BASE_DIR / 'dashboard_categorias_entrada_saida.html'),
    ('Categorias Mensais', BASE_DIR / 'dashboard_categorias_por_mes.html'),
    ('Movimentação Analítica', BASE_DIR / 'dashboard_movimentacao_por_conta.html'),
    ('Maiores Fornecedores', BASE_DIR / 'dashboard_top_fornecedores_saida.html'),
    ('Notas Fiscais', BASE_DIR / 'dashboard_notas_fiscais.html'),
]

COR_ENTRADA = '#16a34a'
COR_SAIDA = '#dc2626'
COR_TRANSFERENCIA = '#d97706'
COR_PRIMARIA = '#2563eb'
COR_CIANO = '#0891b2'
SCORE_COL = 'Score_Suspeita'
MOTIVO_COL = 'Motivo_Suspeita'
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'openai/gpt-4o-mini')
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', 'https://openrouter.ai/api/v1').rstrip('/')
if not os.getenv('OPENAI_API_KEY') and os.getenv('OPENROUTER_API_KEY'):
    os.environ['OPENAI_API_KEY'] = os.getenv('OPENROUTER_API_KEY')
COLUNAS_EXIBICAO = {
    SCORE_COL: 'Score_Divergencia',
    MOTIVO_COL: 'Motivo_Divergencia',
}
PLOTLY_LAYOUT = dict(
    template='plotly_white',
    paper_bgcolor='rgba(255,255,255,0)',
    plot_bgcolor='rgba(248,250,252,0.72)',
    font=dict(family='Inter, Segoe UI, Arial, sans-serif', color='#0f172a'),
    margin=dict(l=24, r=18, t=34, b=24),
    hoverlabel=dict(bgcolor='#0f172a', font_color='#f8fafc', bordercolor='#1e293b'),
    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
)

st.markdown('''
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root {--navy:#0f172a; --muted:#64748b; --line:#e2e8f0; --card:#ffffff; --soft:#f8fafc; --blue:#2563eb;}
html, body, [class*="css"] {font-family: 'Inter', 'Segoe UI', sans-serif;}
.stApp {background: radial-gradient(circle at top left, #dbeafe 0, transparent 32rem), linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%);}
.block-container {max-width: 1600px; padding-top: 1rem; padding-bottom: 2.5rem;}
.hero {position:relative; overflow:hidden; background:linear-gradient(135deg,#020617 0%,#0f172a 42%,#1d4ed8 100%); border:1px solid rgba(255,255,255,.12); border-radius:28px; padding:30px 32px 24px; color:#f8fafc; box-shadow:0 24px 70px rgba(15,23,42,.28); margin-bottom:1rem;}
.hero:before {content:''; position:absolute; width:320px; height:320px; right:-90px; top:-110px; background:radial-gradient(circle,rgba(125,211,252,.28),transparent 67%);}
.hero-badge {display:inline-flex; align-items:center; gap:.45rem; padding:.34rem .78rem; border-radius:999px; background:rgba(255,255,255,.12); color:#bfdbfe; border:1px solid rgba(255,255,255,.15); font-size:.78rem; font-weight:800; letter-spacing:.06em; text-transform:uppercase; margin-bottom:.9rem;}
.hero-title {font-size:clamp(1.8rem,3vw,2.55rem); font-weight:800; margin-bottom:8px; letter-spacing:-.035em;}
.hero-sub {font-size:1rem; color:#cbd5e1; max-width:780px; line-height:1.55;}
.hero-stats {display:grid; grid-template-columns:repeat(4,minmax(120px,1fr)); gap:14px; margin-top:22px;}
.hero-stat {background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.1); border-radius:16px; padding:13px 15px; backdrop-filter:blur(12px);}
.hero-stat-val {font-size:1.2rem; font-weight:800; color:#f8fafc; letter-spacing:-.02em;}
.hero-stat-lbl {font-size:.72rem; color:#93c5fd; text-transform:uppercase; letter-spacing:.08em; margin-top:3px;}
.kpi-card {position:relative; overflow:hidden; background:rgba(255,255,255,.92); border:1px solid rgba(148,163,184,.28); border-radius:20px; padding:18px 18px 16px; box-shadow:0 14px 34px rgba(15,23,42,.08); min-height:128px; transition:transform .18s ease, box-shadow .18s ease;}
.kpi-card:hover {transform:translateY(-2px); box-shadow:0 18px 46px rgba(15,23,42,.14);}
.kpi-card:after {content:''; position:absolute; left:0; right:0; bottom:0; height:4px; background:var(--accent,#2563eb);}
.kpi-top {display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:10px;}
.kpi-icon {width:34px; height:34px; display:grid; place-items:center; border-radius:12px; background:color-mix(in srgb, var(--accent,#2563eb) 12%, white); color:var(--accent,#2563eb); font-weight:800;}
.kpi-title {font-size:.76rem; color:#64748b; text-transform:uppercase; letter-spacing:.08em; font-weight:800;}
.kpi-value {font-size:clamp(1.35rem,2vw,1.95rem); font-weight:800; color:#0f172a; line-height:1.08; letter-spacing:-.04em;}
.kpi-sub {font-size:.8rem; color:#64748b; margin-top:8px;}
.section-title {font-size:1.08rem; font-weight:800; margin:0 0 .25rem 0; color:#0f172a; letter-spacing:-.015em;}
.section-sub {font-size:.86rem; color:#64748b; margin-bottom:.7rem; line-height:1.45;}
.filter-chip {display:inline-flex; align-items:center; padding:.28rem .68rem; border-radius:999px; background:#eff6ff; color:#1d4ed8; border:1px solid #bfdbfe; font-size:.8rem; font-weight:700; margin-right:.35rem; margin-bottom:.4rem;}
.divider {height:1px; background:linear-gradient(90deg, transparent, rgba(148,163,184,.5), transparent); margin:1rem 0;}
.alert-card {background:#fff7ed; border:1px solid #fed7aa; border-left:5px solid #ea580c; border-radius:16px; padding:13px 15px; margin-bottom:10px; box-shadow:0 8px 22px rgba(15,23,42,.05);}
.alert-score {display:inline-block; border-radius:999px; background:#dc2626; color:white; padding:2px 8px; font-size:.72rem; font-weight:800; margin-left:6px;}
.ai-card {background:linear-gradient(135deg,#eff6ff 0%,#ffffff 55%,#ecfeff 100%); border:1px solid rgba(37,99,235,.18); border-radius:20px; padding:18px 20px; box-shadow:0 12px 30px rgba(15,23,42,.07); margin-bottom:12px;}
.ai-card strong {color:#1d4ed8;}
.ai-muted {color:#64748b; font-size:.86rem; line-height:1.5;}
.stMultiSelect [data-baseweb=tag] {background-color:#2563eb !important; border-radius:999px !important;}
.stTabs [data-baseweb=tab-list] {gap:6px; border-bottom:1px solid rgba(148,163,184,.28);}
.stTabs [data-baseweb=tab] {border-radius:12px 12px 0 0; font-weight:700; padding:10px 16px;}
@media (max-width: 900px) {.hero-stats {grid-template-columns:1fr 1fr;} .block-container {padding-left:1rem; padding-right:1rem;}}
.sidebar-badge {display:inline-flex;align-items:center;gap:0.3rem;padding:0.15rem 0.5rem;border-radius:999px;font-size:0.68rem;font-weight:700;}
.sidebar-badge-admin {background:rgba(37,99,235,0.15);color:#2563eb;border:1px solid rgba(37,99,235,0.25);}
.sidebar-badge-viewer {background:rgba(16,185,129,0.15);color:#16a34a;border:1px solid rgba(16,185,129,0.25);}
.sidebar-user-item {display:flex;align-items:center;justify-content:space-between;padding:0.5rem 0.65rem;border-radius:10px;background:rgba(255,255,255,0.6);border:1px solid rgba(148,163,184,0.2);margin-bottom:0.35rem;}
.sidebar-user-item-left {display:flex;align-items:center;gap:0.5rem;}
.sidebar-user-item-name {font-weight:600;font-size:0.8rem;color:#0f172a;}
.sidebar-user-item-time {font-size:0.65rem;color:#64748b;}
.sidebar-pdf-item {font-size:0.8rem;color:#475569;padding:0.15rem 0;}
</style>
''', unsafe_allow_html=True)

def moeda_br(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except Exception:
        return 'R$ 0,00'

def carregar_csv_seguro(caminho: Path) -> pd.DataFrame:
    if not caminho.exists():
        return pd.DataFrame()
    for sep in [';', ',']:
        try:
            return pd.read_csv(caminho, sep=sep, encoding='utf-8-sig')
        except Exception:
            continue
    return pd.DataFrame()

def preparar_numeros(df: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    for col in colunas:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors='coerce')
    return out

def preparar_datas(df: pd.DataFrame, coluna: str) -> pd.DataFrame:
    if df.empty or coluna not in df.columns:
        return df
    out = df.copy()
    out[coluna] = pd.to_datetime(out[coluna], format='%d/%m/%Y', errors='coerce')
    return out

def formatar_fig(fig, *, height: int | None = None, moeda: bool = False):
    fig.update_layout(**PLOTLY_LAYOUT)
    if height:
        fig.update_layout(height=height)
    fig.update_xaxes(showgrid=False, linecolor='#cbd5e1', zeroline=False)
    fig.update_yaxes(gridcolor='rgba(148,163,184,.22)', linecolor='#cbd5e1', zeroline=False)
    if moeda:
        fig.update_yaxes(tickprefix='R$ ', separatethousands=True)
    return fig

def preparar_exibicao(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    return df.rename(columns={origem: destino for origem, destino in COLUNAS_EXIBICAO.items() if origem in df.columns})

def gerar_link_verificacao_nf(chave_nf: str, numero_nf: str = '', tipo: str = '') -> tuple[str, str]:
    if chave_nf and len(chave_nf) >= 44:
        url = f'https://www.nfe.fazenda.gov.br/portal/consultaRecaptcha.aspx?tipoConteudo=XbSeqxE8pl8=&chaveAcesso={chave_nf[:44]}'
        return 'Verificar NF-e na SEFAZ', url
    if numero_nf and tipo:
        tipo_norm = tipo.lower()
        if 'nfs' in tipo_norm or 'municipal' in tipo_norm:
            return 'Consultar NFS-e (Nacional)', 'https://nfs-e.municipios.gov.br/'
    return 'Verificação online', 'https://www.nfe.fazenda.gov.br/portal/consulta.aspx'

def buscar_empresa_cnpj(cnpj: str) -> dict:
    cnpj_limpo = re.sub(r'\D', '', str(cnpj or ''))
    if len(cnpj_limpo) != 14:
        return {}
    try:
        req = Request(f'https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}', headers={'User-Agent': 'AuditoriaCondominio/1.0'})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        return {
            'razao_social': data.get('razao_social', ''),
            'nome_fantasia': data.get('nome_fantasia', ''),
            'situacao': data.get('descricao_situacao_cadastral', ''),
            'atividade': data.get('descricao_tipo_logradouro', '') + ' ' + data.get('cnae_fiscal_descricao', ''),
            'endereco': f"{data.get('logradouro', '')}, {data.get('numero', '')} - {data.get('bairro', '')}/{data.get('municipio', '')}-{data.get('uf', '')}",
        }
    except Exception:
        return {}

def explicar_item_ia(fornecedor: str, descricao: str, valor: float, categoria: str, cnpj: str = '') -> str:
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        return 'Configure OPENAI_API_KEY ou OPENROUTER_API_KEY para ativar explicações por IA.'
    prompt = f'Explique de forma concisa e prática para um auditor de condomínios:\n'
    prompt += f'- Fornecedor: {fornecedor or "Não identificado"}\n'
    prompt += f'- Descrição: {descricao}\n'
    prompt += f'- Valor: {moeda_br(valor)}\n'
    prompt += f'- Categoria: {categoria or "Não classificada"}\n'
    if cnpj:
        prompt += f'- CNPJ: {cnpj}\n'
    prompt += f'\nResponda em português. Inclua: tipo de serviço/obra, riscos comuns, o que verificar no documento, e se há indícios de sobrepreço ou irregularidade. Seja direto.'
    mensagens = [
        {'role': 'system', 'content': 'Você é um analista sênior de auditoria condominial. Responda em português, seja direto, use bullet points e destaque riscos e próximos passos práticos.'},
        {'role': 'user', 'content': prompt},
    ]
    payload = json.dumps({'model': OPENAI_MODEL, 'messages': mensagens, 'temperature': 0.3, 'max_tokens': 600}).encode('utf-8')
    req = Request(
        f'{OPENAI_BASE_URL}/chat/completions',
        data=payload,
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json', 'HTTP-Referer': 'http://localhost:8501', 'X-Title': 'AuditoriaCondominio'},
        method='POST',
    )
    try:
        with urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        return data['choices'][0]['message']['content']
    except HTTPError as exc:
        detalhe = exc.read().decode('utf-8', errors='ignore')[:300]
        return f'Erro na IA ({exc.code}): {detalhe}'
    except Exception as exc:
        return f'Não foi possível consultar a IA: {exc}'

def detectar_divergencia_balanco_mov(df_bal: pd.DataFrame, df_mov: pd.DataFrame) -> list[dict]:
    alertas = []
    if df_bal.empty or df_mov.empty:
        return alertas
    for _, bal in df_bal.iterrows():
        mes = bal.get('Mes_Ano', '')
        desp_bal = float(bal.get('Total_Despesas', 0) or 0)
        saidas_mov = df_mov[(df_mov['Mes_Ano'].astype(str) == str(mes)) & (df_mov['Tipo_Movimento'] == 'Saída')]['Valor_Real'].sum()
        if desp_bal > 0 and saidas_mov > 0:
            diff_pct = abs(desp_bal - saidas_mov) / desp_bal * 100
            if diff_pct > 10:
                alertas.append({
                    'mes': mes,
                    'despesas_balanco': desp_bal,
                    'saidas_analiticas': saidas_mov,
                    'diferenca': desp_bal - saidas_mov,
                    'percentual': diff_pct,
                    'mensagem': f'{mes}: Balancete reporta {moeda_br(desp_bal)} em despesas, mas movimentações analíticas somam {moeda_br(saidas_mov)}. Diferença: {moeda_br(abs(desp_bal - saidas_mov))} ({diff_pct:.1f}%).',
                })
        elif desp_bal > 0 and saidas_mov == 0:
            alertas.append({
                'mes': mes,
                'despesas_balanco': desp_bal,
                'saidas_analiticas': 0,
                'diferenca': desp_bal,
                'percentual': 100,
                'mensagem': f'{mes}: Balancete tem {moeda_br(desp_bal)} em despesas, mas nenhuma saída analítica foi extraída.',
            })
    return alertas

def top_linhas(df: pd.DataFrame, grupo: str, valor: str, limite: int = 5) -> str:
    if df.empty or grupo not in df.columns or valor not in df.columns:
        return 'Sem dados disponíveis.'
    top = df.groupby(grupo, dropna=False)[valor].sum().reset_index().sort_values(valor, ascending=False).head(limite)
    if top.empty:
        return 'Sem dados disponíveis.'
    return '; '.join(f"{linha[grupo]}: {moeda_br(linha[valor])}" for _, linha in top.iterrows())

def resumo_para_ia(df_bal: pd.DataFrame, df_cat: pd.DataFrame, df_mov: pd.DataFrame, df_cob: pd.DataFrame) -> str:
    linhas = []
    if not df_bal.empty:
        receitas_total = float(df_bal['Total_Receitas'].fillna(0).sum()) if 'Total_Receitas' in df_bal.columns else 0
        despesas_total = float(df_bal['Total_Despesas'].fillna(0).sum()) if 'Total_Despesas' in df_bal.columns else 0
        resultado_total = float(df_bal['Movimento_Liquido'].fillna(0).sum()) if 'Movimento_Liquido' in df_bal.columns else receitas_total - despesas_total
        linhas.append(f'Receitas totais: {moeda_br(receitas_total)}')
        linhas.append(f'Despesas totais: {moeda_br(despesas_total)}')
        linhas.append(f'Resultado líquido: {moeda_br(resultado_total)}')
    if not df_cat.empty:
        valor_cat = 'Valor_Saida' if 'Valor_Saida' in df_cat.columns else 'Valor'
        linhas.append(f'Top categorias: {top_linhas(df_cat, "Categoria", valor_cat)}')
    if not df_mov.empty:
        linhas.append(f'Top fornecedores por saída: {top_linhas(df_mov[df_mov.get("Tipo_Movimento", "") == "Saída"] if "Tipo_Movimento" in df_mov.columns else df_mov, "Fornecedor", "Valor_Saida")}')
        if 'Link_NF' in df_mov.columns:
            nfs = df_mov[df_mov['Link_NF'].fillna('').astype(str).str.len() > 0]
            linhas.append(f'Notas fiscais/comprovantes vinculados: {len(nfs)}')
            if not nfs.empty and 'Status_Consulta_NF' in nfs.columns:
                status = nfs['Status_Consulta_NF'].fillna('Sem status').astype(str).value_counts().head(3)
                linhas.append('Status NF: ' + '; '.join(f'{idx}: {valor}' for idx, valor in status.items()))
        if SCORE_COL in df_mov.columns:
            divs = df_mov[df_mov[SCORE_COL].fillna(0) >= 40].copy().sort_values(SCORE_COL, ascending=False).head(5)
            if not divs.empty:
                itens = []
                for _, row in divs.iterrows():
                    itens.append(f"{row.get('Fornecedor', 'Fornecedor não identificado')} | score {row.get(SCORE_COL, 0)} | {moeda_br(row.get('Valor_Real', 0))} | {row.get(MOTIVO_COL, 'Sem motivo')}")
                linhas.append('Principais divergências: ' + '; '.join(itens))
    if not df_cob.empty:
        linhas.append(f'Top blocos por cobrança: {top_linhas(df_cob, "Bloco", "Valor")}' )
    return '\n'.join(linhas) if linhas else 'Ainda não há dados processados para análise.'

def insights_locais(df_bal: pd.DataFrame, df_cat: pd.DataFrame, df_mov: pd.DataFrame, df_cob: pd.DataFrame) -> list[str]:
    insights = []
    if not df_bal.empty and {'Total_Receitas', 'Total_Despesas'}.issubset(df_bal.columns):
        rec = float(df_bal['Total_Receitas'].fillna(0).sum())
        desp = float(df_bal['Total_Despesas'].fillna(0).sum())
        saldo = rec - desp
        margem = (saldo / rec * 100) if rec else 0
        insights.append(f'Resultado do período: {moeda_br(saldo)} ({margem:.1f}% das receitas).')
    if not df_mov.empty and {'Tipo_Movimento', 'Fornecedor', 'Valor_Saida'}.issubset(df_mov.columns):
        saidas = df_mov[df_mov['Tipo_Movimento'] == 'Saída']
        if not saidas.empty:
            top = saidas.groupby('Fornecedor', dropna=False)['Valor_Saida'].sum().reset_index().sort_values('Valor_Saida', ascending=False).iloc[0]
            insights.append(f'Maior fornecedor de saída: {top["Fornecedor"]}, com {moeda_br(top["Valor_Saida"])}.')
    if not df_cat.empty and {'Categoria', 'Valor_Saida'}.issubset(df_cat.columns):
        top = df_cat.groupby('Categoria', dropna=False)['Valor_Saida'].sum().reset_index().sort_values('Valor_Saida', ascending=False).head(1)
        if not top.empty:
            insights.append(f'Categoria de despesa mais relevante: {top.iloc[0]["Categoria"]}, totalizando {moeda_br(top.iloc[0]["Valor_Saida"])}.')
    if not df_mov.empty and SCORE_COL in df_mov.columns:
        qtd = int((df_mov[SCORE_COL].fillna(0) >= 40).sum())
        max_score = float(df_mov[SCORE_COL].fillna(0).max()) if len(df_mov) else 0
        insights.append(f'Divergências mapeadas: {qtd} movimentação(ões) com score >= 40; maior score encontrado: {max_score:.0f}.')
    if not df_mov.empty and 'Link_NF' in df_mov.columns:
        nfs = df_mov[df_mov['Link_NF'].fillna('').astype(str).str.len() > 0]
        chaves = int(nfs['Chave_NF'].fillna('').astype(str).str.len().gt(0).sum()) if not nfs.empty and 'Chave_NF' in nfs.columns else 0
        insights.append(f'Notas fiscais/comprovantes vinculados: {len(nfs)}; {chaves} com chave de acesso identificada.')
    if not df_cob.empty and {'Bloco', 'Valor'}.issubset(df_cob.columns):
        insights.append(f'Cobranças analisadas: {len(df_cob)} registro(s), somando {moeda_br(df_cob["Valor"].fillna(0).sum())}.')
    return insights or ['Execute a auditoria ou carregue os CSVs para gerar insights automáticos.']

def chamar_modelo_ia(pergunta: str, contexto: str, historico: list[dict[str, str]]) -> tuple[str | None, str | None]:
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        return None, 'Defina a variável de ambiente OPENAI_API_KEY para ativar respostas geradas por IA.'
    mensagens = [
        {
            'role': 'system',
            'content': 'Você é um analista sênior de auditoria condominial. Responda em português, seja direto, use somente os dados fornecidos e destaque riscos, divergências e próximos passos práticos.',
        },
        {'role': 'user', 'content': f'Contexto dos dados filtrados:\n{contexto}'},
    ]
    mensagens.extend(historico[-8:])
    mensagens.append({'role': 'user', 'content': pergunta})
    payload = json.dumps({'model': OPENAI_MODEL, 'messages': mensagens, 'temperature': 0.2}).encode('utf-8')
    req = Request(
        f'{OPENAI_BASE_URL}/chat/completions',
        data=payload,
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        return data['choices'][0]['message']['content'], None
    except HTTPError as exc:
        detalhe = exc.read().decode('utf-8', errors='ignore')
        return None, f'Erro da API de IA ({exc.code}): {detalhe[:500]}'
    except (URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
        return None, f'Não foi possível consultar a IA: {exc}'

def limpar_pasta_upload() -> None:
    if PASTA_PDFS.exists():
        shutil.rmtree(PASTA_PDFS)
    PASTA_PDFS.mkdir(exist_ok=True)

def salvar_uploads(arquivos) -> int:
    limpar_pasta_upload()
    total = 0
    for arq in arquivos:
        destino = PASTA_PDFS / arq.name
        with open(destino, 'wb') as f:
            f.write(arq.getbuffer())
        total += 1
    return total

def listar_pdfs() -> list[str]:
    if not PASTA_PDFS.exists():
        return []
    return sorted([p.name for p in PASTA_PDFS.glob('*.pdf')])

def dashboards_existentes() -> list[tuple[str, Path]]:
    return [(nome, caminho) for nome, caminho in DASHBOARDS_HTML if caminho.exists()]

def arquivos_download_existentes() -> list[Path]:
    return [p for p in ARQUIVOS_DOWNLOAD if p.exists()]

def executar_runner_com_log() -> tuple[bool, int | None, str]:
    buffer_out = io.StringIO()
    buffer_err = io.StringIO()
    try:
        with redirect_stdout(buffer_out), redirect_stderr(buffer_err):
            retorno = runner.main()
        log_texto = buffer_out.getvalue()
        if buffer_err.getvalue():
            log_texto += '\n' + buffer_err.getvalue()
        return retorno in (0, None), retorno, log_texto
    except SystemExit as e:
        codigo = e.code if isinstance(e.code, int) else 0
        log_texto = buffer_out.getvalue()
        if buffer_err.getvalue():
            log_texto += '\n' + buffer_err.getvalue()
        return codigo == 0, codigo, log_texto
    except Exception:
        log_texto = buffer_out.getvalue()
        if buffer_err.getvalue():
            log_texto += '\n' + buffer_err.getvalue()
        log_texto += '\n' + traceback.format_exc()
        return False, -1, log_texto

def carregar_bases() -> dict[str, pd.DataFrame]:
    df_bal = carregar_csv_seguro(ARQUIVO_CSV_BALANCO)
    df_cat = carregar_csv_seguro(ARQUIVO_CSV_CATEGORIAS)
    df_mov = carregar_csv_seguro(ARQUIVO_CSV_MOVIMENTACOES)
    df_cob = carregar_csv_seguro(ARQUIVO_CSV_COBRANCAS)
    df_bal = preparar_numeros(df_bal, ['Saldo_Anterior', 'Total_Receitas', 'Total_Despesas', 'Movimento_Liquido', 'Saldo_Final'])
    df_cat = preparar_numeros(df_cat, ['Valor', 'Valor_Entrada', 'Valor_Saida', 'Valor_Resultante'])
    df_mov = preparar_numeros(df_mov, ['Valor_Real', 'Valor_Assinado', 'Valor_Entrada', 'Valor_Saida', 'Valor_Transferencia', 'Saldo_Apos', SCORE_COL])
    df_cob = preparar_numeros(df_cob, ['Valor', 'Valor_Assinado'])
    df_mov = preparar_datas(df_mov, 'Data')
    df_cob = preparar_datas(df_cob, 'Data_Liquidacao')
    return {'balanco': df_bal, 'categorias': df_cat, 'movimentacoes': df_mov, 'cobrancas': df_cob}

def kpi_card(titulo: str, valor: str, subtitulo: str = '', *, icon: str = '•', accent: str = COR_PRIMARIA) -> None:
    titulo_html = html.escape(str(titulo))
    valor_html = html.escape(str(valor))
    subtitulo_html = html.escape(str(subtitulo))
    icon_html = html.escape(str(icon))
    st.markdown(
        f'''<div class="kpi-card" style="--accent:{accent}"><div class="kpi-top"><div class="kpi-title">{titulo_html}</div><div class="kpi-icon">{icon_html}</div></div><div class="kpi-value">{valor_html}</div><div class="kpi-sub">{subtitulo_html}</div></div>''',
        unsafe_allow_html=True,
    )

def filtros_to_html(meses_sel, tipos_sel, contas_sel, categorias_sel) -> str:
    chips = []
    for grupo in [meses_sel[:3], tipos_sel[:3], contas_sel[:3], categorias_sel[:3]]:
        for item in grupo:
            chips.append(f'<span class="filter-chip">{html.escape(str(item))}</span>')
    if not chips:
        return '<span class="filter-chip">Sem filtro específico</span>'
    return ''.join(chips)

st.markdown('''<div class="hero"><div class="hero-badge">Auditoria executiva • Controles financeiros • Evidências</div><div class="hero-title">Auditoria Inteligente de Condomínios</div><div class="hero-sub">Painel profissional para consolidar balancetes, movimentações, cobranças, fornecedores e alertas de divergência em uma visão única para tomada de decisão.</div></div>''', unsafe_allow_html=True)

with st.sidebar:
    username = st.session_state.get('username', '')
    if username:
        st.markdown(f'<div style="padding:0.5rem;text-align:center;font-size:0.8rem;color:#94a3b8;">👤 {username}</div>', unsafe_allow_html=True)
        if st.button('🚪 Sair', key='btn_logout', use_container_width=True):
            logs_acesso.log_acesso(username, 'LOGOUT', detalhes='Logout realizado')
            st.session_state['authenticated'] = False
            st.session_state['username'] = ''
            st.session_state['user_role'] = 'viewer'
            st.rerun()

is_admin = st.session_state.get('user_role') == 'admin'
if is_admin:
    with st.expander('🛠️ Administração', expanded=False):
        st.markdown('<div class="section-title">⚙️ Operação</div>', unsafe_allow_html=True)
        uploads = st.file_uploader('Selecione os PDFs', type=['pdf'], accept_multiple_files=True, label_visibility='collapsed')
        csave, crun = st.columns(2)
        with csave:
            if uploads and st.button('📥 Salvar', key='btn_save', use_container_width=True):
                qtd = salvar_uploads(uploads)
                st.toast(f'{qtd} arquivo(s) salvo(s).', icon='✅')
        with crun:
            btn_exec = st.button('▶ Executar', key='btn_run', type='primary', use_container_width=True)
            if btn_exec:
                if not listar_pdfs():
                    st.warning('Nenhum PDF salvo em ArquivosPDF.')
                else:
                    with st.spinner('Processando...'):
                        ok, codigo, log_texto = executar_runner_com_log()
                        st.session_state['ultimo_log_auditoria'] = log_texto
                        st.session_state['ultimo_status_auditoria'] = (ok, codigo)
                    if ok:
                        st.toast('Auditoria concluída com sucesso!', icon='✅')
                    else:
                        st.error(f'Falha na auditoria. Código: {codigo}')

        pdfs = listar_pdfs()
        if pdfs:
            with st.expander(f'📂 PDFs prontos ({len(pdfs)})', expanded=False):
                for nome in pdfs:
                    st.markdown(f'<div class="sidebar-pdf-item">{nome}</div>', unsafe_allow_html=True)

        with st.expander('📋 Último log', expanded=False):
            if 'ultimo_log_auditoria' in st.session_state:
                st.code(st.session_state['ultimo_log_auditoria'], language='')
            else:
                st.caption('Execute a auditoria para gerar logs.')

        st.divider()

        tab1, tab2, tab3 = st.tabs(["📊 Logs", "👥 Online", "➕ Novo"])

        with tab1:
            logs = logs_acesso.ler_logs()
            if logs:
                st.caption(f'{len(logs)} registro(s)')
                df_logs = pd.DataFrame(logs)
                try:
                    st.dataframe(df_logs.tail(30), hide_index=True, use_container_width=True, height=200)
                except Exception:
                    st.table(df_logs.tail(30).astype(str))
                if st.button('🗑️ Limpar Logs', key='clear_logs', use_container_width=True):
                    if hasattr(logs_acesso, 'LOG_FILE') and logs_acesso.LOG_FILE.exists():
                        logs_acesso.LOG_FILE.unlink()
                    logs_acesso.init_logs()
                    st.toast('Logs limpos!', icon='🗑️')
                    st.rerun()
            else:
                st.caption('Nenhum log registrado.')

        with tab2:
            all_users = get_all_users()
            online_users = [(u, info) for u, info in all_users.items() if is_user_online(u, minutes=5)]
            offline_users = [(u, info) for u, info in all_users.items() if not is_user_online(u, minutes=5)]

            col_refresh, col_count = st.columns([1, 1])
            with col_refresh:
                if st.button('🔄 Atualizar', key='refresh_users', use_container_width=True):
                    st.rerun()
            with col_count:
                st.markdown(f'<div style="text-align:right;font-size:0.75rem;color:#64748b;padding-top:0.2rem;">{len(online_users)} online</div>', unsafe_allow_html=True)

            if online_users:
                for u, info in online_users:
                    last_seen = info.get('last_seen')
                    time_str = datetime.fromisoformat(last_seen).strftime("%H:%M") if last_seen else "—"
                    role_badge = "Admin" if info.get('role') == 'admin' else "Viewer"
                    bdg = "sidebar-badge-admin" if info.get('role') == 'admin' else "sidebar-badge-viewer"
                    st.markdown(f'''
                    <div class="sidebar-user-item">
                        <div class="sidebar-user-item-left">
                            <span style="width:8px;height:8px;border-radius:50%;background:#34d399;flex-shrink:0;"></span>
                            <div>
                                <div class="sidebar-user-item-name">{u}</div>
                                <div class="sidebar-user-item-time">{time_str}</div>
                            </div>
                        </div>
                        <span class="sidebar-badge {bdg}">{role_badge}</span>
                    </div>
                    ''', unsafe_allow_html=True)
            else:
                st.info('Ninguém online no momento.')

            if offline_users:
                with st.expander(f"Offline ({len(offline_users)})"):
                    for u, info in offline_users:
                        last_seen = info.get('last_seen')
                        time_str = datetime.fromisoformat(last_seen).strftime("%d/%m %H:%M") if last_seen else "Nunca"
                        role_badge = "Admin" if info.get('role') == 'admin' else "Viewer"
                        bdg = "sidebar-badge-admin" if info.get('role') == 'admin' else "sidebar-badge-viewer"
                        st.markdown(f'''
                        <div class="sidebar-user-item">
                            <div class="sidebar-user-item-left">
                                <span style="width:8px;height:8px;border-radius:50%;background:#6b7280;flex-shrink:0;"></span>
                                <div>
                                    <div class="sidebar-user-item-name">{u}</div>
                                    <div class="sidebar-user-item-time">{time_str}</div>
                                </div>
                            </div>
                            <span class="sidebar-badge {bdg}">{role_badge}</span>
                        </div>
                        ''', unsafe_allow_html=True)

        with tab3:
            with st.form("create_user_form", border=False):
                new_username = st.text_input('Usuário', placeholder='Nome')
                new_password = st.text_input('Senha', type='password', placeholder='Senha')
                confirm_password = st.text_input('Confirmar', type='password', placeholder='Confirme')
                user_role = st.selectbox('Perfil', ['viewer', 'admin'])

                if st.form_submit_button('➕ Criar Usuário', use_container_width=True):
                    if not new_username or not new_password:
                        st.error('Preencha todos os campos.')
                    elif new_password != confirm_password:
                        st.error('Senhas não conferem.')
                    elif len(new_password) < 6:
                        st.error('Mínimo 6 caracteres.')
                    else:
                        all_users = get_all_users()
                        if new_username in all_users:
                            st.error('Usuário já existe.')
                        else:
                            users = get_all_users()
                            users[new_username] = {
                                'password_hash': hash_password(new_password),
                                'role': user_role,
                                'created_at': datetime.now().isoformat(),
                                'last_login': None,
                                'last_seen': None
                            }
                            save_all_users_to_file(users)
                            st.toast(f'Usuário "{new_username}" criado!', icon='✅')
                            logs_acesso.log_acesso(st.session_state['username'], 'USER_CREATED',
                                                 detalhes=f'Usuário {new_username} criado com perfil {user_role}')
                            st.rerun()

bases = carregar_bases()
df_bal = bases['balanco']
df_cat = bases['categorias']
df_mov = bases['movimentacoes']
df_cob = bases['cobrancas']

meses_disponiveis = sorted(df_bal['Mes_Ano'].dropna().astype(str).unique().tolist()) if not df_bal.empty and 'Mes_Ano' in df_bal.columns else (sorted(df_mov['Mes_Ano'].dropna().astype(str).unique().tolist()) if not df_mov.empty and 'Mes_Ano' in df_mov.columns else [])
tipos_mov = sorted(df_mov['Tipo_Movimento'].dropna().astype(str).unique().tolist()) if not df_mov.empty and 'Tipo_Movimento' in df_mov.columns else []
contas_mov = sorted(df_mov['Conta'].dropna().astype(str).unique().tolist()) if not df_mov.empty and 'Conta' in df_mov.columns else []
categorias_mov = sorted(df_mov['Categoria'].dropna().astype(str).unique().tolist()) if not df_mov.empty and 'Categoria' in df_mov.columns else []

with st.expander('🎛️ Abrir filtros analíticos', expanded=False):
    st.markdown('<div class="section-sub">Os filtros agora ficam recolhidos por padrão e vazios significam: mostrar tudo.</div>', unsafe_allow_html=True)
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        meses_sel = st.multiselect('Mês/Ano', meses_disponiveis, default=[])
    with f2:
        tipos_sel = st.multiselect('Tipo de movimento', tipos_mov, default=[])
    with f3:
        contas_sel = st.multiselect('Conta', contas_mov, default=[])
    with f4:
        categorias_sel = st.multiselect('Categoria de movimento', categorias_mov, default=[])

st.markdown(filtros_to_html(meses_sel, tipos_sel, contas_sel, categorias_sel), unsafe_allow_html=True)

df_bal_f = df_bal.copy()
if not df_bal.empty and meses_sel:
    df_bal_f = df_bal_f[df_bal_f['Mes_Ano'].astype(str).isin(meses_sel)]
df_cat_f = df_cat.copy()
if not df_cat.empty and meses_sel:
    df_cat_f = df_cat_f[df_cat_f['Mes_Ano'].astype(str).isin(meses_sel)]
df_mov_f = df_mov.copy()
if not df_mov.empty:
    if meses_sel:
        df_mov_f = df_mov_f[df_mov_f['Mes_Ano'].astype(str).isin(meses_sel)]
    if tipos_sel:
        df_mov_f = df_mov_f[df_mov_f['Tipo_Movimento'].astype(str).isin(tipos_sel)]
    if contas_sel:
        df_mov_f = df_mov_f[df_mov_f['Conta'].astype(str).isin(contas_sel)]
    if categorias_sel:
        df_mov_f = df_mov_f[df_mov_f['Categoria'].astype(str).isin(categorias_sel)]
df_cob_f = df_cob.copy()
if not df_cob.empty and meses_sel:
    df_cob_f = df_cob_f[df_cob_f['Mes_Ano'].astype(str).isin(meses_sel)]

receitas = float(df_bal_f['Total_Receitas'].fillna(0).sum()) if not df_bal_f.empty and 'Total_Receitas' in df_bal_f.columns else 0.0
despesas = float(df_bal_f['Total_Despesas'].fillna(0).sum()) if not df_bal_f.empty and 'Total_Despesas' in df_bal_f.columns else 0.0
resultado = float(df_bal_f['Movimento_Liquido'].fillna(0).sum()) if not df_bal_f.empty and 'Movimento_Liquido' in df_bal_f.columns else (receitas - despesas)
saldo_final = float(df_bal_f['Saldo_Final'].dropna().iloc[-1]) if not df_bal_f.empty and 'Saldo_Final' in df_bal_f.columns and not df_bal_f['Saldo_Final'].dropna().empty else 0.0
qtd_pdfs = len(listar_pdfs())
qtd_mov = len(df_mov_f) if not df_mov_f.empty else 0
qtd_cob = len(df_cob_f) if not df_cob_f.empty else 0
qtd_alertas = int((df_mov_f[SCORE_COL].fillna(0) >= 40).sum()) if not df_mov_f.empty and SCORE_COL in df_mov_f.columns else 0
df_nf_f = df_mov_f[df_mov_f['Link_NF'].fillna('').astype(str).str.len() > 0].copy() if not df_mov_f.empty and 'Link_NF' in df_mov_f.columns else pd.DataFrame()
qtd_nf = len(df_nf_f) if not df_nf_f.empty else 0
qtd_nf_chave = int(df_nf_f['Chave_NF'].fillna('').astype(str).str.len().gt(0).sum()) if not df_nf_f.empty and 'Chave_NF' in df_nf_f.columns else 0

c1, c2, c3, c4 = st.columns(4)
with c1: kpi_card('Receitas', moeda_br(receitas), f'{len(df_bal_f)} período(s) selecionado(s)', icon='R$', accent=COR_ENTRADA)
with c2: kpi_card('Despesas', moeda_br(despesas), 'Baseado no balancete consolidado', icon='D', accent=COR_SAIDA)
with c3: kpi_card('Resultado', moeda_br(resultado), 'Movimento líquido dos períodos filtrados', icon='Δ', accent=COR_PRIMARIA if resultado >= 0 else COR_SAIDA)
with c4: kpi_card('Saldo Final', moeda_br(saldo_final), 'Último saldo final disponível', icon='S', accent=COR_CIANO)
c5, c6, c7, c8 = st.columns(4)
with c5: kpi_card('PDFs', str(qtd_pdfs), 'Arquivos em ArquivosPDF', icon='PDF', accent='#7c3aed')
with c6: kpi_card('Movimentações', f'{qtd_mov:,}'.replace(',', '.'), 'Após os filtros aplicados', icon='MOV', accent=COR_TRANSFERENCIA)
with c7: kpi_card('Notas Fiscais', f'{qtd_nf:,}'.replace(',', '.'), f'{qtd_nf_chave} com chave identificada', icon='NF', accent='#0f766e')
with c8: kpi_card('Alertas', f'{qtd_alertas:,}'.replace(',', '.'), 'Score de divergência >= 40', icon='!', accent=COR_SAIDA)

alertas_div = detectar_divergencia_balanco_mov(df_bal_f, df_mov_f)
if alertas_div:
    st.markdown('<div class="section-title" style="color:#dc2626">⚠️ Divergências: Balancete vs Movimentações Analíticas</div>', unsafe_allow_html=True)
    for alerta in alertas_div[:5]:
        st.markdown(f'<div class="alert-card"><strong>{html.escape(alerta["mes"])}</strong><br>{html.escape(alerta["mensagem"])}</div>', unsafe_allow_html=True)
    if len(alertas_div) > 5:
        st.caption(f'+ {len(alertas_div) - 5} outras divergências detectadas.')

tab_labels = ['📈 Visão Executiva', '🤖 Assistente IA', '💰 Balanço', '🧩 Categorias', '🧾 Notas Fiscais', '🔎 Movimentações', '🏷️ Cobranças', '🌐 HTMLs', '📥 Downloads']
tabs = st.tabs(tab_labels)
aba_exec, aba_ia, aba_balanco, aba_cat, aba_nf, aba_mov, aba_cob, aba_dash, aba_dl = tabs

with aba_exec:
    r1c1, r1c2 = st.columns(2)
    with r1c1:
        with st.container(border=True):
            st.markdown('<div class="section-title">Receitas x Despesas x Resultado</div><div class="section-sub">Barras + linha usando Plotly Graph Objects.</div>', unsafe_allow_html=True)
            if not df_bal_f.empty and 'Mes_Ano' in df_bal_f.columns:
                bal_plot = df_bal_f[['Mes_Ano', 'Total_Receitas', 'Total_Despesas', 'Movimento_Liquido']].copy().sort_values('Mes_Ano')
                fig = go.Figure()
                fig.add_trace(go.Bar(name='Receitas', x=bal_plot['Mes_Ano'], y=bal_plot['Total_Receitas'], marker_color='#22c55e'))
                fig.add_trace(go.Bar(name='Despesas', x=bal_plot['Mes_Ano'], y=bal_plot['Total_Despesas'], marker_color='#ef4444'))
                fig.add_trace(go.Scatter(name='Resultado', x=bal_plot['Mes_Ano'], y=bal_plot['Movimento_Liquido'], mode='lines+markers', line=dict(color='#2563eb', width=4)))
                formatar_fig(fig, height=470, moeda=True)
                fig.update_layout(barmode='group')
                st.plotly_chart(fig, width='stretch')
            else:
                st.info('Sem dados de balanço para exibir.')
    with r1c2:
        with st.container(border=True):
            st.markdown('<div class="section-title">Linha do tempo dos saldos</div><div class="section-sub">Evolução do saldo anterior e saldo final.</div>', unsafe_allow_html=True)
            if not df_bal_f.empty and 'Mes_Ano' in df_bal_f.columns:
                fig = go.Figure()
                if 'Saldo_Anterior' in df_bal_f.columns:
                    fig.add_trace(go.Scatter(name='Saldo anterior', x=df_bal_f['Mes_Ano'], y=df_bal_f['Saldo_Anterior'], mode='lines+markers', line=dict(color='#94a3b8', width=3)))
                if 'Saldo_Final' in df_bal_f.columns:
                    fig.add_trace(go.Scatter(name='Saldo final', x=df_bal_f['Mes_Ano'], y=df_bal_f['Saldo_Final'], mode='lines+markers', line=dict(color='#0ea5e9', width=4)))
                formatar_fig(fig, height=470, moeda=True)
                st.plotly_chart(fig, width='stretch')
            else:
                st.info('Sem dados de saldo para exibir.')
    r2c1, r2c2 = st.columns(2)
    with r2c1:
        with st.container(border=True):
            st.markdown('<div class="section-title">Treemap das categorias</div><div class="section-sub">Visual premium para entradas e saídas por categoria.</div>', unsafe_allow_html=True)
            if not df_cat_f.empty:
                tree = px.treemap(df_cat_f, path=[px.Constant('Categorias'), 'Grupo', 'Categoria'], values='Valor', color='Grupo', color_discrete_map={'Entrada': COR_ENTRADA, 'Saída': COR_SAIDA}, height=540)
                formatar_fig(tree, height=540)
                st.plotly_chart(tree, width='stretch')
            else:
                st.info('Sem categorias para exibir.')
    with r2c2:
        with st.container(border=True):
            st.markdown('<div class="section-title">Mix de movimentações</div><div class="section-sub">Donut chart das entradas, saídas e transferências.</div>', unsafe_allow_html=True)
            if not df_mov_f.empty and 'Tipo_Movimento' in df_mov_f.columns:
                resumo_tipos = df_mov_f.groupby('Tipo_Movimento', dropna=False)[['Valor_Entrada', 'Valor_Saida', 'Valor_Transferencia']].sum().reset_index()
                resumo_tipos['Valor'] = resumo_tipos.apply(lambda row: row['Valor_Entrada'] if row['Tipo_Movimento'] == 'Entrada' else (row['Valor_Saida'] if row['Tipo_Movimento'] == 'Saída' else row['Valor_Transferencia']), axis=1)
                fig = px.pie(resumo_tipos, names='Tipo_Movimento', values='Valor', hole=0.62, color='Tipo_Movimento', color_discrete_map={'Entrada': COR_ENTRADA, 'Saída': COR_SAIDA, 'Transferência': COR_TRANSFERENCIA}, height=540)
                fig.update_traces(textposition='inside', textinfo='percent+label', marker=dict(line=dict(color='white', width=2)))
                formatar_fig(fig, height=540)
                st.plotly_chart(fig, width='stretch')
            else:
                st.info('Sem movimentações para exibir.')
    r3c1, r3c2 = st.columns(2)
    with r3c1:
        with st.container(border=True):
            st.markdown('<div class="section-title">Top fornecedores por saídas</div><div class="section-sub">Funnel chart para destacar os maiores fornecedores de despesa.</div>', unsafe_allow_html=True)
            if not df_mov_f.empty and 'Tipo_Movimento' in df_mov_f.columns:
                top_saida = df_mov_f[df_mov_f['Tipo_Movimento'] == 'Saída'].groupby('Fornecedor', dropna=False)['Valor_Saida'].sum().reset_index().sort_values('Valor_Saida', ascending=False).head(12)
                if not top_saida.empty:
                    fig = px.funnel(top_saida, x='Valor_Saida', y='Fornecedor', height=520, color_discrete_sequence=[COR_SAIDA])
                    formatar_fig(fig, height=520, moeda=True)
                    st.plotly_chart(fig, width='stretch')
                else:
                    st.info('Sem saídas para ranking de fornecedores.')
            else:
                st.info('Sem movimentações de saída para ranking.')
    with r3c2:
        with st.container(border=True):
            st.markdown('<div class="section-title">Heatmap das categorias de saída</div><div class="section-sub">Matriz mês × categoria para identificar concentração de despesas.</div>', unsafe_allow_html=True)
            if not df_cat_f.empty and {'Mes_Ano', 'Categoria', 'Valor_Saida'}.issubset(df_cat_f.columns):
                heat = df_cat_f.groupby(['Categoria', 'Mes_Ano'], dropna=False)['Valor_Saida'].sum().reset_index()
                if not heat.empty:
                    piv = heat.pivot(index='Categoria', columns='Mes_Ano', values='Valor_Saida').fillna(0)
                    fig = px.imshow(piv, aspect='auto', color_continuous_scale='Tealgrn', height=520, labels={'x': 'Mês', 'y': 'Categoria', 'color': 'Saídas'})
                    formatar_fig(fig, height=520)
                    st.plotly_chart(fig, width='stretch')
                else:
                    st.info('Sem dados para mapa de calor.')
            else:
                st.info('Sem categorias de saída para o heatmap.')
    r4c1, r4c2 = st.columns(2)
    with r4c1:
        with st.container(border=True):
            st.markdown('<div class="section-title">Saídas x score de divergência</div><div class="section-sub">Scatter plot para identificar outliers por conta, valor e justificativa.</div>', unsafe_allow_html=True)
            if not df_mov_f.empty and {SCORE_COL, 'Conta', 'Tipo_Movimento'}.issubset(df_mov_f.columns):
                divergencias = df_mov_f[df_mov_f['Tipo_Movimento'] == 'Saída'].copy()
                if not divergencias.empty:
                    divergencias_plot = preparar_exibicao(divergencias)
                    hover_cols = [c for c in ['Data', 'Fornecedor', 'Descricao', 'Motivo_Divergencia'] if c in divergencias_plot.columns]
                    fig = px.scatter(divergencias_plot, x='Score_Divergencia', y='Valor_Real', color='Conta' if 'Conta' in divergencias_plot.columns else None, hover_data=hover_cols, height=520, size='Valor_Real' if 'Valor_Real' in divergencias_plot.columns else None, color_discrete_sequence=px.colors.qualitative.Safe)
                    fig.update_traces(marker=dict(opacity=.82, line=dict(width=1, color='white')))
                    formatar_fig(fig, height=520, moeda=True)
                    st.plotly_chart(fig, width='stretch')
                    top_div = divergencias_plot.sort_values('Score_Divergencia', ascending=False).head(3)
                    for _, row in top_div.iterrows():
                        fornecedor = html.escape(str(row.get('Fornecedor', 'Fornecedor não identificado')))
                        motivo = html.escape(str(row.get('Motivo_Divergencia', 'Sem motivo registrado')))
                        valor = moeda_br(row.get('Valor_Real', 0))
                        score_val = pd.to_numeric(row.get('Score_Divergencia', 0), errors='coerce')
                        score = int(score_val) if pd.notna(score_val) else 0
                        st.markdown(f'<div class="alert-card"><strong>{fornecedor}</strong><span class="alert-score">{score}</span><br><span>{valor} · {motivo}</span></div>', unsafe_allow_html=True)
                else:
                    st.info('Sem saídas para análise de score.')
            else:
                st.info('Sem score de divergência disponível.')
    with r4c2:
        with st.container(border=True):
            st.markdown('<div class="section-title">Sunburst por conta e tipo</div><div class="section-sub">Navegação hierárquica para entender o peso das contas e dos tipos de movimento.</div>', unsafe_allow_html=True)
            if not df_mov_f.empty and {'Conta', 'Tipo_Movimento', 'Valor_Entrada', 'Valor_Saida', 'Valor_Transferencia'}.issubset(df_mov_f.columns):
                grp = df_mov_f.groupby(['Conta', 'Tipo_Movimento'], dropna=False)[['Valor_Entrada', 'Valor_Saida', 'Valor_Transferencia']].sum().reset_index()
                grp['Valor'] = grp.apply(lambda row: row['Valor_Entrada'] if row['Tipo_Movimento'] == 'Entrada' else (row['Valor_Saida'] if row['Tipo_Movimento'] == 'Saída' else row['Valor_Transferencia']), axis=1)
                fig = px.sunburst(grp, path=[px.Constant('Contas'), 'Conta', 'Tipo_Movimento'], values='Valor', height=520, color='Tipo_Movimento', color_discrete_map={'Entrada': COR_ENTRADA, 'Saída': COR_SAIDA, 'Transferência': COR_TRANSFERENCIA})
                formatar_fig(fig, height=520)
                st.plotly_chart(fig, width='stretch')
            else:
                st.info('Sem dados suficientes para o sunburst.')

def encontrar_imagem_divergente(row):
    """Busca imagem do divergente em múltiplos locais"""
    arquivo_nf = str(row.get('Arquivo_NF_Baixado', '') or '')
    link_nf = str(row.get('Link_NF', '') or '')
    
    # Verifica se já é imagem PNG
    if Path(arquivo_nf).exists() and arquivo_nf.lower().endswith('.png'):
        return arquivo_nf
    if Path(link_nf).exists() and link_nf.lower().endswith('.png'):
        return link_nf
    
    # Busca em divergentes_imgs/ por PNG correspondente
    fornecedor = str(row.get('Fornecedor', '') or '')
    valor = row.get('Valor_Real', 0)
    
    imgs_dir = Path('divergentes_imgs')
    if imgs_dir.exists():
        # Busca por nome aproximado
        for img in imgs_dir.glob('*.png'):
            nome_img = img.name.lower()
            if fornecedor.lower()[:15] in nome_img or f"_{str(valor).replace('.', '_')}_" in nome_img:
                return str(img)
    
    # Se tem PDF, extrai primeira página como imagem
    if Path(arquivo_nf).exists() and arquivo_nf.lower().endswith('.pdf'):
        try:
            import fitz
            doc = fitz.open(arquivo_nf)
            if len(doc) > 0:
                pix = doc[0].get_pixmap(dpi=150)
                img_path = Path(arquivo_nf).with_suffix('.png')
                pix.save(img_path)
                doc.close()
                return str(img_path)
        except:
            pass
    
    return ''

with aba_ia:
    st.markdown('<div class="section-title">Assistente IA para análise da auditoria</div><div class="section-sub">Use como um copiloto analítico: peça resumo executivo, riscos, prioridades, fornecedores relevantes ou explicações sobre divergências.</div>', unsafe_allow_html=True)
    contexto_ia = resumo_para_ia(df_bal_f, df_cat_f, df_mov_f, df_cob_f)
    st.markdown('<div class="ai-card"><strong>Leitura automática dos dados filtrados</strong><div class="ai-muted">Os pontos abaixo são gerados localmente, mesmo sem chave de API.</div></div>', unsafe_allow_html=True)
    for insight in insights_locais(df_bal_f, df_cat_f, df_mov_f, df_cob_f):
        st.markdown(f'<div class="alert-card">{html.escape(insight)}</div>', unsafe_allow_html=True)

    with st.expander('Contexto que será enviado para a IA', expanded=False):
        st.code(contexto_ia, language='text')

    if not os.getenv('OPENAI_API_KEY'):
        st.info('Para ativar respostas por IA generativa, configure OPENAI_API_KEY. Opcionalmente use OPENAI_MODEL e OPENAI_BASE_URL para modelos compatíveis com OpenAI.')

    if 'chat_ia_auditoria' not in st.session_state:
        st.session_state['chat_ia_auditoria'] = []

    for msg in st.session_state['chat_ia_auditoria']:
        with st.chat_message(msg['role']):
            st.markdown(msg['content'])

    pergunta = st.chat_input('Pergunte para a IA sobre a auditoria, os gráficos ou as divergências...')
    if pergunta:
        historico_anterior = list(st.session_state['chat_ia_auditoria'])
        st.session_state['chat_ia_auditoria'].append({'role': 'user', 'content': pergunta})
        with st.spinner('Analisando os dados filtrados...'):
            resposta, erro = chamar_modelo_ia(pergunta, contexto_ia, historico_anterior)
        if erro and not resposta:
            resposta = f'{erro}\n\nEnquanto a IA generativa não está configurada, use estes insights locais:\n' + '\n'.join(f'- {item}' for item in insights_locais(df_bal_f, df_cat_f, df_mov_f, df_cob_f))
        st.session_state['chat_ia_auditoria'].append({'role': 'assistant', 'content': resposta or 'Não consegui gerar uma resposta para esta pergunta.'})
        st.rerun()

    st.markdown('<hr style="margin: 2rem 0;"><div class="section-title">🔍 Análise IA dos Documentos Divergentes</div>', unsafe_allow_html=True)
    divergentes = df_mov_f[df_mov_f[SCORE_COL] > 0].sort_values(SCORE_COL, ascending=False).head(10)
    if divergentes.empty:
        st.info('Nenhuma divergência encontrada nos dados filtrados.')
    else:
        st.markdown(f'<div class="ai-muted">Analisando {len(divergentes)} itens com score de divergência > 0</div>', unsafe_allow_html=True)
    for idx, (_, row) in enumerate(divergentes.iterrows()):
        fornecedor_str = str(row.get('Fornecedor', 'N/A'))
        with st.expander(f"#{idx+1} Score {int(row.get(SCORE_COL, 0))} | {row.get('Data', '')} | {fornecedor_str[:50]} | {moeda_br(row.get('Valor_Real', 0))}", expanded=(idx == 0)):
                col_img, col_info = st.columns([1, 1])
                with col_img:
                    caminho_img = encontrar_imagem_divergente(row)
                    if caminho_img and Path(caminho_img).exists():
                        st.image(caminho_img, caption=Path(caminho_img).name, width='stretch')
                    else:
                        st.info('Documento não encontrado')
                with col_info:
                    st.markdown(f"**Fornecedor:** {str(row.get('Fornecedor', 'N/A'))}")
                    st.markdown(f"**Descrição:** {str(row.get('Descricao', 'N/A'))}")
                    st.markdown(f"**Valor:** {moeda_br(row.get('Valor_Real', 0))}")
                    st.markdown(f"**Categoria:** {str(row.get('Categoria', 'N/A'))}")
                    st.markdown(f"**Score Divergência:** {int(row.get(SCORE_COL, 0))}")
                    st.markdown(f"**Motivo:** {str(row.get(MOTIVO_COL, 'N/A'))}")
                    if st.button('Analisar com IA', key=f'ia_div_{idx}'):
                        with st.spinner('IA analisando documento...'):
                            prompt_div = f'Analise este documento divergente:\n'
                            prompt_div += f'Fornecedor: {str(row.get("Fornecedor", "N/A"))}\n'
                            prompt_div += f'Descrição: {str(row.get("Descricao", "N/A"))}\n'
                            prompt_div += f'Valor: {moeda_br(row.get("Valor_Real", 0))}\n'
                            prompt_div += f'Score: {int(row.get(SCORE_COL, 0))}\n'
                            prompt_div += f'Motivo: {str(row.get(MOTIVO_COL, "N/A"))}\n'
                            prompt_div += f'\nDê sua análise como auditor sênior. Seja direto.'
                            resp_div, _ = chamar_modelo_ia(prompt_div, contexto_ia, [])
                        st.markdown(f'<div class="ai-card">{html.escape(resp_div or "Erro na análise")}</div>', unsafe_allow_html=True)

with aba_balanco:
    st.markdown('<div class="section-title">Balanço Mensal Consolidado</div>', unsafe_allow_html=True)
    try:
        st.dataframe(preparar_exibicao(df_bal_f), width='stretch', hide_index=True)
    except Exception:
        st.table(preparar_exibicao(df_bal_f).astype(str).head(50))
with aba_cat:
    st.markdown('<div class="section-title">Categorias Mensais</div>', unsafe_allow_html=True)
    if not df_cat_f.empty:
        fig = px.bar(df_cat_f.groupby(['Categoria', 'Grupo'], dropna=False)['Valor'].sum().reset_index().sort_values('Valor', ascending=False).head(20), x='Valor', y='Categoria', color='Grupo', orientation='h', height=520, title='Top categorias', color_discrete_map={'Entrada': COR_ENTRADA, 'Saída': COR_SAIDA})
        formatar_fig(fig, height=520, moeda=True)
        st.plotly_chart(fig, width='stretch')
    try:
        st.dataframe(preparar_exibicao(df_cat_f), width='stretch', hide_index=True)
    except Exception:
        st.table(preparar_exibicao(df_cat_f).astype(str).head(50))
    st.markdown('<div class="section-title">Notas fiscais e comprovantes vinculados</div><div class="section-sub">Imagens extraídas dos PDFs, número da nota, chave de acesso, status da consulta e vínculo por valor com a movimentação.</div>', unsafe_allow_html=True)
    if df_nf_f.empty:
        st.info('Nenhuma nota fiscal ou comprovante foi vinculado às movimentações filtradas ainda.')
    else:
        nf1, nf2, nf3 = st.columns(3)
        with nf1: kpi_card('NFs vinculadas', f'{qtd_nf:,}'.replace(',', '.'), 'Imagens relacionadas a movimentações', icon='NF', accent=COR_CIANO)
        with nf2: kpi_card('Com chave', f'{qtd_nf_chave:,}'.replace(',', '.'), 'Chave de acesso localizada no OCR', icon='44', accent=COR_PRIMARIA)
        with nf3:
            qtd_consulta = int(df_nf_f['Status_Consulta_NF'].fillna('').astype(str).str.contains('HTTP|sucesso', case=False, regex=True).sum()) if 'Status_Consulta_NF' in df_nf_f.columns else 0
            kpi_card('Consultadas', f'{qtd_consulta:,}'.replace(',', '.'), 'Links oficiais/QR consultados automaticamente', icon='OK', accent=COR_ENTRADA)

        if 'Status_Consulta_NF' in df_nf_f.columns:
            status_nf = df_nf_f['Status_Consulta_NF'].fillna('Sem status').astype(str).value_counts().reset_index()
            status_nf.columns = ['Status', 'Quantidade']
            fig = px.bar(status_nf, x='Quantidade', y='Status', orientation='h', height=360, color_discrete_sequence=[COR_CIANO], title='Status das consultas de NF')
            formatar_fig(fig, height=360)
            st.plotly_chart(fig, width='stretch')

        df_nf_view = df_nf_f.reset_index(drop=True).copy()
        df_nf_view['Item'] = df_nf_view.apply(lambda row: f"{row.get('Data', '')} | {row.get('Fornecedor', 'Sem fornecedor') or 'Sem fornecedor'} | {moeda_br(row.get('Valor_Real', 0))} | {str(row.get('Descricao', ''))[:80]}", axis=1)
        item_sel = st.selectbox('Clique/escolha uma nota ou despesa para abrir os detalhes', df_nf_view['Item'].tolist(), index=0)
        row_sel = df_nf_view[df_nf_view['Item'] == item_sel].iloc[0]
        detalhe_ctx = st.popover('Abrir imagem e dados da nota', use_container_width=True) if hasattr(st, 'popover') else st.expander('Abrir imagem e dados da nota', expanded=True)
        with detalhe_ctx:
            d1, d2 = st.columns([1.1, 1])
            with d1:
                caminho_img = str(row_sel.get('Link_NF', '') or '')
                if caminho_img and Path(caminho_img).exists():
                    st.image(caminho_img, caption=Path(caminho_img).name, width='stretch')
                else:
                    st.info('Imagem vinculada não encontrada no disco.')
            with d2:
                st.markdown(f"**Fornecedor:** {html.escape(str(row_sel.get('Fornecedor', '')))}")
                st.markdown(f"**Descrição:** {html.escape(str(row_sel.get('Descricao', '')))}")
                st.markdown(f"**Valor:** {moeda_br(row_sel.get('Valor_Real', 0))}")
                st.markdown(f"**Número NF:** `{html.escape(str(row_sel.get('Numero_NF', '') or 'Não identificado'))}`")
                st.markdown(f"**Chave NF:** `{html.escape(str(row_sel.get('Chave_NF', '') or 'Não identificada'))}`")
                st.markdown(f"**Status:** {html.escape(str(row_sel.get('Status_Consulta_NF', '') or 'Sem status'))}")
                link_origem = str(row_sel.get('Link_Origem_NF', '') or '')
                link_consulta = str(row_sel.get('Link_Consulta_NF', '') or '')
                arquivo_baixado = str(row_sel.get('Arquivo_NF_Baixado', '') or '')
                chave_nf = str(row_sel.get('Chave_NF', '') or '')
                numero_nf = str(row_sel.get('Numero_NF', '') or '')
                cnpj = str(row_sel.get('CNPJ', '') or '')
                fornecedor = str(row_sel.get('Fornecedor', '') or '')
                descricao = str(row_sel.get('Descricao', '') or '')
                categoria = str(row_sel.get('Categoria', '') or '')
                valor = float(row_sel.get('Valor_Real', 0) or 0)
                if link_origem:
                    st.link_button('Abrir link original do balancete', link_origem, width='stretch')
                if link_consulta and link_consulta != link_origem:
                    st.link_button('Abrir link de consulta/documento', link_consulta, width='stretch')
                label_verif, url_verif = gerar_link_verificacao_nf(chave_nf, numero_nf, categoria)
                st.link_button(label_verif, url_verif, width='stretch')
                google_url = f'https://www.google.com/search?q={html.escape(fornecedor or descricao)}+CNPJ+{cnpj}'
                st.link_button('Pesquisar empresa no Google', google_url, width='stretch')
                if cnpj and len(re.sub(r'\D', '', cnpj)) == 14:
                    with st.spinner('Buscando dados da empresa...'):
                        dados_empresa = buscar_empresa_cnpj(cnpj)
                    if dados_empresa:
                        st.markdown(f"**Razão Social:** {html.escape(dados_empresa.get('razao_social', ''))}")
                        st.markdown(f"**Nome Fantasia:** {html.escape(dados_empresa.get('nome_fantasia', ''))}")
                        st.markdown(f"**Situação:** {html.escape(dados_empresa.get('situacao', ''))}")
                        st.markdown(f"**Atividade:** {html.escape(dados_empresa.get('atividade', ''))}")
                        st.markdown(f"**Endereço:** {html.escape(dados_empresa.get('endereco', ''))}")
                if arquivo_baixado and Path(arquivo_baixado).exists():
                    with open(arquivo_baixado, 'rb') as f:
                        st.download_button('Baixar documento arquivado', f, file_name=Path(arquivo_baixado).name, width='stretch')
                if st.button('Explicar com IA', key=f'ia_{item_sel[:30]}'):
                    with st.spinner('Analisando item...'):
                        explicacao = explicar_item_ia(fornecedor, descricao, valor, categoria, cnpj)
                    st.markdown(f'<div class="ai-card"><strong>Análise IA</strong><br>{html.escape(explicacao)}</div>', unsafe_allow_html=True)

        colunas_nf = [c for c in ['Data', 'Fornecedor', 'Descricao', 'Valor_Real', 'Numero_NF', 'Chave_NF', 'Status_Consulta_NF', 'Link_Consulta_NF', 'Link_Origem_NF', 'Arquivo_NF_Baixado', 'Link_NF'] if c in df_nf_f.columns]
        df_display = preparar_exibicao(df_nf_f[colunas_nf]).copy()
        
        # Sanitize: replace inf/-inf with None (Arrow can't handle them)
        df_display = df_display.replace([float('inf'), float('-inf')], None)
        
        # Ensure link columns contain only strings or None
        for col in ['Link_Consulta_NF', 'Link_Origem_NF']:
            if col in df_display.columns:
                df_display[col] = df_display[col].apply(
                    lambda x: str(x) if pd.notna(x) and str(x).strip() != '' else None
                )
        
        try:
            st.dataframe(
                df_display,
                width='stretch',
                hide_index=True,
                column_config={
                    'Link_Consulta_NF': st.column_config.LinkColumn('Link consulta NF'),
                    'Link_Origem_NF': st.column_config.LinkColumn('Link original'),
                    'Valor_Real': st.column_config.NumberColumn('Valor', format='R$ %.2f'),
                },
            )
        except Exception as e:
            st.error(f"Erro ao exibir tabela interativa: {str(e)}")
            try:
                st.dataframe(df_display, width='stretch', hide_index=True)
            except Exception:
                st.table(df_display.astype(str).head(50))

        imagens = [p for p in df_nf_f['Link_NF'].dropna().astype(str).unique().tolist() if Path(p).exists()] if 'Link_NF' in df_nf_f.columns else []
        if imagens:
            st.markdown('<div class="section-title">Amostra das imagens extraídas</div>', unsafe_allow_html=True)
            cols_img = st.columns(3)
            for idx, caminho in enumerate(imagens[:6]):
                with cols_img[idx % 3]:
                    st.image(caminho, caption=Path(caminho).name, width='stretch')

with aba_mov:
    st.markdown('<div class="section-title">Movimentações Analíticas</div>', unsafe_allow_html=True)
    if not df_mov_f.empty and {'Mes_Ano', 'Conta', 'Tipo_Movimento', 'Valor_Entrada', 'Valor_Saida', 'Valor_Transferencia'}.issubset(df_mov_f.columns):
        grp = df_mov_f.groupby(['Mes_Ano', 'Conta', 'Tipo_Movimento'], dropna=False)[['Valor_Entrada', 'Valor_Saida', 'Valor_Transferencia']].sum().reset_index()
        grp['Valor'] = grp.apply(lambda row: row['Valor_Entrada'] if row['Tipo_Movimento'] == 'Entrada' else (row['Valor_Saida'] if row['Tipo_Movimento'] == 'Saída' else row['Valor_Transferencia']), axis=1)
        fig = px.bar(grp, x='Mes_Ano', y='Valor', color='Tipo_Movimento', facet_col='Conta', height=560, title='Movimentação analítica por conta', color_discrete_map={'Entrada': COR_ENTRADA, 'Saída': COR_SAIDA, 'Transferência': COR_TRANSFERENCIA})
        formatar_fig(fig, height=560, moeda=True)
        st.plotly_chart(fig, width='stretch')
    if not df_mov_f.empty and {'Categoria', 'Tipo_Movimento'}.issubset(df_mov_f.columns):
        saidas_detalhe = df_mov_f[df_mov_f['Tipo_Movimento'] == 'Saída'].copy()
        categorias_detalhe = sorted(saidas_detalhe['Categoria'].dropna().astype(str).unique().tolist()) if not saidas_detalhe.empty else []
        if categorias_detalhe:
            cat_sel = st.selectbox('Detalhar categoria/despesa (ex.: obra, manutenção, serviços)', categorias_detalhe)
            detalhes = saidas_detalhe[saidas_detalhe['Categoria'].astype(str) == cat_sel].sort_values('Valor_Real', ascending=False).head(30)
            try:
                st.dataframe(preparar_exibicao(detalhes), width='stretch', hide_index=True)
            except Exception:
                st.table(preparar_exibicao(detalhes).astype(str).head(50))
            if 'Link_NF' in detalhes.columns:
                imgs = [p for p in detalhes['Link_NF'].dropna().astype(str).tolist() if p and Path(p).exists()]
                if imgs:
                    with st.expander(f'Imagens vinculadas em {cat_sel}', expanded=False):
                        cols = st.columns(3)
                        for i, img in enumerate(imgs[:9]):
                            with cols[i % 3]:
                                st.image(img, caption=Path(img).name, width='stretch')
    try:
        st.dataframe(preparar_exibicao(df_mov_f), width='stretch', hide_index=True)
    except Exception:
        st.table(preparar_exibicao(df_mov_f).astype(str).head(50))
with aba_cob:
    st.markdown('<div class="section-title">Composição das Cobranças</div>', unsafe_allow_html=True)
    if not df_cob_f.empty and {'Bloco', 'Valor'}.issubset(df_cob_f.columns):
        fig = px.bar(df_cob_f.groupby('Bloco', dropna=False)['Valor'].sum().reset_index(), x='Bloco', y='Valor', height=420, title='Valor por bloco', color_discrete_sequence=[COR_CIANO])
        formatar_fig(fig, height=420, moeda=True)
        st.plotly_chart(fig, width='stretch')
    try:
        st.dataframe(preparar_exibicao(df_cob_f), width='stretch', hide_index=True)
    except Exception:
        st.table(preparar_exibicao(df_cob_f).astype(str).head(50))
with aba_dash:
    st.markdown('<div class="section-title">Dashboards HTML do motor</div>', unsafe_allow_html=True)
    dashs = dashboards_existentes()
    if not dashs:
        st.info('Nenhum dashboard HTML foi encontrado ainda. Execute a auditoria para gerá-los.')
    else:
        abas_dash = st.tabs([nome for nome, _ in dashs])
        for aba, (nome, arquivo) in zip(abas_dash, dashs):
            with aba:
                with open(arquivo, 'r', encoding='utf-8') as f:
                    html_data = f.read()
                components.html(html_data, height=740, scrolling=True)
with aba_dl:
    st.markdown('<div class="section-title">Downloads dos relatórios</div>', unsafe_allow_html=True)
    existentes = arquivos_download_existentes()
    if not existentes:
        st.info('Nenhum arquivo de saída foi encontrado. Execute a auditoria primeiro.')
    else:
        cols = st.columns(2)
        for i, arq in enumerate(existentes):
            mime = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' if arq.suffix.lower() == '.xlsx' else 'text/csv'
            with cols[i % 2]:
                with open(arq, 'rb') as f:
                    st.download_button(label=f'Baixar {arq.name}', data=f, file_name=arq.name, mime=mime, key=f'dl_{arq.name}', width='stretch')
                st.caption(f'Tamanho: {round(arq.stat().st_size / 1024, 1)} KB')
