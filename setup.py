import os
from setuptools import setup, find_packages

setup(
    name='ww_door_controller',
    version='0.1',
    packages=find_packages(),
    # List external dependencies from requirements.txt
    # install_requires=install_requires,

    # Define your command-line entry points (console scripts)
    entry_points={
        'console_scripts': [
            'get_swipes=door_controller.tools.get_recent_swipes:main',
            'get_acl_from_controller=door_controller.tools.get_acl_from_controller:main',
            'get_foblist_from_controller=door_controller.tools.get_foblist_from_controller:main',
            'set_permissions=door_controller.tools.set_permissions:main',
            'add_remove_fob=door_controller.tools.add_remove_fob:main',
            'list_fobs_simple=door_controller.tools.list_fobs_simple:main',
            'list_fobs=door_controller.tools.list_fobs:main'
            # ... add more tools here
        ]
    },
    python_requires='>=3.8',
   # tools=['tools/get_recent_swipes.py'],
    url='',
    license='',
    author='ebpowell',
    author_email='ebpowell.chip@gmail.com',
    description=''
)
