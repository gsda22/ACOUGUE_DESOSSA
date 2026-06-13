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
            
            with col_upload:
                evidencia = st.file_uploader("📸 Anexar Evidência da Desossa", type=['png', 'jpg', 'jpeg', 'webp', 'bmp'], label_visibility="collapsed", key=f"up_{rec_selecionado}")
                if evidencia is not None:
                    if dados_rec.get("evidencia_nome") != evidencia.name:
                        nota_atualizada = dados_rec.copy()
                        nota_atualizada["evidencia_nome"] = evidencia.name
                        nota_atualizada["evidencia_bytes"] = evidencia.getvalue()
                        nota_atualizada["evidencia_tipo"] = evidencia.type
                        upd_recebimento(rec_selecionado, nota_atualizada)
                        st.success("Evidência anexada! Vá para a Aba Evidências para consultar.")
                        st.rerun()

            with col_excluir:
                if st.button("🗑️ Excluir Nota", type="secondary", use_container_width=True):
                    del_recebimento(rec_selecionado)
                    st.rerun()
            
            st.markdown("---")
            
            for idx, peca in enumerate(dados_rec["pecas"]):
                tipo_peca = identificar_tipo_peca(peca['nome'])
                
                with st.expander(f"🔪 {peca['nome']} | Recebido: {peca['peso_recebido']:.3f} kg", expanded=True):
                    with st.form(f"form_cortes_{idx}"):
                        st.markdown("**Responsáveis por esta desossa:**")
                        col_resp1, col_resp2, col_resp3 = st.columns(3)
                        data_des = col_resp1.date_input("Data da Desossa", datetime.date.today())
                        acoug_des = col_resp2.selectbox("Açougueiro", st.session_state["acougueiros"])
                        prev_des = col_resp3.selectbox("Prevenção (Acompanhou)", st.session_state["prevencao_equipe"])
                        
                        st.markdown("---")
                        valores_cortes = {}
                        
                        if tipo_peca and tipo_peca in CORTES_PARAMETROS:
                            cortes_esperados = CORTES_PARAMETROS[tipo_peca]
                            for corte in cortes_esperados:
                                valor_atual = peca.get('detalhes_cortes', {}).get(corte, 0.0)
                                valores_cortes[corte] = st.number_input(corte, min_value=0.0, format="%.3f", step=0.001, value=float(valor_atual))
                                
                            soma_desossa = sum(valores_cortes.values())
                        else:
                            st.warning("Peça sem parâmetros. Insira o peso total manual.")
                            soma_desossa = st.number_input("Peso Total Final (KG)", min_value=0.0, format="%.3f", step=0.001, value=float(peca['peso_desossado']))

                        st.markdown("---")
                        salvar_desossa = st.form_submit_button("💾 Salvar Auditoria e Sincronizar na Nuvem", type="primary", use_container_width=True)
                        
                        if salvar_desossa:
                            nota_atualizada = dados_rec.copy()
                            nota_atualizada["pecas"][idx]["detalhes_cortes"] = valores_cortes
                            nota_atualizada["pecas"][idx]["peso_desossado"] = soma_desossa
                            nota_atualizada["pecas"][idx]["data_desossa"] = data_des.strftime("%d/%m/%Y")
                            nota_atualizada["pecas"][idx]["acougueiro_desossa"] = acoug_des
                            nota_atualizada["pecas"][idx]["prev_desossa"] = prev_des
                            upd_recebimento(rec_selecionado, nota_atualizada)
                            st.success("Dados salvos com segurança!")
                            st.rerun()

                    col_res1, col_res2, col_res3 = st.columns(3)
                    div = peca['peso_recebido'] - peca['peso_desossado']
                    
                    col_res1.metric("Peso Recebido", f"{peca['peso_recebido']:.3f} kg")
                    col_res2.metric("Total Desossado", f"{peca['peso_desossado']:.3f} kg")
                    
                    if peca['peso_desossado'] > 0:
                        if div > 0: col_res3.metric("Quebra (Falta)", f"{div:.3f} kg", f"-{div:.3f} kg", delta_color="normal")
                        elif div < 0: col_res3.metric("Sobra", f"{abs(div):.3f} kg", f"+{abs(div):.3f} kg", delta_color="normal")
                        else: col_res3.metric("Divergência", "0.000 kg", "Exato", delta_color="off")

