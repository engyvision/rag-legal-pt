"""Streamlit frontend for Portuguese Legal Assistant."""

import streamlit as st
import requests
import os
from datetime import datetime
import json

# Configuration
RETRIEVAL_SERVICE_URL = os.getenv(
    "RETRIEVAL_SERVICE_URL", "http://localhost:8000")
API_BASE = f"{RETRIEVAL_SERVICE_URL}/api/v1"

# Page configuration
st.set_page_config(
    page_title="Assistente Jurídico Português",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        color: #1f4788;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stButton>button {
        background-color: #1f4788;
        color: white;
    }
    .source-box {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 0.5rem;
    }
    .answer-box {
        background-color: #e8f4f9;
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "search_history" not in st.session_state:
    st.session_state.search_history = []


def query_backend(query: str, use_llm: bool = True, top_k: int = 5):
    """Send query to backend service."""
    try:
        response = requests.post(
            f"{API_BASE}/query",
            json={
                "query": query,
                "use_llm": use_llm,
                "top_k": top_k
            }
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Erro ao processar consulta: {str(e)}")
        return None


def main():
    """Main application."""
    # Header
    st.markdown('<h1 class="main-header">⚖️ Assistente Jurídico Português</h1>',
                unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.header("Configurações")

        search_mode = st.radio(
            "Modo de Pesquisa",
            ["Resposta Completa (com IA)", "Apenas Documentos"],
            help="Escolha entre obter uma resposta elaborada pela IA ou apenas os documentos relevantes"
        )

        num_results = st.slider(
            "Número de Resultados",
            min_value=1,
            max_value=10,
            value=5,
            help="Quantidade de documentos relevantes a retornar"
        )

        st.divider()

        # Statistics
        if st.button("📊 Ver Estatísticas"):
            try:
                stats = requests.get(f"{API_BASE}/stats").json()
                st.metric("Total de Documentos", stats["total_documents"])
                st.metric("Total de Vetores", stats["total_vectors"])
            except:
                st.error("Não foi possível carregar estatísticas")

        st.divider()

        # About
        st.header("Sobre")
        st.info(
            "Este assistente utiliza IA para ajudar com questões "
            "relacionadas à legislação portuguesa. Os dados são "
            "obtidos do Diário da República e outras fontes oficiais."
        )

    # Main content area
    col1, col2 = st.columns([2, 1])

    with col1:
        # Query input
        st.subheader("Faça sua pergunta sobre a legislação portuguesa")

        query = st.text_area(
            "Pergunta:",
            placeholder="Ex: Quais são os requisitos para constituir uma empresa em Portugal?",
            height=100,
            key="query_input"
        )

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            search_button = st.button(
                "🔍 Pesquisar", type="primary", use_container_width=True)
        with col_btn2:
            clear_button = st.button("🗑️ Limpar", use_container_width=True)

        if clear_button:
            st.session_state.messages = []
            st.session_state.search_history = []
            st.rerun()

        if search_button and query:
            # Add to history
            st.session_state.search_history.append({
                "query": query,
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })

            # Show loading
            with st.spinner("Pesquisando na legislação portuguesa..."):
                use_llm = search_mode == "Resposta Completa (com IA)"
                result = query_backend(query, use_llm, num_results)

            if result:
                # Display answer
                if use_llm and "answer" in result:
                    st.markdown("### 💡 Resposta")
                    st.markdown(
                        f'<div class="answer-box">{result["answer"]}</div>',
                        unsafe_allow_html=True
                    )

                # Display sources
                st.markdown("### 📚 Fontes Relevantes")
                for i, source in enumerate(result.get("sources", [])):
                    with st.expander(f"Fonte {i+1}: {source.get('title', 'Documento')}"):
                        st.write(
                            f"**Texto:** {source.get('text', '')[:500]}...")
                        if "metadata" in source:
                            st.write("**Metadados:**")
                            st.json(source["metadata"])
                        if "score" in source:
                            st.progress(
                                source["score"], text=f"Relevância: {source['score']:.2%}")

    with col2:
        # Search history
        st.subheader("📜 Histórico de Pesquisas")

        if st.session_state.search_history:
            for item in reversed(st.session_state.search_history[-10:]):
                st.markdown(
                    f"**{item['timestamp']}**  \n{item['query'][:50]}...",
                    help=item['query']
                )
        else:
            st.info("Nenhuma pesquisa realizada ainda")

    # File upload section (Stage 2)
    with st.expander("📄 Análise de Contratos (Beta)", expanded=False):
        st.info(
            "Faça upload de um contrato para identificar leis aplicáveis, "
            "obter resumos e identificar possíveis problemas."
        )

        uploaded_file = st.file_uploader(
            "Escolha um arquivo",
            type=["pdf", "txt", "docx"],
            help="Formatos suportados: PDF, TXT, DOCX"
        )

        if uploaded_file:
            analysis_type = st.selectbox(
                "Tipo de Análise",
                ["Análise Completa", "Apenas Resumo",
                    "Verificação de Conformidade"]
            )

            if st.button("Analisar Contrato"):
                with st.spinner("Analisando contrato..."):
                    # TODO: Implement contract analysis
                    st.warning("Funcionalidade em desenvolvimento")


if __name__ == "__main__":
    main()
