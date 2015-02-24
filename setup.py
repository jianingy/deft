# -*- coding: utf-8 -*-
#
# Copyright 2015, Jianing Yang
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
#
# Author: Jianing Yang <jianingy.yang@gmail.com>
#
import setuptools

setuptools.setup(
    name='deft',
    version='0.1',
    description='View and Edit database record in terminal',
    author='Jianing Yang',
    author_email='jianingy.yang@gmail.com',
    url='http://github.com/jianingy/deft',
    scripts=['deft.py'],
    install_requires=['argparse', 'sqlalchemy', 'prettytable',
                      'pyparsing', 'PyYAML', 'psycopg2'],
    py_modules=['deft'],
    entry_points={'console_scripts': ['deft= deft:main']},
    classifiers=[
        'Development Status :: 1 - Planning',
        'Environment :: Console',
        'Topic :: Utilities',
    ],
)
