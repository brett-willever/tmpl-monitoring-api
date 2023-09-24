from setuptools import setup, find_packages

setup(
    name="monitoring",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["fastapi", "uvicorn", "httpx", "sqlalchemy", "asyncpg"],
    entry_points={
        "console_scripts": [
            "monitoring-api=monitoring.__main__:cli",
        ],
    },
)
