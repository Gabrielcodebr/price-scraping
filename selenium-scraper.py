"""
Ponto de entrada do scraper.

Mantido com este nome de arquivo porque o Dockerfile chama `python selenium-scraper.py`
(CMD) — trocar o nome exigiria alterar também o Dockerfile. Toda a lógica real foi
movida para o pacote scraper/ (veja scraper/main.py).
"""
from scraper.main import main

if __name__ == "__main__":
    main()
