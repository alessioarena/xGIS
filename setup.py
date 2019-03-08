from setuptools import setup

with open("README.md", 'r') as f:
    long_description = f.read()

setup(
    name='arcpy_extender',
    version='1.0',
    description='a module that helps running subprocess calls from within your arcpy, extending what you can achieve with ArcGIS',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author='Alessio Arena',
    author_email='alessio.arena@zoho.com',
    url="https://github.com/alessioarena/arcpy_extender",
    packages=['arcpy_extender'],
    package_dir={'arcpy_extender': 'core'},
    scripts=['scripts\setup_external_libs.py', 'scripts\getpip.py'],
    package_data={'arcpy_extender': ['*.yml']},
    classifiers=[
        "Programming Language :: Python :: 2",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)