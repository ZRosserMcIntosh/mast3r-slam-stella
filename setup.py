from setuptools import setup, find_packages

setup(
    name='mast3r-slam-stella',
    version='0.1.0',
    author='Virgil',
    author_email='virgil@example.com',
    description='Create and manage .stella world files - ZIP containers for 3D environments',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/example/mast3r-slam-stella',
    packages=find_packages(include=['stella', 'stella.*']),
    install_requires=[
        'numpy>=1.20.0',
        'opencv-python>=4.5.0',
        'trimesh>=3.10.0',
    ],
    extras_require={
        'slam': [
            'open3d>=0.15.0',
            'scipy>=1.7.0',
        ],
        'dev': [
            'pytest>=7.0.0',
            'pytest-cov>=4.0.0',
        ],
    },
    entry_points={
        'console_scripts': [
            'stella=stella.cli:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'License :: Other/Proprietary License',
        'Operating System :: OS Independent',
        'Topic :: Scientific/Engineering :: Visualization',
        'Topic :: Multimedia :: Graphics :: 3D Modeling',
    ],
    python_requires='>=3.8',
    include_package_data=True,
    package_data={
        'stella': ['py.typed'],
    },
)