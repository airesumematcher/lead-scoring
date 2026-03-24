from setuptools import setup, find_packages

setup(
    name="lead-scoring",
    version="0.1.0",
    description="B2B Lead Scoring System with ACE Framework",
    author="RevOps Data Science",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.10",
    install_requires=[
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "scikit-learn>=1.3.0",
        "lightgbm>=4.0.0",
        "xgboost>=2.1.0",
        "sqlalchemy>=2.0.0",
        "psycopg2-binary>=2.9.0",
        "pydantic>=2.0.0",
        "python-dotenv>=1.0.0",
        "pyyaml>=6.0",
        "loguru>=0.7.0",
        "shap>=0.42.0",
        "requests>=2.31.0",
        "httpx>=0.28.0,<1.0.0",
        "python-multipart>=0.0.20",
        "openpyxl>=3.1.5",
        "xlrd>=2.0.1",
    ],
    extras_require={
        "dev": ["pytest>=7.4.0", "pytest-cov>=4.1.0"],
    },
)
