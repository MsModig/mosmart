#!/usr/bin/env python3
"""
Setup configuration for MoSMART - S.M.A.R.T Monitor Tool
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="mosmart",
    version="0.9.2",
    author="Magnus Modig",
    author_email="magnus@modig.no",
    description="S.M.A.R.T Monitor Tool for Linux - Real-time disk health monitoring with web dashboard",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/MsModig/mosmart",
    project_urls={
        "Bug Tracker": "https://github.com/MsModig/mosmart/issues",
        "Documentation": "https://github.com/MsModig/mosmart#readme",
    },
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Development Status :: 4 - Beta",
        "Intended Audience :: System Administrators",
        "Topic :: System :: Monitoring",
    ],
    python_requires=">=3.7",
    install_requires=[
        "pySMART>=1.2.0",
        "flask>=3.0.0",
        "flask-cors>=4.0.0",
        "waitress>=2.1.0",
    ],
    entry_points={
        "console_scripts": [
            "mosmart=smart_monitor:main",
        ],
    },
    include_package_data=True,
    keywords="smart monitoring disk health s.m.a.r.t linux",
    zip_safe=False,
)
