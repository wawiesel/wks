from setuptools import setup, find_packages

setup(
    name="wks",
    version="0.4.0",
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
        "jinja2",             # Template rendering for CLI outputs
        "pytest>=7.0",        # Testing framework
        "pytest-timeout>=2.1",  # Test timeouts
        "pytest-xdist>=3.0",  # Parallel test execution
        "pre-commit",         # Git hook management
    ],
    entry_points={
        "console_scripts": [
            # Primary CLI name
            "wksc=wks.cli:main",
        ],
    },
)
