from pathlib import Path
import runpy

# Ponto de entrada padrão para o Streamlit Community Cloud (streamlit_app.py)
runpy.run_path(str(Path(__file__).with_name("app.py")), run_name="__main__")
