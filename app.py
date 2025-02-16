from datetime import datetime
import os
import time
import unicodedata
import re
import streamlit as st
import psycopg2
import pandas as pd
from contextlib import closing

# Função para criar uma conexão com o banco de dados
def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("PG_DB", "db_z0bb"),
        user=os.getenv("PG_USER", "db_z0bb_user"),
        password=os.getenv("PG_PASS", "Tur9VycRGOxEMtHCtrjfXZFBolw2gtjS"),
        host=os.getenv("PG_HOST", "dpg-cuou4jl2ng1s73ecudj0-a.oregon-postgres.render.com"),
        port=os.getenv("PG_PORT", "5432"),
        sslmode="require",  
        connect_timeout=10  
    )

# Função para normalizar o nome da sequência
def normalizar_nome(nome):
    return nome.replace(" ", "_").replace("-", "_").lower()

# Função para executar queries no banco de dados
def execute_query(query, params=None, fetch=False):
    try:
        with closing(get_db_connection()) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params or ())
                if fetch:
                    return cursor.fetchall()
                conn.commit()
    except psycopg2.Error as e:
        st.error(f"Erro no banco de dados: {e}")
        return None

# Função para formatar a data para o padrão que o PostgreSQL aceita (YYYY-MM-DD)
def formatar_data(data_str):
    try:
        data_obj = datetime.strptime(data_str, "%d/%m/%Y")
        return data_obj.strftime("%Y-%m-%d")  # Formata para YYYY-MM-DD
    except ValueError:
        return None  # Retorna None caso não consiga converter a data

# Criar tabelas e sequências se não existirem
def create_tables():
    tipos = [
        "OFICIO", "CARTA_PRECATORIA", "DESPACHO", "PROTOCOLO", "ORDEM_DE_MISSAO", 
        "RELATORIO_POLICIAL", "VERIFICACAO_DE_PROCEDENCIA_DE_INFORMACAO_VPI", 
        "CARTA_PRECATORIA_EXPEDIDA", "CARTA_PRECATORIA_RECEBIDA", "INTIMACAO"
    ]
    
    # Criar a tabela documentos
    execute_query("""
        CREATE TABLE IF NOT EXISTS documentos (
            id SERIAL PRIMARY KEY,
            tipo TEXT,
            numero TEXT UNIQUE,
            destino TEXT,
            data_emissao TEXT
        )
    """)
    
    # Criar as sequências para cada tipo de documento
    for tipo in tipos:
        sequence_name = normalizar_nome(tipo)
        execute_query(f"CREATE SEQUENCE IF NOT EXISTS {sequence_name} START WITH 1 INCREMENT BY 1;")
        execute_query(f"ALTER SEQUENCE {sequence_name} OWNED BY documentos.id;")

# Chamar a função para criar as tabelas e sequências
create_tables()

def ensure_sequence(sequence_name):
    """Garante que a sequência existe e está correta."""
    execute_query(f"""
        CREATE SEQUENCE IF NOT EXISTS {sequence_name}
        START WITH 1
        INCREMENT BY 1
        CACHE 1;
    """)

def get_next_number(tipo):
    """Gera o próximo número sequencial de um documento do tipo informado"""
    sequence_name = normalizar_nome(tipo)
    ensure_sequence(sequence_name)

    with get_db_connection() as conn:
        conn.set_session(autocommit=True)  # 🚀 Garante autocommit
        with conn.cursor() as cursor:
            cursor.execute(f"SELECT nextval('{sequence_name}')")  # Obtém próximo número
            count = cursor.fetchone()[0]

            numero = f"{count:03d}/{datetime.now().year}"  # Formata para 001/2025
            st.write(f"🔍 Sequência: {sequence_name}, Número Gerado: {numero}")

            # Verifica se esse número já existe
            cursor.execute("SELECT 1 FROM documentos WHERE numero = %s", (numero,))
            exists = cursor.fetchone()

            if not exists:
                return numero  # ✅ Retorna imediatamente!

    st.error("🚨 Nenhum número retornado (primeira tentativa falhou)!")
    return None

