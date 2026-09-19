import os
from setuptools import setup, find_packages

setup(
    name='BeSeen Door Controller Hardware API',
    version='0.2',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'get_swipes=door_controller.cli_synch_tools.get_swipes:main',
            'get_acl_from_controller=door_controller.cli_synch_tools.get_acl_from_controller:main',
            'get_foblist_from_controller=door_controller.cli_synch_tools.get_foblist_from_controller:main',
            'list_fobs_simple=door_controller.cli_synch_tools.list_fobs_simple:main',
            'list_fobs=door_controller.cli_synch_tools.list_fobs_simple:main',
            'BeSeen_driver=door_controller.cli_synch_tools.BeSeen_driver:main',
            'BeSeen_config_gui=door_controller.config_gui:main'
        ]
    },
    include_package_data=True,
    python_requires='>=3.8',
    url='https://github.com/ebpowell/BeSeenDoorController',
    license='GPL-v2',
    author='ebpowell',
    author_email='ebpowell.chip@gmail.com',
    description='OpenSource API layer and driver toolset for managing physical door access using the BeSeen Door Controller hardware.'
)
