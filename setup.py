from setuptools import setup, find_packages

setup(
    name='ww_door_controller',
    version='0.1',
    # packages=['door_controller/access_control_list.py',
    #           'door_controller/data_extractor.py',
    #           'door_controller/database',
    #           'door_controller/door_controller',
    #           'door_controller/fobs',
    #           'door_controller/pg_database',
    #           'door_controller/swipes'],
    packages=find_packages(),
    scripts=['scripts/get_recent_swipes.py'],
    url='',
    license='',
    author='ebpowell',
    author_email='ebpowell.chip@gmail.com',
    description=''
)
