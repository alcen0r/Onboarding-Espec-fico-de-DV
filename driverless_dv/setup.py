from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'driverless_dv'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'weights'), glob('weights/*.pt')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='demarco',
    maintainer_email='gfdmarco@gmail.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
    'console_scripts': [
        'perception_node = driverless_dv.perception_node:main',
        'mapping_node = driverless_dv.mapping_node:main',
        'control_node = driverless_dv.control_node:main',
        ],
    },
)
