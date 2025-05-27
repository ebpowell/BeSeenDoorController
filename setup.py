from setuptools import setup

setup(
    name='ww_door_controller',
    version='0.1',
    packages=['door_controller/access_control_list',
              'door_controller/data_extractor',
              'door_controller/database',
              'door_controller/door_controller',
              'door_controller/fobs',
              'door_controller/pg_database',
              'door_controller/swipes'],
    scripts=['scripts/get_recent_swipes'],
    url='',
    license='',
    author='ebpowell',
    author_email='ebpowell.chip@gmail,com',
    description=''
)
