from src.cli.main import app
from src.monitoring.logger import setup_logging

setup_logging()

if __name__ == "__main__":
    app()