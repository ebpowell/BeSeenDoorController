import os
from setuptools import setup, find_packages

setup(
    name='DoorController_Driver_API',
    version='0.2',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'get_swipes=door_controller.cli_synch_tools.get_swipes:main',
            'get_acl_from_controller=door_controller.cli_synch_tools.get_acl_from_controller:main',
            'get_foblist_from_controller=door_controller.cli_synch_tools.get_foblist_from_controller:main',
            'DoorController_Driver_API=door_controller.cli_synch_tools.DoorController_Driver_API:main',
            'BeSeen_driver=door_controller.cli_synch_tools.DoorController_Driver_API:main',
            'BeSeen_config_gui=door_controller.config_gui:main',
            'BeSeen_api=door_controller.api:main'
        ]
    },
    include_package_data=True,
    python_requires='>=3.8',
    url='https://github.com/ebpowell/BeSeenDoorController',
    license='GPL-v2',
    author='ebpowell',
    author_email='ebpowell.chip@gmail.com',
    description='OpenSource API layer and driver toolset for managing physical door access using the DoorController_Driver_API hardware.'
)