def save_document(tipo, destino, data_emissao):
    """Salva o documento gerando novo número se houver conflito."""
    sequence_name = normalizar_nome(tipo)
    ensure_sequence(sequence_name)

    for tentativa in range(5):
        try:
            numero = get_next_number(tipo)
            if not numero:
                st.error("❌ get_next_number() retornou None!")
                return None

            # Formatar a data antes de inseri-la no banco
            data_emissao_formatada = formatar_data(data_emissao)
            if not data_emissao_formatada:
                st.error("🚨 Formato de data inválido. Use DD/MM/YYYY.")
                return None

            query = """
            INSERT INTO documentos (tipo, numero, destino, data_emissao)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (numero) DO UPDATE
            SET destino = EXCLUDED.destino
            RETURNING numero;
            """

            resultado = execute_query(query, (tipo, numero, destino, data_emissao_formatada), fetch=True)
            if resultado:
                st.success(f"✅ Documento salvo: {resultado[0][0]}")
                return resultado[0][0]

            st.warning(f"⚠️ Conflito para número {numero}, tentando novamente...")
        except psycopg2.IntegrityError:
            st.error("🚨 Erro de integridade. Tentando novamente...")
            continue

        time.sleep(0.2)

    st.error("❌ Falha após 5 tentativas.")
    return None


# Inicializa o estado de login
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

def login():
    st.sidebar.image("imagens/brasao.png", width=150)
    st.sidebar.markdown("## 🔒 Login")

    username = st.sidebar.text_input("Usuário", key="login_user")
    password = st.sidebar.text_input("Senha", type="password", key="login_pass")

    if st.sidebar.button("Entrar", key="login_button"):
        correct_user = os.getenv("APP_USER", "DRITAPIPOCA")
        correct_password = os.getenv("APP_PASS", "Itapipoca2024")
        if username == correct_user and password == correct_password:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.sidebar.error("Usuário ou senha incorretos!")

def main():
    
    if not st.session_state["authenticated"]:
        login()
    else:
        st.sidebar.image("imagens/brasao.png", width=150)
        st.sidebar.header("📄 Menu")
        menu = st.sidebar.selectbox("Escolha uma opção", ["Gerar Documento", "Histórico", "Sair"], key="menu_select")

        if menu == "Gerar Documento":
            st.title("📄 Numerador de Documentos")

            with st.form("form_documento"):
                tipo = st.selectbox("📌 Tipo de Documento", [
                    "Oficio", "Protocolo", "Despacho", "Ordem de Missao", "Relatorio Policial",
                    "Verificacao de Procedencia de Informacao - VPI", "Carta Precatoria Expedida",
                    "Carta Precatoria Recebida", "Intimacao"
                ], key="doc_type")

                destino = st.text_input("✉️ Destino", key="doc_destino")
                data_emissao = datetime.today().strftime('%d/%m/%Y')
                st.text(f"📅 Data de Emissão: {data_emissao}")

                submit_button = st.form_submit_button(label="✅ Gerar Número")

            if submit_button:
                if destino.strip():
                    try:
                        numero = save_document(tipo, destino, data_emissao)
                        st.success(f"Número {numero} gerado com sucesso para o tipo {tipo}!")
                        st.code(numero, language="text")
                    except Exception as e:
                        st.error(f"Erro ao gerar número: {e}")
                else:
                    st.error("Por favor, informe o destino.")
        elif menu == "Histórico":
            st.title("📜 Histórico de Documentos")
            with get_db_connection() as conn:
                df = pd.read_sql_query("SELECT tipo, numero, data_emissao, destino FROM documentos ORDER BY id DESC", conn)
            if not df.empty:
                filtro_tipo = st.selectbox("Filtrar por Tipo", ["Todos"] + sorted(df['tipo'].unique()), key="filter_type")
                if filtro_tipo != "Todos":
                    df = df[df['tipo'] == filtro_tipo]
                st.dataframe(df, height=300)
            else:
                st.warning("Nenhum documento encontrado.")
        elif menu == "Sair":
            st.session_state["authenticated"] = False
            st.rerun()

if __name__ == "__main__":
    main()
