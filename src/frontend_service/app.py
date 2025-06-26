"""Streamlit frontend for Portuguese Legal Assistant."""

import streamlit as st
import requests
import os
from datetime import datetime
import json

# Configuration
RETRIEVAL_SERVICE_URL = os.getenv("RETRIEVAL_SERVICE_URL", "http://localhost:8000")
API_BASE = f"{RETRIEVAL_SERVICE_URL}/api/v1"

# Page configuration - will be updated after language selection
st.set_page_config(
    page_title="Portuguese Legal Assistant / Assistente Jurídico Português",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown(
    """
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
        color: #1f4788;
    }
</style>
""",
    unsafe_allow_html=True,
)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "search_history" not in st.session_state:
    st.session_state.search_history = []
if "language" not in st.session_state:
    st.session_state.language = "pt"

# Translation dictionary
TRANSLATIONS = {
    "pt": {
        "page_title": "Assistente Jurídico Português",
        "main_header": "⚖️ Assistente Jurídico Português",
        "language_selector": "Idioma / Language",
        "settings": "Configurações",
        "search_mode": "Modo de Pesquisa",
        "search_mode_ai": "Resposta Completa (com IA)",
        "search_mode_docs": "Apenas Documentos",
        "search_mode_help": "Escolha entre obter uma resposta elaborada pela IA ou apenas os documentos relevantes",
        "num_results": "Número de Resultados",
        "num_results_help": "Quantidade de documentos relevantes a retornar",
        "view_stats": "📊 Ver Estatísticas",
        "stats_error": "Não foi possível carregar estatísticas",
        "total_docs": "Total de Documentos",
        "total_vectors": "Total de Vetores",
        "about": "Sobre",
        "about_text": "Este assistente utiliza IA para ajudar com questões relacionadas à legislação portuguesa. Os dados são obtidos do Diário da República e outras fontes oficiais.",
        "question_placeholder": "Faça sua pergunta sobre a legislação portuguesa",
        "question_label": "Pergunta:",
        "question_example": "Ex: Quais são os requisitos para constituir uma empresa em Portugal?",
        "search_btn": "🔍 Pesquisar",
        "clear_btn": "🗑️ Limpar",
        "searching": "Pesquisando na legislação portuguesa...",
        "answer_title": "💡 Resposta",
        "sources_title": "📚 Fontes Relevantes",
        "source_prefix": "Fonte",
        "document": "Documento",
        "text_label": "**Texto:**",
        "metadata_label": "**Metadados:**",
        "relevance": "Relevância",
        "search_history": "📜 Histórico de Pesquisas",
        "no_searches": "Nenhuma pesquisa realizada ainda",
        "contract_analysis": "📄 Análise de Contratos (Beta)",
        "contract_analysis_info": "Faça upload de um contrato para identificar leis aplicáveis, obter resumos e identificar possíveis problemas.",
        "choose_file": "Escolha um arquivo",
        "file_types": "Formatos suportados: PDF, TXT, DOCX",
        "analysis_type": "Tipo de Análise",
        "analysis_complete": "Análise Completa",
        "analysis_summary": "Apenas Resumo",
        "analysis_compliance": "Verificação de Conformidade",
        "analyze_contract": "Analisar Contrato",
        "analyzing": "Analisando contrato...",
        "dev_feature": "Funcionalidade em desenvolvimento",
    },
    "en": {
        "page_title": "Portuguese Legal Assistant",
        "main_header": "⚖️ Portuguese Legal Assistant",
        "language_selector": "Language / Idioma",
        "settings": "Settings",
        "search_mode": "Search Mode",
        "search_mode_ai": "Complete Answer (with AI)",
        "search_mode_docs": "Documents Only",
        "search_mode_help": "Choose between getting an AI-generated answer or just relevant documents",
        "num_results": "Number of Results",
        "num_results_help": "Number of relevant documents to return",
        "view_stats": "📊 View Statistics",
        "stats_error": "Could not load statistics",
        "total_docs": "Total Documents",
        "total_vectors": "Total Vectors",
        "about": "About",
        "about_text": "This assistant uses AI to help with questions related to Portuguese legislation. Data is obtained from Diário da República and other official sources.",
        "question_placeholder": "Ask your question about Portuguese legislation",
        "question_label": "Question:",
        "question_example": "Ex: What are the requirements to establish a company in Portugal?",
        "search_btn": "🔍 Search",
        "clear_btn": "🗑️ Clear",
        "searching": "Searching Portuguese legislation...",
        "answer_title": "💡 Answer",
        "sources_title": "📚 Relevant Sources",
        "source_prefix": "Source",
        "document": "Document",
        "text_label": "**Text:**",
        "metadata_label": "**Metadata:**",
        "relevance": "Relevance",
        "search_history": "📜 Search History",
        "no_searches": "No searches performed yet",
        "contract_analysis": "📄 Contract Analysis (Beta)",
        "contract_analysis_info": "Upload a contract to identify applicable laws, get summaries and identify potential issues.",
        "choose_file": "Choose a file",
        "file_types": "Supported formats: PDF, TXT, DOCX",
        "analysis_type": "Analysis Type",
        "analysis_complete": "Complete Analysis",
        "analysis_summary": "Summary Only",
        "analysis_compliance": "Compliance Check",
        "analyze_contract": "Analyze Contract",
        "analyzing": "Analyzing contract...",
        "dev_feature": "Feature under development",
    },
}


def t(key: str) -> str:
    """Get translation for the current language."""
    return TRANSLATIONS[st.session_state.language].get(key, key)


def query_backend(
    query: str, language: str = "pt", use_llm: bool = True, top_k: int = 5
):
    """Send query to backend service."""
    try:
        response = requests.post(
            f"{API_BASE}/query",
            json={
                "query": query,
                "language": language,
                "use_llm": use_llm,
                "top_k": top_k,
            },
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        error_msg = (
            f"Erro ao processar consulta: {str(e)}"
            if language == "pt"
            else f"Error processing query: {str(e)}"
        )
        st.error(error_msg)
        return None


def main():
    """Main application."""

    # Sidebar with language selector first
    with st.sidebar:
        # Language selector at the top
        st.subheader("🌐 " + t("language_selector"))
        language_options = {"Português": "pt", "English": "en"}
        selected_language = st.selectbox(
            "",
            options=list(language_options.keys()),
            index=0 if st.session_state.language == "pt" else 1,
            key="language_selector",
        )

        # Update session state if language changed
        new_language = language_options[selected_language]
        if new_language != st.session_state.language:
            st.session_state.language = new_language
            st.rerun()

        st.divider()

        # Settings section
        st.subheader("⚙️ " + t("settings"))

        search_mode = st.radio(
            t("search_mode"),
            [t("search_mode_ai"), t("search_mode_docs")],
            help=t("search_mode_help"),
        )

        num_results = st.slider(
            t("num_results"),
            min_value=1,
            max_value=10,
            value=5,
            help=t("num_results_help"),
        )

        st.divider()

        # Statistics section
        st.subheader("📊 " + t("view_stats"))
        if st.button(t("view_stats"), use_container_width=True):
            try:
                stats = requests.get(f"{API_BASE}/stats").json()
                st.metric(t("total_docs"), stats["total_documents"])
                st.metric(t("total_vectors"), stats["total_vectors"])
            except:
                st.error(t("stats_error"))

        st.divider()

        # About section
        st.subheader("ℹ️ " + t("about"))
        st.info(t("about_text"))

    # Header
    st.markdown(
        f'<h1 class="main-header">{t("main_header")}</h1>', unsafe_allow_html=True
    )

    # Main content area
    col1, col2 = st.columns([2, 1])

    with col1:
        # Query input
        st.subheader(t("question_placeholder"))

        query = st.text_area(
            t("question_label"),
            placeholder=t("question_example"),
            height=100,
            key="query_input",
        )

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            search_button = st.button(
                t("search_btn"), type="primary", use_container_width=True
            )
        with col_btn2:
            clear_button = st.button(t("clear_btn"), use_container_width=True)

        if clear_button:
            st.session_state.messages = []
            st.session_state.search_history = []
            st.rerun()

        if search_button and query:
            # Add to history
            st.session_state.search_history.append(
                {"query": query, "timestamp": datetime.now().strftime("%H:%M:%S")}
            )

            # Show loading
            with st.spinner(t("searching")):
                use_llm = search_mode == t("search_mode_ai")
                result = query_backend(
                    query, st.session_state.language, use_llm, num_results
                )

            if result:
                # Display answer
                if use_llm and "answer" in result:
                    st.markdown(f"### {t('answer_title')}")
                    st.markdown(
                        f'<div class="answer-box">{result["answer"]}</div>',
                        unsafe_allow_html=True,
                    )

                # Display sources
                st.markdown(f"### {t('sources_title')}")
                for i, source in enumerate(result.get("sources", [])):
                    with st.expander(
                        f"{t('source_prefix')} {i+1}: {source.get('title', t('document'))}"
                    ):
                        st.write(f"{t('text_label')} {source.get('text', '')[:500]}...")
                        
                        # Create curated display info instead of raw metadata
                        display_info = {}
                        if source.get("issuing_body"):
                            display_info["Órgão Emissor" if st.session_state.language == "pt" else "Issuing Body"] = source.get("issuing_body")
                        if source.get("description"):
                            display_info["Descrição" if st.session_state.language == "pt" else "Description"] = source.get("description")
                        if source.get("document_type"):
                            display_info["Tipo de Documento" if st.session_state.language == "pt" else "Document Type"] = source.get("document_type")
                        if source.get("document_number"):
                            display_info["Número" if st.session_state.language == "pt" else "Number"] = source.get("document_number")
                        if source.get("publication_date"):
                            display_info["Data de Publicação" if st.session_state.language == "pt" else "Publication Date"] = source.get("publication_date")
                        if source.get("url"):
                            display_info["URL"] = source.get("url")
                            
                        # Add category/keywords if they exist in metadata or root level
                        if source.get("category"):
                            display_info["Categoria" if st.session_state.language == "pt" else "Category"] = source.get("category")
                        elif source.get("metadata", {}).get("category"):
                            display_info["Categoria" if st.session_state.language == "pt" else "Category"] = source["metadata"]["category"]
                            
                        if source.get("keywords"):
                            display_info["Palavras-chave" if st.session_state.language == "pt" else "Keywords"] = source.get("keywords")
                        elif source.get("metadata", {}).get("keywords"):
                            display_info["Palavras-chave" if st.session_state.language == "pt" else "Keywords"] = source["metadata"]["keywords"]
                        
                        if display_info:
                            st.write(t("metadata_label"))
                            st.json(display_info)
                            
                        if "score" in source:
                            st.progress(
                                source["score"],
                                text=f"{t('relevance')}: {source['score']:.2%}",
                            )

    with col2:
        # Search history
        st.subheader(t("search_history"))

        if st.session_state.search_history:
            for item in reversed(st.session_state.search_history[-10:]):
                st.markdown(
                    f"**{item['timestamp']}**  \n{item['query'][:50]}...",
                    help=item["query"],
                )
        else:
            st.info(t("no_searches"))

    # File upload section (Stage 2)
    with st.expander(t("contract_analysis"), expanded=False):
        st.info(t("contract_analysis_info"))

        uploaded_file = st.file_uploader(
            t("choose_file"), type=["pdf", "txt", "docx"], help=t("file_types")
        )

        if uploaded_file:
            analysis_type = st.selectbox(
                t("analysis_type"),
                [
                    t("analysis_complete"),
                    t("analysis_summary"),
                    t("analysis_compliance"),
                ],
            )

            if st.button(t("analyze_contract")):
                with st.spinner(t("analyzing")):
                    # TODO: Implement contract analysis
                    st.warning(t("dev_feature"))


if __name__ == "__main__":
    main()
