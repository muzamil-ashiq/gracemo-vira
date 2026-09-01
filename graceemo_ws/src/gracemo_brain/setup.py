from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'gracemo_brain'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'), glob('config/*.*')),
        (os.path.join('share', package_name, 'config/behavior_trees'), glob('config/behavior_trees/*')),
        (os.path.join('share', package_name, 'config/prompts'), glob('config/prompts/*')),
        (os.path.join('share', package_name, 'launch'), glob('launch/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='GraceEMO Team',
    maintainer_email='team@graceemo.ai',
    description='GraceEMO AI Decision Making, LLM, and Planning Engine',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'llm_node = gracemo_brain.llm_node:main',
            'planner_node = gracemo_brain.planner_node:main',
        ],
    },
)
