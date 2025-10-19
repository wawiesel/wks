from setuptools import setup, find_packages

setup(
    name="wks",
    version="0.1.0",
    description="Wieselquist Knowledge System - AI-assisted file organization",
    author="William Wieselquist",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "watchdog",  # File system monitoring
        "rich",      # Terminal formatting
        # Add more as needed
    ],
    entry_points={
        "console_scripts": [
            "wks=wks.cli:main",
        ],
    },
)
