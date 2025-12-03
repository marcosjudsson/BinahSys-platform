import streamlit as st
import logging

# Configuração básica de logging para o console
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger("BinahSys")

def debug_log(message: str, data=None, error: Exception = None):
    """
    Centraliza logs de debug.
    - Se 'debug_mode' estiver ativo na sessão: Exibe no Streamlit (Expander).
    - Sempre: Registra no console/logging do Python.
    """
    # 1. Log no Console (Backend)
    log_msg = f"{message}"
    if data:
        log_msg += f" | Data: {str(data)[:500]}..." # Trunca dados longos no console
    
    if error:
        logger.error(f"{log_msg} | Error: {str(error)}")
    else:
        logger.info(log_msg)

    # 2. Log na Interface (Frontend) - Apenas se Debug Mode estiver ON
    if st.session_state.get('debug_mode', False):
        icon = "❌" if error else "🕵️"
        label = f"{icon} Debug: {message}"
        
        with st.expander(label, expanded=False):
            if error:
                st.error(f"Exception: {str(error)}")
            
            if data:
                st.markdown("**Payload:**")
                if isinstance(data, (dict, list)):
                    st.json(data)
                else:
                    st.code(str(data))
