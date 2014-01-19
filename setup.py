#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name='saedeploy',
    version='0.9',
    description='A handy command-line tool to deploy apps to Sina App Engine',
    author='Bo Zhu',
    url='https://github.com/zhuzhuor/saedeploy',
    packages=find_packages(),
    license='MIT',
    entry_points={
        'console_scripts': [
            'saedeploy = saedeploy.saedeploy:main'
        ]
    },
    install_requires=[
        'pyyaml',
        'termcolor'
    ]
)
