import os
from setuptools import setup, find_packages

setup(
    name='ww_door_controller',
    version='0.1',
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
            'sync_controller=door_controller.key_management_application.synchronization:main'
        ]
    },
    package_data={
        'door_controller.key_management_application.web_app': ['templates/*.html'],
    },
    include_package_data=True,
    python_requires='>=3.8',
   # tools=['tools/get_recent_swipes.py'],
    url='',
    license='',
    author='ebpowell',
    author_email='ebpowell.chip@gmail.com',
    description=''
)
