"""
The Harvest module is for anything related to extracting raw lists of repositories from various sources, and, 
specifically, providing RESTful CRUD (create, read, update, delete) operations relating to these lists of repositories, 
providing the interface with our persistance layer.

These sources could include:
    GitHub search results
    Spack and other build system configuration files
    ArXiV
    University websites
    URLs within scientific papers
and so on.

Note: Harvesting only refers to repositories (and the metadata about how they were harvested) themselves; harvesting
does not include any data associated with the repository. (That comes in the bottling stage.)
"""