from setuptools import find_packages
from setuptools import setup

with open("README.rst") as readme_file:
    readme = readme_file.read()

with open("CHANGELOG.rst") as changelog_file:
    changelog = changelog_file.read()

requirements = [
    "boltons",
    "black",
    "click>=6.0",
    "isort",
    "tomli",
]

setup(
    name="esss_fix_format",
    version="3.0.0",
    description="ESSS code formatter and checker",
    long_description=readme + "\n\n" + changelog,
    author="ESSS",
    author_email="foss@esss.co",
    url="https://github.com/esss/esss_fix_format",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    entry_points={
        "console_scripts": [
            "fix-format=esss_fix_format.cli:main",
            "ff=esss_fix_format.cli:main",
        ]
    },
    include_package_data=True,
    install_requires=requirements,
    license="MIT license",
    zip_safe=False,
    keywords="esss_fix_format",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ],
)
