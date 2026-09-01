from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'gracemo_gazebo'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*')),
        (os.path.join('share', package_name, 'worlds'), glob('worlds/*')),
        (os.path.join('share', package_name, 'config'), glob('config/*')),
        (os.path.join('share', package_name, 'models'), glob('models/*')),
        (os.path.join('share', package_name, 'web'), glob('web/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='GraceEMO Team',
    maintainer_email='team@graceemo.ai',
    description='GraceEMO Simulation and Virtual Space Studio',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'virtual_space_node = gracemo_gazebo.virtual_space_node:main',
        ],
    },
)
