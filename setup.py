from setuptools import setup, find_packages

setup(
    name="wks",
    version="0.2.4",
    description="Wieselquist Knowledge System - AI-assisted file organization",
    author="William Wieselquist",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "watchdog",           # File system monitoring
        "rich",               # Terminal formatting
        "pymongo",            # MongoDB
        "sentence-transformers",  # Embeddings
        "docling",            # Required content extraction engine
        "bsdiff4",            # Binary diff size for change snapshots
        "mongomock",          # In-memory MongoDB for tests
    ],
    entry_points={
        "console_scripts": [
            # Primary CLI name (short, avoids conflicts)
            "wkso=wks.cli:main",
        ],
    },
)
