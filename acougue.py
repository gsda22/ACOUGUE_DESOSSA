import streamlit as st
import datetime
import pandas as pd
from io import BytesIO
import base64
import streamlit.components.v1 as components
import json
import firebase_admin
from firebase_admin import credentials, firestore

# ==========================================
# CONFIGURAÇÃO DE PÁGINA E ESTILO
# ==========================================
st.set_page_config(page_title="Painel de Prevenção: Açougue", page_icon="🥩", layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stMetricDelta > div { font-size: 1.2rem !important; }
    input::-webkit-outer-spin-button,
    input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
    input[type=number] { -moz-appearance: textfield; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# CONEXÃO COM O BANCO DE DADOS (FIREBASE)
# ==========================================
@st.cache_resource
def init_firebase():
    if not firebase_admin._apps:
        try:
            firebase_secrets = dict(st.secrets["firebase"])
            cred = credentials.Certificate(firebase_secrets)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            return None
    return firestore.client()

db = init_firebase()

# ==========================================
# SINCRONIZAÇÃO E PERSISTÊNCIA (CRUD)
# ==========================================
def carregar_dados_iniciais():
    defaults = {
        "fornecedores": ["Friboi", "Seara", "Masterboi"],
        "pecas_cadastro": ["TRASEIRO", "DIANTEIRO", "CHUPA MOLHO"],
        "lideres": ["João (Líder)", "Carlos (Líder)"],
        "acougueiros": ["Marcos", "José"],
        "prevencao_equipe": ["Fiscal Lucas", "Fiscal Maria"]
    }
    
    if db is not None:
        doc_ref = db.collection('configs').document('cadastros')
        doc = doc_ref.get()
        if doc.exists:
            dados = doc.to_dict()
            for k in defaults.keys(): st.session_state[k] = dados.get(k, defaults[k])
        else:
            doc_ref.set(defaults)
            for k in defaults.keys(): st.session_state[k] = defaults[k]

        recs = []
        for doc in db.collection('recebimentos').stream():
            recs.append(doc.to_dict())
        st.session_state["recebimentos"] = recs
    else:
        for k in defaults.keys():
            if k not in st.session_state: st.session_state[k] = defaults[k]
        if "recebimentos" not in st.session_state: st.session_state["recebimentos"] = []

def add_config(key, item):
    st.session_state[key].append(item)
    if db is not None: db.collection('configs').document('cadastros').update({key: st.session_state[key]})

def rm_config(key, item):
    st.session_state[key].remove(item)
    if db is not None: db.collection('configs').document('cadastros').update({key: st.session_state[key]})

def add_recebimento(novo_registro):
    st.session_state["recebimentos"].append(novo_registro)
    if db is not None: db.collection('recebimentos').document(novo_registro['id']).set(novo_registro)

def del_recebimento(id_rec):
    st.session_state["recebimentos"] = [r for r in st.session_state["recebimentos"] if r["id"] != id_rec]
    if db is not None: db.collection('recebimentos').document(id_rec).delete()

def upd_recebimento(id_rec, nota_atualizada):
    for i, r in enumerate(st.session_state["recebimentos"]):
        if r["id"] == id_rec:
            st.session_state["recebimentos"][i] = nota_atualizada
            break
    if db is not None: db.collection('recebimentos').document(id_rec).set(nota_atualizada)

# INICIALIZAÇÃO DE ESTADOS TEMPORÁRIOS
if "logado" not in st.session_state:
    st.session_state["logado"] = False
    st.session_state["usuario_atual"] = None
    st.session_state["perfil_atual"] = None
if "pecas_temp" not in st.session_state:
    st.session_state["pecas_temp"] = []
if "dados_carregados" not in st.session_state:
    carregar_dados_iniciais()
    st.session_state["dados_carregados"] = True

# ==========================================
# BANCO DE USUÁRIOS E PERMISSÕES
# ==========================================
USUARIOS_SISTEMA = {
    "admin": {"senha": "79318520", "perfil": "ADMIN"},
    "fiscal": {"senha": "1234", "perfil": "PREVENCAO"},
    "lider": {"senha": "1234", "perfil": "OPERACAO"}
}

PERMISSOES_ABAS = {
    "ADMIN": ["📥 1. Lançar Recebimento", "🔪 2. Auditar Desossa", "⚙️ 3. Cadastros", "📊 4. Painel de Acompanhamento", "📂 5. Evidências"],
    "PREVENCAO": ["📥 1. Lançar Recebimento", "🔪 2. Auditar Desossa", "📊 4. Painel de Acompanhamento", "📂 5. Evidências"],
    "OPERACAO": ["📥 1. Lançar Recebimento", "🔪 2. Auditar Desossa"]
}

# ==========================================
# TELA DE LOGIN (BLOQUEIO DO SISTEMA)
# ==========================================
if not st.session_state["logado"]:
    col_vazia1, col_login, col_vazia2 = st.columns([1, 2, 1])
    
    with col_login:
        st.image("https://www.novomixsupermercados.com.br/wp-content/themes/novo-mix/img/logo.png", width=300)
        st.title("🔒 Acesso ao Sistema")
        st.markdown("Controle de Prevenção e Desossa")
        
        with st.form("form_login"):
            usuario_input = st.text_input("Usuário").lower().strip()
            senha_input = st.text_input("Senha", type="password")
            btn_entrar = st.form_submit_button("Entrar no Sistema", type="primary", use_container_width=True)
            
            if btn_entrar:
                if usuario_input in USUARIOS_SISTEMA and USUARIOS_SISTEMA[usuario_input]["senha"] == senha_input:
                    st.session_state["logado"] = True
                    st.session_state["usuario_atual"] = usuario_input
                    st.session_state["perfil_atual"] = USUARIOS_SISTEMA[usuario_input]["perfil"]
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")
    st.stop()

# ==========================================
# FUNÇÕES AUXILIARES E PARÂMETROS
# ==========================================
def botao_copiar_whatsapp(texto):
    b64_texto = base64.b64encode(texto.encode("utf-8")).decode()
    html_code = f"""
    <div style="display: flex; justify-content: left;">
        <button onclick="copyToClipboard()" style="
            background-color: #25D366; color: white; border: none; padding: 12px 24px; 
            text-align: center; font-size: 16px; cursor: pointer; border-radius: 8px;
            font-family: sans-serif; font-weight: bold; box-shadow: 0px 4px 6px rgba(0,0,0,0.1);">
            📲 Copiar Relatório para WhatsApp
        </button>
    </div>
    <script>
    function copyToClipboard() {{
        const decodedText = decodeURIComponent(escape(window.atob('{b64_texto}')));
        const el = document.createElement('textarea');
        el.value = decodedText; document.body.appendChild(el); el.select();
        document.execCommand('copy'); document.body.removeChild(el);
        alert('Copiado com sucesso! Cole no WhatsApp.');
    }}
    </script>
    """
    components.html(html_code, height=70)

CORTES_PARAMETROS = {
    "TRASEIRO": [
        "FILÉ MIGNON", "PATINHO", "CHAN DE DENTRO", "ALCATRA", "FILÉ ESPECIAL (CAPA E CAPOTE)", 
        "CHAN DE FORA", "PICANHA", "PAULISTA", "COSTELA DO FILÉ", "OSSO PATINHO", 
        "OSSO DE PERÚ", "PELE TRASEIRO", "OSSO TRASEIRO", "MUSCULO TRASEIRO", "EMBALAGEM"
    ],
    "DIANTEIRO": [
        "PONTA DE AGULHA (C/ ACEM)", "CRUZ MACHADO", "CUPIM", "PEITO COM OSSO", 
        "PEITO S/ OSSO", "MUSCULO", "PELE DO DIANTEIRO", "OSSO DO DIANTEIRO", "EMBALAGEM"
    ],
    "CHUPA MOLHO": ["CHUPA MOLHO (C/ FRALDINHA)", "PELE", "EMBALAGEM"]
}

def identificar_tipo_peca(nome_peca):
    nome_upper = nome_peca.upper()
    if "TRASEIRO" in nome_upper: return "TRASEIRO"
    if "DIANTEIRO" in nome_upper: return "DIANTEIRO"
    if "CHUPA MOLHO" in nome_upper: return "CHUPA MOLHO"
    return None

# ==========================================
# CABEÇALHO E ALERTA DE BANCO DE DADOS
# ==========================================
if db is None:
    st.error("⚠️ **MODO OFFLINE:** O banco de dados Firebase não está conectado. As informações serão apagadas ao atualizar a página. Configure as chaves no 'Secrets' do Streamlit Cloud.")

col_logo, col_titulo, col_logout = st.columns([1, 4, 1])
with col_logo:
    st.image("https://www.novomixsupermercados.com.br/wp-content/themes/novo-mix/img/logo.png", use_container_width=True)
with col_titulo:
    st.title("Gestão de Prevenção e Desossa")
with col_logout:
    st.markdown(f"👤 **{st.session_state['usuario_atual'].capitalize()}** ({st.session_state['perfil_atual']})")
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state["logado"] = False
        st.session_state["usuario_atual"] = None
        st.session_state["perfil_atual"] = None
        st.rerun()

st.markdown("---")

# ==========================================
# INTERFACE DO USUÁRIO (ABAS DINÂMICAS)
# ==========================================
abas_permitidas = PERMISSOES_ABAS[st.session_state["perfil_atual"]]
objetos_abas = st.tabs(abas_permitidas)
dict_abas = dict(zip(abas_permitidas, objetos_abas))

# ------------------------------------------
# ABA 3: CONFIGURAÇÕES
# ------------------------------------------
if "⚙️ 3. Cadastros" in dict_abas:
    with dict_abas["⚙️ 3. Cadastros"]:
        st.header("Gerenciamento de Cadastros")
        
        def render_cadastro_box(titulo, session_key):
            st.info(titulo)
            novo_item = st.text_input(f"Novo {titulo}", key=f"add_{session_key}")
            if st.button(f"➕ Add", key=f"btn_add_{session_key}", use_container_width=True) and novo_item:
                add_config(session_key, novo_item)
                st.rerun()
                
            st.dataframe(st.session_state[session_key], hide_index=True, use_container_width=True)
            
            if len(st.session_state[session_key]) > 0:
                item_remover = st.selectbox("Remover item", st.session_state[session_key], key=f"sel_rm_{session_key}")
                if st.button("🗑️ Excluir", key=f"btn_rm_{session_key}", use_container_width=True):
                    rm_config(session_key, item_remover)
                    st.rerun()

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1: render_cadastro_box("Fornecedor", "fornecedores")
        with col2: render_cadastro_box("Peça", "pecas_cadastro")
        with col3: render_cadastro_box("Líder", "lideres")
        with col4: render_cadastro_box("Açougueiro", "acougueiros")
        with col5: render_cadastro_box("Prevenção", "prevencao_equipe")

# ------------------------------------------
# ABA 1: NOVO RECEBIMENTO
# ------------------------------------------
if "📥 1. Lançar Recebimento" in dict_abas:
    with dict_abas["📥 1. Lançar Recebimento"]:
        col_a, col_b = st.columns([1, 2])
        
        with col_a:
            st.subheader("📦 Dados da Nota")
            nf = st.text_input("Nº da Nota Fiscal")
            fornecedor = st.selectbox("Fornecedor", st.session_state["fornecedores"])
            data_rec = st.date_input("Data do Recebimento", datetime.date.today())
            lider = st.selectbox("Líder do Açougue (Recebimento)", st.session_state["lideres"])
            prev_recebeu = st.selectbox("Prevenção (Recebimento)", st.session_state["prevencao_equipe"])
            
        with col_b:
            st.subheader("⚖️ Inserir Peças na Nota")
            with st.container(border=True):
                cols_peca = st.columns([3, 2, 2])
                with cols_peca[0]:
                    peca_sel = st.selectbox("Selecione a Peça", st.session_state["pecas_cadastro"], label_visibility="collapsed")
                with cols_peca[1]:
                    peso_sel = st.number_input("Peso (KG)", min_value=0.0, format="%.3f", step=0.001, label_visibility="collapsed")
                with cols_peca[2]:
                    if st.button("➕ Adicionar Peça", use_container_width=True) and peso_sel > 0:
                        st.session_state["pecas_temp"].append({
                            "nome": peca_sel, "peso_recebido": peso_sel, "peso_desossado": 0.0,
                            "detalhes_cortes": {}, "data_desossa": None,
                            "acougueiro_desossa": None, "prev_desossa": None
                        })
                        st.rerun()
                        
            if st.session_state["pecas_temp"]:
                df_temp = pd.DataFrame(st.session_state["pecas_temp"])[["nome", "peso_recebido"]]
                df_temp["peso_recebido"] = df_temp["peso_recebido"].apply(lambda x: f"{x:.3f} kg")
                st.table(df_temp)
                
                if st.button("💾 Gravar Nota Completa", type="primary", use_container_width=True):
                    if not nf:
                        st.error("Preencha a NF!")
                    else:
                        novo_registro = {
                            "id": f"NF{nf}-{data_rec.strftime('%Y%m%d%H%M%S')}", "nf": nf,
                            "fornecedor": fornecedor, "lider": lider, "prev_recebeu": prev_recebeu,
                            "data": data_rec.strftime("%Y-%m-%d"), "pecas": list(st.session_state["pecas_temp"]),
                            "evidencia_nome": None, "evidencia_bytes": None, "evidencia_tipo": None
                        }
                        add_recebimento(novo_registro)
                        st.session_state["pecas_temp"] = []
                        st.success("Nota gravada no banco de dados com sucesso! Vá para a aba de Desossa.")
                        st.rerun()

# ------------------------------------------
# ABA 2: AUDITORIA DE DESOSSA
# ------------------------------------------
if "🔪 2. Auditar Desossa" in dict_abas:
    with dict_abas["🔪 2. Auditar Desossa"]:
        if not st.session_state["recebimentos"]:
            st.info("Nenhuma Nota Fiscal cadastrada ou carregada do banco de dados.")
        else:
            opcoes_rec = {r["id"]: r for r in st.session_state["recebimentos"]}
            rec_selecionado = st.selectbox("🔍 Selecione a Nota para Auditar", list(opcoes_rec.keys()), format_func=lambda x: f"NF: {opcoes_rec[x]['nf']} | {opcoes_rec[x]['fornecedor']}")
            dados_rec = opcoes_rec[rec_selecionado]
            
            data_exibicao = datetime.datetime.strptime(dados_rec['data'], "%Y-%m-%d").strftime("%d/%m/%Y")
            
            col_cabecalho, col_upload, col_excluir = st.columns([3, 2, 1])
            with col_cabecalho:
                st.write(f"**Data Recebimento:** {data_exibicao} | **Prev. Recebimento:** {dados_rec['prev_recebeu']}")
                if dados_rec.get("evidencia_nome"):
                    st.success(f"📎 Evidência salva na nuvem: {dados_rec['evidencia_nome']}")
            
            with col_
