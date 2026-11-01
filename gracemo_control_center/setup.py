from setuptools import find_packages, setup
import os
from glob import glob

package_name = "gracemo_control_center"

setup(
    name=package_name,
    version="1.0.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name] if os.path.exists("resource/" + package_name) else []),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="sabarishchandrasekaran",
    maintainer_email="samdavi163@gmail.com",
    description="GRaCEmo ViRa Unified Autonomous Robotics Control Center (UARCC) Desktop Application",
    license="Proprietary",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "control_center = gracemo_control_center.main:main",
        ],
    },
)
