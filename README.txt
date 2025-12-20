-   Create and activate a Python virtualenv (Windows PowerShell):
    
    -   conda create --prefix ./venv python=3.10 -y
    -   conda activate ./venv
-   Install dependencies:
    
    -   pip install -r requirements.txt
        
    -   python -m scripts.create_super_admin
        
    -   python -m scripts.seed_all
        
    -  python -m uvicorn app.main:app --reload                                       