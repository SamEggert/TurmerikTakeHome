from setuptools import setup, find_packages

setup(
    name="clinical_trial_matcher",
    version="0.1",
    packages=find_packages(include=["src", "src.*"]),
    # Add install_requires for dependencies
    install_requires=[
        "pandas",
        "chromadb",
        "langchain-openai",
        "python-dotenv",
        "tqdm",
        "sentence-transformers",
        "openpyxl"
    ],
)