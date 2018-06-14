#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('CHANGELOG.rst') as changelog_file:
    changelog = changelog_file.read()

requirements = [
    'click>=6.0',
    'isort',
    'pydevf==0.1.4',
]

test_requirements = [
]

setup(
    name='esss_fix_format',
    version='1.5.0',
    description="ESSS code formatter and checker",
    long_description=readme + '\n\n' + changelog,
    author="Bruno Oliveira",
    author_email='bruno@esss.com.br',
    url='https://github.com/esss/esss_fix_format',
    packages=[
        'esss_fix_format',
    ],
    package_dir={'esss_fix_format':
                 'esss_fix_format'},
    entry_points={
        'console_scripts': [
            'fix-format=esss_fix_format.cli:main',
            'ff=esss_fix_format.cli:main',
        ]
    },
    include_package_data=True,
    install_requires=requirements,
    license="MIT license",
    zip_safe=False,
    keywords='esss_fix_format',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        "Programming Language :: Python :: 2",
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
    test_suite='tests',
    tests_require=test_requirements
)
