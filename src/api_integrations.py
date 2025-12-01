import os
import requests
from src.config import AVAILABLE_MODELS

def list_available_models():
    """
    Retorna a lista de modelos de IA aprovados para uso no sistema.
    Atualmente retorna a lista estática definida em config.py.
    Futuramente pode ser expandido para validar contra a API da Vertex AI.
    """
    return AVAILABLE_MODELS

def get_psi_data(url: str) -> dict:
    """Chama a API do Google PageSpeed Insights e retorna os scores de performance."""
    api_key = os.environ.get("PAGESPEED_API_KEY")
    if not api_key:
        return {"error": "GOOGLE_API_KEY não encontrada."}
    
    api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&key={api_key}&category=PERFORMANCE&category=ACCESSIBILITY&category=BEST_PRACTICES&category=SEO"
    
    try:
        response = requests.get(api_url)
        response.raise_for_status()  # Lança um erro para códigos de status ruins (4xx ou 5xx)
        data = response.json()
        
        # Extrair os scores principais
        performance_score = data.get('lighthouseResult', {}).get('categories', {}).get('performance', {}).get('score', 0) * 100
        accessibility_score = data.get('lighthouseResult', {}).get('categories', {}).get('accessibility', {}).get('score', 0) * 100
        best_practices_score = data.get('lighthouseResult', {}).get('categories', {}).get('best-practices', {}).get('score', 0) * 100
        seo_score = data.get('lighthouseResult', {}).get('categories', {}).get('seo', {}).get('score', 0) * 100
        
        return {
            "performance": f"{performance_score:.0f}",
            "accessibility": f"{accessibility_score:.0f}",
            "best_practices": f"{best_practices_score:.0f}",
            "seo": f"{seo_score:.0f}"
        }

    except requests.exceptions.RequestException as e:
        return {"error": f"Erro ao chamar a API do PageSpeed Insights: {e}"}
    except Exception as e:
        return {"error": f"Erro ao processar a resposta do PageSpeed Insights: {e}"}

# Exemplo de função para Google Search Console API
def get_gsc_data(query):
    # Implementação futura
    pass

# Exemplo de função para Google Keyword Planner API
def get_gkp_data(keywords):
    # Implementação futura
    pass