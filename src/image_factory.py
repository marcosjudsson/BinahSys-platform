import io
import gc
import fitz  # PyMuPDF
import streamlit as st
from google.cloud import storage
from src.utils import debug_log
from src.google_rag_engine import setup_google_credentials

def _parse_gcs_uri(uri: str):
    """
    Remove o prefixo gs:// e separa bucket e blob_name.
    """
    if not uri or not uri.startswith("gs://"):
        return None, None
    
    parts = uri[5:].split("/", 1)
    if len(parts) != 2:
        return None, None
        
    return parts[0], parts[1]

def _download_blob_volatile(bucket_name: str, blob_name: str) -> io.BytesIO:
    """
    Baixa blob para memória. 
    NOTA: Deve ser usado dentro de um contexto que garanta sua limpeza imediata.
    """
    try:
        setup_google_credentials()
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        buffer = io.BytesIO()
        blob.download_to_file(buffer)
        buffer.seek(0)
        return buffer
    except Exception as e:
        debug_log(f"Erro download GCS: {blob_name}", error=e)
        return None

@st.cache_data(ttl=3600, show_spinner=False)
def render_pdf_page_to_image(gcs_uri: str, page_number: int = 1, zoom: float = 2.0) -> bytes:
    """
    Baixa PDF, renderiza página como PNG e retorna os BYTES crus (não buffer).
    Cacheado pelo Streamlit para evitar downloads repetidos da Europa.
    
    Args:
        gcs_uri: gs://bucket/file.pdf
        page_number: 1-based index
        zoom: Qualidade (2.0 = HD)
    
    Returns:
        bytes: Conteúdo do arquivo PNG.
    """
    pdf_stream = None
    doc = None
    image_bytes = None

    try:
        bucket, blob_name = _parse_gcs_uri(gcs_uri)
        if not bucket:
            return None

        # 1. Download (Fase Crítica de Memória)
        pdf_stream = _download_blob_volatile(bucket, blob_name)
        if not pdf_stream:
            return None

        # 2. Renderização
        doc = fitz.open(stream=pdf_stream, filetype="pdf")
        
        # Ajuste de índice (Human 1-based -> Python 0-based)
        idx = page_number - 1
        if idx < 0: idx = 0
        if idx >= len(doc): idx = len(doc) - 1
        
        page = doc[idx]
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        # 3. Extração para Bytes Puros (Desacoplando do Fitz)
        image_bytes = pix.tobytes("png")
        
        debug_log(f"Imagem renderizada: {blob_name} pág {page_number}")

    except Exception as e:
        debug_log(f"Erro renderização imagem: {gcs_uri}", error=e)
        return None

    finally:
        # 4. LIMPEZA AGRESSIVA DE MEMÓRIA (Crítico para Streamlit Cloud)
        if doc:
            doc.close()
            del doc
        if pdf_stream:
            pdf_stream.close()
            del pdf_stream
        
        # Força o Garbage Collector a limpar os buffers grandes do PDF agora
        gc.collect()

    return image_bytes