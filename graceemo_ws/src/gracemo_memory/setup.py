from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'gracemo_memory'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'), glob('config/*')),
        (os.path.join('share', package_name, 'launch'), glob('launch/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='GraceEMO Team',
    maintainer_email='team@graceemo.ai',
    description='GraceEMO Persistent Episodic & Semantic Memory Engine',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'memory_node = gracemo_memory.memory_node:main',
        ],
    },
)
