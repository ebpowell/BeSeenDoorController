import os
from setuptools import setup, find_packages

setup(
    name='BeSeen Door Controller - HOA Tools',
    version='0.2',
    packages=find_packages(),
    # List external dependencies from requirements.txt
    # install_requires=install_requires,

    entry_points={
        'console_scripts': [
            'get_swipes=door_controller.cli_synch_tools.get_recent_swipes:main',
            'get_acl_from_controller=door_controller.cli_synch_tools.get_acl_from_controller:main',
            'get_foblist_from_controller=door_controller.cli_synch_tools.get_foblist_from_controller:main',
            'list_fobs_simple=door_controller.cli_synch_tools.list_fobs_simple:main',
            'list_fobs=door_controller.cli_synch_tools.list_fobs_simple:main',
            'BeSeen_driver=door_controller.cli_synch_tools.BeSeen_driver:main',
            'BeSeen_web=door_controller.key_management_application.web_app.app:main',
            'sync_controller=door_controller.key_management_application.update_access:main',
            'trim_fobs=door_controller.key_management_application.trim_fobs:main',
            'update_access=door_controller.key_management_application.update_access:main'
        ]
    },
    package_data={
        'door_controller.key_management_application.web_app': ['templates/*.html'],
    },
    include_package_data=True,
    python_requires='>=3.8',
    url='https://github.com/ebpowell/BeSeenDoorController',
    license='GPL-v2',
    author='ebpowell',
    author_email='ebpowell.chip@gmail.com',
    description='Simplified, HOA Focused toolset for managing door acccess using the BeSeen Door Controller board.'
)
