"""Vertex AI LLM client for response generation."""

import logging
from typing import List, Dict, Any, Optional
import vertexai
from vertexai.generative_models import GenerativeModel
import asyncio
from concurrent.futures import ThreadPoolExecutor

from .config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Client for Vertex AI Gemini model."""

    def __init__(self):
        self.model = None
        self.executor = ThreadPoolExecutor(max_workers=2)
        self._initialize()

    def _initialize(self):
        """Initialize Vertex AI and Gemini model."""
        try:
            vertexai.init(
                project=settings.google_cloud_project,
                location=settings.vertex_ai_location
            )

            # Initialize Gemini model
            self.model = GenerativeModel(settings.llm_model)

            # Configure generation settings
            self.generation_config = {
                "temperature": settings.temperature,
                "max_output_tokens": settings.max_output_tokens,
                "top_p": 0.95,
                "top_k": 40
            }

            logger.info(f"Initialized LLM model: {settings.llm_model}")

        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}")
            raise

    def generate_response(
        self,
        query: str,
        contexts: List[Dict[str, Any]],
        system_prompt: Optional[str] = None
    ) -> str:
        """Generate a response using the LLM."""
        try:
            # Build the prompt
            prompt = self._build_prompt(query, contexts, system_prompt)

            # Generate response
            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config
            )

            return response.text

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise

    async def agenerate_response(
        self,
        query: str,
        contexts: List[Dict[str, Any]],
        system_prompt: Optional[str] = None
    ) -> str:
        """Async wrapper for response generation."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.generate_response,
            query,
            contexts,
            system_prompt
        )

    def _build_prompt(
        self,
        query: str,
        contexts: List[Dict[str, Any]],
        system_prompt: Optional[str] = None
    ) -> str:
        """Build the prompt for the LLM."""

        # Default system prompt for Portuguese legal assistant
        if not system_prompt:
            system_prompt = """Você é um assistente jurídico especializado em legislação portuguesa. 
Sua função é fornecer respostas precisas e úteis sobre leis portuguesas com base nos documentos fornecidos.

Diretrizes:
1. Responda sempre em português de Portugal
2. Cite os documentos legais específicos (número e data) ao fazer referências
3. Seja preciso e objetivo, mas também claro e acessível
4. Se não tiver certeza ou se a informação não estiver disponível nos contextos fornecidos, indique isso claramente
5. Organize a resposta de forma estruturada quando apropriado
6. Evite dar conselhos jurídicos pessoais - forneça apenas informações sobre a legislação"""

        # Build context section
        context_text = "\n\n".join([
            f"**Documento {i+1}:**\n"
            f"Título: {ctx.get('title', 'Sem título')}\n"
            f"Tipo: {ctx.get('document_type', 'Desconhecido')}\n"
            f"Data: {ctx.get('publication_date', 'Sem data')}\n"
            f"Texto: {ctx.get('text', '')[:1000]}..."
            for i, ctx in enumerate(contexts)
        ])

        # Build full prompt
        prompt = f"""{system_prompt}

Contextos Legais Relevantes:
{context_text}

Pergunta do Utilizador: {query}

Resposta:"""

        return prompt

    def analyze_contract(
        self,
        contract_text: str,
        analysis_type: str = "comprehensive"
    ) -> Dict[str, Any]:
        """Analyze a contract document."""

        prompts = {
            "comprehensive": """Analise este contrato e forneça:
1. Resumo do contrato (tipo, partes, objeto principal)
2. Cláusulas principais identificadas
3. Legislação portuguesa aplicável
4. Possíveis problemas ou cláusulas questionáveis
5. Sugestões de melhorias
6. Conformidade com a lei portuguesa""",

            "summary": """Forneça um resumo conciso deste contrato incluindo:
1. Tipo de contrato
2. Partes envolvidas
3. Objeto principal
4. Principais obrigações
5. Prazo/vigência""",

            "compliance": """Verifique a conformidade deste contrato com a legislação portuguesa:
1. Identifique as leis aplicáveis
2. Verifique cláusulas obrigatórias ausentes
3. Identifique cláusulas potencialmente inválidas
4. Sugira correções necessárias"""
        }

        prompt = f"""{prompts.get(analysis_type, prompts['comprehensive'])}

Contrato:
{contract_text[:4000]}...

Análise:"""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config
            )

            return {
                "analysis_type": analysis_type,
                "analysis": response.text,
                "status": "completed"
            }

        except Exception as e:
            logger.error(f"Error analyzing contract: {e}")
            return {
                "analysis_type": analysis_type,
                "analysis": "Erro ao analisar o contrato",
                "status": "error",
                "error": str(e)
            }

    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract legal entities from text."""
        prompt = f"""Extraia as seguintes entidades do texto jurídico português:
1. Números de leis/decretos (ex: Lei n.º 23/2024)
2. Datas importantes
3. Órgãos/instituições mencionados
4. Valores monetários
5. Prazos

Formato da resposta em JSON.

Texto:
{text[:2000]}

Entidades:"""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config
            )

            # Parse response (simplified - in production use proper JSON parsing)
            entities = {
                "laws": [],
                "dates": [],
                "institutions": [],
                "monetary_values": [],
                "deadlines": []
            }

            # Basic extraction logic would go here

            return entities

        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return {}


# Global LLM client instance
llm_client = LLMClient()
