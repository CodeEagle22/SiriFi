from setuptools import setup, find_packages


try:
    with open("README.md", "r", encoding="utf-8") as fh:
        long_description = fh.read()
except FileNotFoundError:
    print("README.md file not found.")
    long_description = ""
except Exception as e:
    print("An error occurred while reading README.md:", str(e))
    long_description = ""
setup(
    name="sirifi",
    version="0.1.5.1",
    author="Your Name",
    author_email="you@example.com",
    description="Streaming financial data from Alpha Vantage, Binance, and Yahoo Finance",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/sirifi",  # Change or remove if not applicable
    packages=find_packages(),
    install_requires=[
        "pandas>=1.4",
        "requests",
        "yfinance>=0.2.36",
        "python-binance",
        "newsapi-python",
        "alpha_vantage",
        "newsapi-python",
        "vaderSentiment",
        "plotly"
        
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: MIT License",
    ],
    python_requires='>=3.7',
    include_package_data=True,
)
