from datetime import datetime
import os
import streamlit as st
import psycopg2
import pandas as pd
from psycopg2 import pool
import atexit

# Inicialização do pool de conexões
class Database:
    def __init__(self):
        self.db_pool = None
        self.init_db_pool()

    def init_db_pool(self):
        try:
            self.db_pool = psycopg2.pool.SimpleConnectionPool(
                1, 2,
                dbname=os.getenv("PG_DB", "db_z0bb"),
                user=os.getenv("PG_USER", "db_z0bb_user"),
                password=os.getenv("PG_PASS", "Tur9VycRGOxEMtHCtrjfXZFBolw2gtjS"),
                host=os.getenv("PG_HOST", "dpg-cuou4jl2ng1s73ecudj0-a.oregon-postgres.render.com"),
                port=os.getenv("PG_PORT", "5432"),
                sslmode="require",
                connect_timeout=10
            )
            print("✅ Pool de conexões inicializado!")
        except Exception as e:
            print(f"❌ Erro ao criar o pool de conexões: {e}")

    def get_connection(self):
        if self.db_pool is None:
            raise Exception("⚠️ O pool de conexões não foi inicializado!")
        return self.db_pool.getconn()

    def release_connection(self, conn):
        if conn and self.db_pool:
            self.db_pool.putconn(conn)

    def close_pool(self):
        if self.db_pool:
            self.db_pool.closeall()
            print("✅ Pool de conexões fechado!")

# Inicializa banco de dados
db = Database()
atexit.register(db.close_pool)

def execute_query(query, params=None, fetch=False):
    conn = db.get_connection()
    if conn is None:
        st.error("❌ Não foi possível obter conexão com o banco!")
        return None
    
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params or ())
            if fetch:
                return cursor.fetchall()
            conn.commit()
    except psycopg2.Error as e:
        st.error(f"❌ Erro no banco de dados: {e}")
        return None
    finally:
        db.release_connection(conn)

def create_tables():
    execute_query("""
        CREATE TABLE IF NOT EXISTS documentos (
            id SERIAL PRIMARY KEY,
            tipo TEXT,
            numero TEXT UNIQUE,
            destino TEXT,
            data_emissao TEXT
        )
    ""
    )

def get_next_number(tipo):
    sequence_name = tipo.lower().replace(" ", "_")
    execute_query(f"CREATE SEQUENCE IF NOT EXISTS {sequence_name} START WITH 1 INCREMENT BY 1;")
    
    conn = db.get_connection()
    if conn is None:
        return None
    
    try:
        conn.set_session(autocommit=True)
        with conn.cursor() as cursor:
            cursor.execute(f"SELECT nextval('{sequence_name}')")
            count = cursor.fetchone()[0]
            return f"{count:03d}/{datetime.now().year}"
    finally:
        db.release_connection(conn)

def save_document(tipo, destino, data_emissao):
    for _ in range(5):
        numero = get_next_number(tipo)
        if not numero:
            return None
        
        data_formatada = datetime.strptime(data_emissao, "%d/%m/%Y").strftime("%Y-%m-%d")
        query = """
            INSERT INTO documentos (tipo, numero, destino, data_emissao)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (numero) DO UPDATE
            SET destino = EXCLUDED.destino
            RETURNING numero;
        """
        resultado = execute_query(query, (tipo, numero, destino, data_formatada), fetch=True)
        if resultado:
            return resultado[0][0]
    
    return None

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

def login():
    st.sidebar.image("imagens/brasao.png", width=150)
    st.sidebar.markdown("## 🔒 Login")
    username = st.sidebar.text_input("Usuário", key="login_user")
    password = st.sidebar.text_input("Senha", type="password", key="login_pass")
    if st.sidebar.button("Entrar", key="login_button"):
        if username == os.getenv("APP_USER", "DRITAPIPOCA") and password == os.getenv("APP_PASS", "Itapipoca2024"):
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
                    numero = save_document(tipo, destino, data_emissao)
                    if numero:
                        st.success(f"Número {numero} gerado com sucesso para {tipo}!")
                        st.code(numero, language="text")
                    else:
                        st.error("Erro ao gerar número.")
                else:
                    st.error("Por favor, informe o destino.")

        if menu == "Histórico":
            st.title("📜 Histórico de Documentos")
            conn = db.get_connection()
            df = pd.read_sql_query("SELECT tipo, numero, data_emissao, destino FROM documentos ORDER BY id DESC", conn)
            db.release_connection(conn)
            if not df.empty:
                filtro_tipo = st.selectbox("Filtrar por Tipo", ["Todos"] + sorted(df['tipo'].unique()), key="filter_type")
                if filtro_tipo != "Todos":
                    df = df[df['tipo'] == filtro_tipo]
                st.dataframe(df, height=300)
            else:
                st.warning("Nenhum documento encontrado.")

if __name__ == "__main__":
    main()
