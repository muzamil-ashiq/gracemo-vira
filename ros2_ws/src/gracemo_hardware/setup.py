from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'gracemo_hardware'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'),
         glob('config/*.yaml')),
        (os.path.join('share', package_name, 'launch'),
         glob('launch/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Sabarish',
    maintainer_email='sabarish@gracemo.ai',
    description='GRaCEmo ViRa Hardware Abstraction Layer',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'mcu_bridge_node = gracemo_hardware.mcu_bridge_node:main',
            'hardware_status_node = gracemo_hardware.hardware_status_node:main',
        ],
    },
)
