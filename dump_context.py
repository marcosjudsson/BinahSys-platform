import os
import glob

# Defina aqui os diretórios ou arquivos foco da missão
target_files = [
    "src/google_rag_engine.py",
    "src/chat_logic.py",
    # Se houver algum utils que gerencia credenciais, inclua aqui:
    # "src/auth_utils.py" 
]

# Se preferir ler tudo de .py dentro de src/ (caso não sejam centenas):
# target_files = glob.glob("src/*.py")

print("--- INICIO DO CONTEXT DUMP ---\n")

for filepath in target_files:
    # Resolve para caminhos relativos para manter a sanidade
    if os.path.exists(filepath):
        print(f"=== FILE START: {filepath} ===")
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                print(f.read())
        except Exception as e:
            print(f"# Erro ao ler arquivo: {e}")
        print(f"=== FILE END: {filepath} ===\n")
    else:
        # Tenta buscar via glob se a lista acima estiver comentada e usar a logica de pasta
        pass

# Fallback: Se você quiser listar todos os .py de src/ automaticamente, descomente abaixo:
for filepath in glob.glob("src/*.py"):
    if filepath not in target_files: # Evita duplicados se já listado
        print(f"=== FILE START: {filepath} ===")
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                print(f.read())
        except Exception as e:
            print(f"# Erro ao ler arquivo: {e}")
        print(f"=== FILE END: {filepath} ===\n")

print("--- FIM DO CONTEXT DUMP ---")