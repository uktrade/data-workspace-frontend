import setuptools


setuptools.setup(
    name="jupyterlab_template_notebooks",
    version="0.0.1",
    author="Department for International Trade",
    author_email="webops@digital.trade.gov.uk",
    packages=["jupyterlab_template_notebooks"],
    package_data={"": ["*.png", "*.ipynb"]},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
