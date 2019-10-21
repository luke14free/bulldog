import setuptools
from bulldog.model import version

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="bulldog",
    version=version,
    author="Luca Giacomel",
    author_email="luca.giacomel@gmail.com",
    description="State management for Data Science & Analytics",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/luke14free/bulldog",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