# ------------------------------------------
# ABA 4: PAINEL DE ACOMPANHAMENTO E RELATÓRIOS
# ------------------------------------------
if "📊 4. Painel de Acompanhamento" in dict_abas:
    with dict_abas["📊 4. Painel de Acompanhamento"]:
        notas_pendentes, notas_parciais, notas_concluidas = [], [], []
        
        for r in st.session_state["recebimentos"]:
            total_pecas = len(r["pecas"])
            pecas_desossadas = sum(1 for p in r["pecas"] if p.get("peso_desossado", 0) > 0)
            
            if pecas_desossadas == 0: notas_pendentes.append(r)
            elif pecas_desossadas == total_pecas: notas_concluidas.append(r)
            else: notas_parciais.append(r)

        st.header("📋 Status das Notas Fiscais")
        
        col_p1, col_p2, col_p3 = st.columns(3)
        col_p1.metric("🔴 Pendentes (Aguardando Desossa)", len(notas_pendentes))
        col_p2.metric("🟡 Parcialmente Desossadas", len(notas_parciais))
        col_p3.metric("🟢 Concluídas (Totalmente Auditadas)", len(notas_concluidas))
        
        with st.expander("Ver detalhes dos Status"):
            c_p1, c_p2, c_p3 = st.columns(3)
            with c_p1:
                for n in notas_pendentes: st.write(f"- NF: {n['nf']} ({n['fornecedor']})")
            with c_p2:
                for n in notas_parciais: st.write(f"- NF: {n['nf']} ({n['fornecedor']})")
            with c_p3:
                for n in notas_concluidas: st.write(f"- NF: {n['nf']} ({n['fornecedor']})")

        st.markdown("---")
        st.header("📊 Filtro e Exportação de Dados")
        
        col_filtro1, col_filtro2 = st.columns(2)
        data_inicio = col_filtro1.date_input("Data Inicial", datetime.date.today() - datetime.timedelta(days=30))
        data_fim = col_filtro2.date_input("Data Final", datetime.date.today())
        
        linhas_relatorio = []
        total_recebido_geral = total_desossado_geral = 0.0
        
        for r in st.session_state["recebimentos"]:
            data_rec_obj = datetime.datetime.strptime(r["data"], "%Y-%m-%d").date()
            if data_inicio <= data_rec_obj <= data_fim:
                for p in r["pecas"]:
                    div = p["peso_recebido"] - p["peso_desossado"]
                    perc = (div / p["peso_recebido"]) * 100 if p["peso_recebido"] > 0 else 0
                    
                    if p["peso_desossado"] > 0:
                        total_recebido_geral += p["peso_recebido"]
                        total_desossado_geral += p["peso_desossado"]
                    
                    linhas_relatorio.append({
                        "NF": r["nf"], "Fornecedor": r["fornecedor"],
                        "Data Recebimento": data_rec_obj.strftime("%d/%m/%Y"), "Peça": p["nome"],
                        "Data Desossa": p.get("data_desossa", "Pendente"),
                        "Açougueiro": p.get("acougueiro_desossa", "Pendente"),
                        "Prevenção (Auditor)": p.get("prev_desossa", "Pendente"),
                        "Peso Recebido (KG)": p["peso_recebido"], "Peso Desossado (KG)": p["peso_desossado"],
                        "Divergência (KG)": round(div, 3), "Quebra (%)": round(perc, 3),
                        "Evidência": r.get("evidencia_nome", "Não anexada")
                    })
                
        if not linhas_relatorio:
            st.info("Nenhum dado registrado para o período selecionado.")
        else:
            quebra_geral = total_recebido_geral - total_desossado_geral
            perc_geral = (quebra_geral / total_recebido_geral * 100) if total_recebido_geral > 0 else 0
            
            col_met1, col_met2, col_met3 = st.columns(3)
            col_met1.metric("Volume Total Auditado (Período)", f"{total_recebido_geral:.3f} kg")
            col_met2.metric("Rendimento Total (Período)", f"{total_desossado_geral:.3f} kg")
            col_met3.metric("Quebra Global (Período)", f"{quebra_geral:.3f} kg", f"{perc_geral:.3f}%", delta_color="inverse")
            
            st.markdown("---")
            df_relatorio = pd.DataFrame(linhas_relatorio)
            st.dataframe(df_relatorio.style.format({
                "Peso Recebido (KG)": "{:.3f}", "Peso Desossado (KG)": "{:.3f}", 
                "Divergência (KG)": "{:.3f}", "Quebra (%)": "{:.3f}"
            }), use_container_width=True)
            
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_relatorio.to_excel(writer, index=False, sheet_name='Historico_Desossa')
            
            st.download_button(
                label="📥 Baixar Histórico Filtrado (Excel .xlsx)",
                data=buffer.getvalue(), file_name="Historico_Desossa.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
            
            st.markdown("---")
            st.subheader("📲 Compartilhar no WhatsApp")
            tipo_wpp = st.radio("Selecione o que deseja copiar:", ["Resumo do Período Filtrado", "Detalhes de uma Nota Específica (NF)"], horizontal=True)
            texto_wpp = ""
            
            if tipo_wpp == "Resumo do Período Filtrado":
                texto_wpp += f"🏪 *PREVENÇÃO DE PERDAS - LOJA 16-7*\n📊 *RESUMO DO AÇOUGUE*\n"
                texto_wpp += f"📅 Período: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}\n\n"
                texto_wpp += f"🥩 *Total Recebido/Auditado:* {total_recebido_geral:.3f} kg\n"
                texto_wpp += f"🔪 *Total Desossado/Rendimento:* {total_desossado_geral:.3f} kg\n"
                if quebra_geral > 0: texto_wpp += f"🔻 *Quebra Global:* {quebra_geral:.3f} kg ({perc_geral:.3f}%)\n"
                elif quebra_geral < 0: texto_wpp += f"🔺 *Sobra Global:* {abs(quebra_geral):.3f} kg ({abs(perc_geral):.3f}%)\n"
                else: texto_wpp += f"✅ *Divergência Global:* ZERO\n"
                botao_copiar_whatsapp(texto_wpp)
                
            elif tipo_wpp == "Detalhes de uma Nota Específica (NF)":
                nfs_disponiveis = df_relatorio['NF'].unique()
                if len(nfs_disponiveis) > 0:
                    nf_selecionada = st.selectbox("Selecione a Nota Fiscal", nfs_disponiveis)
                    dados_rec = next((r for r in st.session_state["recebimentos"] if r["nf"] == nf_selecionada), None)
                    if dados_rec:
                        data_rec_fmt = datetime.datetime.strptime(dados_rec['data'], "%Y-%m-%d").strftime("%d/%m/%Y")
                        texto_wpp += f"🏪 *PREVENÇÃO DE PERDAS - LOJA 16-7*\n🧾 *RECEBIMENTO DE AÇOUGUE - NF: {dados_rec['nf']}*\n"
                        texto_wpp += f"📅 *Data Rec.:* {data_rec_fmt}\n🏢 *Fornecedor:* {dados_rec['fornecedor']}\n"
                        texto_wpp += f"👨‍🍳 *Líder:* {dados_rec['lider']} | 🕵️‍♂️ *Prev:* {dados_rec['prev_recebeu']}\n"
                        if dados_rec.get("evidencia_nome"): texto_wpp += f"📎 *Evidência anexada no sistema*\n\n"
                        else: texto_wpp += f"\n"
                        texto_wpp += "🥩 *DETALHAMENTO DE DESOSSA:*\n"
                        for peca in dados_rec['pecas']:
                            texto_wpp += f"🔸 *{peca['nome']}* (Rec: {peca['peso_recebido']:.3f}kg)\n"
                            if peca['peso_desossado'] > 0:
                                texto_wpp += f"  🧑‍🔧 Desossado por: {peca.get('acougueiro_desossa', 'N/A')}\n"
                                texto_wpp += f"  👀 Acompanhado por: {peca.get('prev_desossa', 'N/A')}\n"
                                div = peca['peso_recebido'] - peca['peso_desossado']
                                porc = (div / peca['peso_recebido']) * 100 if peca['peso_recebido'] > 0 else 0
                                texto_wpp += f"  👉 Rendimento Final: {peca['peso_desossado']:.3f}kg\n"
                                if div > 0: texto_wpp += f"  🔻 *QUEBRA:* {div:.3f}kg ({porc:.3f}%)\n\n"
                                elif div < 0: texto_wpp += f"  🔺 *SOBRA:* {abs(div):.3f}kg ({abs(porc):.3f}%)\n\n"
                                else: texto_wpp += f"  ✅ *DIVERGÊNCIA:* ZERO\n\n"
                            else:
                                texto_wpp += f"  ⏳ *Status:* Pendente de desossa\n\n"
                        botao_copiar_whatsapp(texto_wpp)

# ------------------------------------------
# ABA 5: VISUALIZADOR DE EVIDÊNCIAS
# ------------------------------------------
if "📂 5. Evidências" in dict_abas:
    with dict_abas["📂 5. Evidências"]:
        st.header("📂 Galeria de Evidências Fotográficas")
        st.markdown("Filtre e visualize as fotos sincronizadas com o banco de dados.")
        
        col_filtro_ev1, col_filtro_ev2, col_filtro_ev3 = st.columns(3)
        data_inicio_ev = col_filtro_ev1.date_input("Data Inicial", datetime.date.today() - datetime.timedelta(days=30), key="ev_d1")
        data_fim_ev = col_filtro_ev2.date_input("Data Final", datetime.date.today(), key="ev_d2")
        nf_filtro_ev = col_filtro_ev3.text_input("Filtrar por NF (Opcional)", key="ev_nf").strip()
        
        st.markdown("---")
        
        recs_com_evidencia = []
        for r in st.session_state["recebimentos"]:
            if r.get("evidencia_bytes"):
                data_rec_obj = datetime.datetime.strptime(r["data"], "%Y-%m-%d").date()
                if data_inicio_ev <= data_rec_obj <= data_fim_ev:
                    if not nf_filtro_ev or nf_filtro_ev in r["nf"]:
                        recs_com_evidencia.append(r)
        
        if not recs_com_evidencia:
            st.info("Nenhuma imagem encontrada para os filtros selecionados.")
        else:
            for r in recs_com_evidencia:
                data_rec_fmt = datetime.datetime.strptime(r['data'], "%Y-%m-%d").strftime("%d/%m/%Y")
                
                with st.container(border=True):
                    col_img, col_info, col_acao = st.columns([1.5, 3, 1])
                    
                    with col_img:
                        if "image" in r["evidencia_tipo"]:
                            st.image(r["evidencia_bytes"], width=150)
                            
                    with col_info:
                        st.subheader(f"🧾 NF: {r['nf']}")
                        st.write(f"**Fornecedor:** {r['fornecedor']} | **Data:** {data_rec_fmt}")
                        st.write(f"**Arquivo:** `{r['evidencia_nome']}`")
                            
                    with col_acao:
                        st.download_button(
                            label="📥 Baixar Imagem",
                            data=r["evidencia_bytes"],
                            file_name=r["evidencia_nome"],
                            mime=r["evidencia_tipo"],
                            key=f"dl_btn_ev_{r['id']}",
                            use_container_width=True,
                            type="primary"
                        )
